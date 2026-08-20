"""
JARVIS Startpunkt

    python -m src.main          Oberfläche mit Partikel-Orb (Standard)
    python -m src.main --cli    Reine Texteingabe im Terminal

Ist keine grafische Anzeige vorhanden, wechselt JARVIS selbstständig in
den Textbetrieb.
"""

import argparse

from config.config import config
from src.core.brain import JarvisBrain
from src.utils.logging import setup_logging

EXIT_WORDS = {"exit", "quit", "beenden"}


def run_cli() -> None:
    """Textbetrieb im Terminal."""
    print("=" * 50)
    print("JARVIS V6")
    print("Lokaler KI-Assistent")
    print("=" * 50)
    print("JARVIS ist bereit, Sir.")
    print("Mit 'exit' beenden.")
    print()

    try:
        brain = JarvisBrain()
    except Exception as error:
        print("[FEHLER] JARVIS konnte nicht gestartet werden:")
        print(error)
        return

    try:
        while True:
            try:
                message = input("Du: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nJARVIS wird beendet, Sir.")
                break

            if not message:
                continue

            if message.lower() in EXIT_WORDS:
                print("JARVIS wird beendet, Sir.")
                break

            try:
                print(f"JARVIS: {brain.respond(message)}")
            except Exception as error:
                print(
                    f"[FEHLER] Bei der Verarbeitung ist "
                    f"ein Fehler aufgetreten: {error}"
                )
    finally:
        brain.close()


def run_ui() -> bool:
    """Startet die grafische Oberfläche. False, wenn das nicht möglich ist."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("[HINWEIS] tkinter fehlt (Linux: sudo apt install python3-tk).")
        return False

    from src.ui.app import JarvisApp

    try:
        app = JarvisApp()
    except tkinter.TclError as error:
        print(f"[HINWEIS] Keine grafische Anzeige verfügbar: {error}")
        return False

    app.run()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS – lokaler KI-Assistent")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Nur Texteingabe im Terminal, ohne Oberfläche",
    )
    arguments = parser.parse_args()

    logging_settings = config.section("logging")
    setup_logging(
        level=str(logging_settings.get("level", "INFO")),
        log_file=config.log_file_path if logging_settings.get("to_file") else None,
    )

    use_ui = not arguments.cli and config.section("ui").get("enabled", True)

    if use_ui and run_ui():
        return

    run_cli()


if __name__ == "__main__":
    main()
