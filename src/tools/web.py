"""
JARVIS Web-Tools

Kostenlose Websuche ohne API-Schlüssel über DuckDuckGo.

Aufbau:

    WebSearchTool → SearchProvider (austauschbar) → Internet

Fällt ein Anbieter aus, wird der nächste aus der konfigurierten Reihenfolge
versucht. Schlägt alles fehl, bleibt JARVIS funktionsfähig und meldet nur:
"Die Websuche ist momentan nicht verfügbar."
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from config.config import config
from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult
from src.utils.logging import WEB, get_logger

logger = get_logger(WEB)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

MAX_DOWNLOAD_BYTES = 2_000_000

_TAG_PATTERN = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")


def http_request(
    url: str,
    timeout: float,
    data: Optional[Dict[str, str]] = None,
) -> str:
    """
    Minimaler HTTP-Zugriff über die Standardbibliothek – bewusst ohne
    zusätzliche Abhängigkeit, damit JARVIS lokal lauffähig bleibt.
    """
    payload = urllib.parse.urlencode(data).encode("utf-8") if data else None

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        },
        method="POST" if payload else "GET",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_DOWNLOAD_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"

    return raw.decode(charset, errors="replace")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""

    def as_text(self) -> str:
        if self.snippet:
            return f"{self.title}\n  {self.snippet}\n  {self.url}"
        return f"{self.title}\n  {self.url}"


class _DuckDuckGoParser(HTMLParser):
    """Liest Titel, Link und Beschreibung aus einer DuckDuckGo-Ergebnisseite."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: List[SearchResult] = []
        self._current_url: Optional[str] = None
        self._current_title: List[str] = []
        self._in_snippet = False
        self._snippet: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "a" and ("result__a" in classes or "result-link" in classes):
            self._current_url = _clean_url(attributes.get("href", ""))
            self._current_title = []
            return

        if tag in {"a", "td", "div"} and (
            "result__snippet" in classes or "result-snippet" in classes
        ):
            self._in_snippet = True
            self._snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_url is not None and self._current_title:
            title = " ".join("".join(self._current_title).split())
            if title:
                self.results.append(
                    SearchResult(title=title, url=self._current_url, snippet="")
                )
            self._current_url = None
            self._current_title = []
            return

        if self._in_snippet and tag in {"a", "td", "div"}:
            snippet = " ".join("".join(self._snippet).split())
            self._in_snippet = False
            self._snippet = []

            if snippet and self.results:
                last = self.results[-1]
                if not last.snippet:
                    self.results[-1] = SearchResult(last.title, last.url, snippet)

    def handle_data(self, data: str) -> None:
        if self._current_url is not None:
            self._current_title.append(data)
        elif self._in_snippet:
            self._snippet.append(data)


def _clean_url(href: str) -> str:
    """Löst DuckDuckGo-Weiterleitungen (/l/?uddg=...) auf."""
    if not href:
        return ""

    if href.startswith("//"):
        href = f"https:{href}"

    parsed = urllib.parse.urlparse(href)

    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg")
        if target:
            return urllib.parse.unquote(target[0])

    return href


class SearchProvider(ABC):
    name = ""
    endpoint = ""

    @abstractmethod
    def search(self, query: str, max_results: int, timeout: float) -> List[SearchResult]:
        ...


class DuckDuckGoHtmlProvider(SearchProvider):
    name = "duckduckgo_html"
    endpoint = "https://html.duckduckgo.com/html/"

    def search(self, query: str, max_results: int, timeout: float) -> List[SearchResult]:
        html = http_request(self.endpoint, timeout, {"q": query, "kl": "de-de"})

        parser = _DuckDuckGoParser()
        parser.feed(html)

        return [result for result in parser.results if result.url][:max_results]


class DuckDuckGoLiteProvider(SearchProvider):
    name = "duckduckgo_lite"
    endpoint = "https://lite.duckduckgo.com/lite/"

    def search(self, query: str, max_results: int, timeout: float) -> List[SearchResult]:
        html = http_request(self.endpoint, timeout, {"q": query, "kl": "de-de"})

        parser = _DuckDuckGoParser()
        parser.feed(html)

        return [result for result in parser.results if result.url][:max_results]


class DuckDuckGoApiProvider(SearchProvider):
    """Offizielle Instant-Answer-API: liefert Definitionen und Themenlisten."""

    name = "duckduckgo_api"
    endpoint = "https://api.duckduckgo.com/"

    def search(self, query: str, max_results: int, timeout: float) -> List[SearchResult]:
        url = self.endpoint + "?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": 1, "kl": "de-de"}
        )
        payload = json.loads(http_request(url, timeout))
        results: List[SearchResult] = []

        abstract = payload.get("AbstractText")
        if abstract:
            results.append(
                SearchResult(
                    title=payload.get("Heading") or query,
                    url=payload.get("AbstractURL") or "",
                    snippet=abstract,
                )
            )

        for topic in payload.get("RelatedTopics", []):
            entries = topic.get("Topics", [topic])
            for entry in entries:
                text = entry.get("Text")
                link = entry.get("FirstURL")
                if not text or not link:
                    continue
                results.append(
                    SearchResult(title=text.split(" - ")[0], url=link, snippet=text)
                )
                if len(results) >= max_results:
                    return results

        return results[:max_results]


class WikipediaProvider(SearchProvider):
    """Deutsche Wikipedia als verlässliche, kostenlose Wissensquelle."""

    name = "wikipedia"
    endpoint = "https://de.wikipedia.org/w/api.php"

    def search(self, query: str, max_results: int, timeout: float) -> List[SearchResult]:
        url = self.endpoint + "?" + urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
            }
        )
        payload = json.loads(http_request(url, timeout))
        results: List[SearchResult] = []

        for item in payload.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = _ANY_TAG.sub("", unescape(item.get("snippet", "")))
            results.append(
                SearchResult(
                    title=title,
                    url="https://de.wikipedia.org/wiki/"
                    + urllib.parse.quote(title.replace(" ", "_")),
                    snippet=snippet,
                )
            )

        return results


PROVIDERS: Dict[str, type] = {
    DuckDuckGoHtmlProvider.name: DuckDuckGoHtmlProvider,
    DuckDuckGoLiteProvider.name: DuckDuckGoLiteProvider,
    DuckDuckGoApiProvider.name: DuckDuckGoApiProvider,
    WikipediaProvider.name: WikipediaProvider,
}


class WebSearchTool(Tool):
    name = "web_search"
    description = "Sucht im Internet (DuckDuckGo, ohne API-Schlüssel) und liefert Kurzergebnisse."
    parameters = [
        ToolParameter(name="query", description="Suchbegriff"),
        ToolParameter(
            name="max_results",
            description="Anzahl der Treffer",
            type="number",
            required=False,
        ),
    ]
    risk = RiskLevel.SAFE

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("web")

    def is_available(self) -> bool:
        return bool(self.settings.get("enabled", True))

    def _providers(self) -> List[SearchProvider]:
        order = self.settings.get("provider_order") or list(PROVIDERS)
        providers = []

        for name in order:
            provider_class = PROVIDERS.get(name)
            if provider_class is None:
                logger.warning(f"Unbekannter Suchanbieter: {name}")
                continue
            providers.append(provider_class())

        return providers

    def run(self, query: str, max_results: Any = None, **kwargs: Any) -> ToolResult:
        if not self.is_available():
            return ToolResult.failure("Die Websuche ist deaktiviert.")

        try:
            limit = int(max_results) if max_results else int(self.settings.get("max_results", 5))
        except (TypeError, ValueError):
            limit = 5

        timeout = float(self.settings.get("timeout", 10))
        errors: List[str] = []

        for provider in self._providers():
            try:
                results = provider.search(query, limit, timeout)
            except Exception as error:
                logger.warning(f"{provider.name} fehlgeschlagen: {error}")
                errors.append(f"{provider.name}: {error}")
                continue

            if results:
                logger.info(f"{len(results)} Treffer über {provider.name} für '{query}'.")
                return ToolResult.success(
                    "\n".join(result.as_text() for result in results),
                    provider=provider.name,
                    results=[result.__dict__ for result in results],
                )

            errors.append(f"{provider.name}: keine Treffer")

        return ToolResult.failure(
            "Die Websuche ist momentan nicht verfügbar. " + "; ".join(errors)
        )


class FetchUrlTool(Tool):
    name = "fetch_url"
    description = "Lädt eine Webseite und liefert ihren Textinhalt."
    parameters = [ToolParameter(name="url", description="Vollständige URL")]
    risk = RiskLevel.SAFE

    max_characters = 6000

    def run(self, url: str, **kwargs: Any) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            html = http_request(url, float(config.section("web").get("timeout", 10)))
        except (urllib.error.URLError, OSError, ValueError) as error:
            logger.warning(f"Abruf von {url} fehlgeschlagen: {error}")
            return ToolResult.failure(f"Seite nicht abrufbar: {error}")

        text = _TAG_PATTERN.sub(" ", html)
        text = _ANY_TAG.sub(" ", text)
        text = unescape(" ".join(text.split()))

        return ToolResult.success(text[: self.max_characters], url=url)
