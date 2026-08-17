"""Tests für das Werkzeug-System: Rechner, Rechte, Registry, Dateien."""

import tempfile
import unittest
from pathlib import Path

from src.tools.base import ToolResult
from src.tools.calculator import CalculatorTool, evaluate
from src.tools.files import ReadFileTool, WriteFileTool
from src.tools.permissions import PermissionPolicy
from src.tools.registry import ToolRegistry
from src.tools.terminal import TerminalTool
from src.tools.time_tools import CurrentTimeTool


class TestCalculator(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(evaluate("2 + 3 * 4"), 14)
        self.assertAlmostEqual(evaluate("sqrt(16)"), 4.0)

    def test_rejects_code_execution(self):
        with self.assertRaises(ValueError):
            evaluate("__import__('os').system('ls')")

    def test_tool_returns_result(self):
        result = CalculatorTool().execute({"expression": "10 / 4"})
        self.assertTrue(result.ok)
        self.assertIn("2.5", result.output)

    def test_tool_reports_error_instead_of_raising(self):
        result = CalculatorTool().execute({"expression": "1 / 0"})
        self.assertFalse(result.ok)


class TestPermissions(unittest.TestCase):
    def test_terminal_disabled_by_default(self):
        policy = PermissionPolicy(settings={"allow_terminal": False})
        decision = policy.check(TerminalTool(policy=policy))

        self.assertFalse(decision.allowed)
        self.assertIn("Terminal", decision.reason)

    def test_path_outside_allowed_roots_is_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            policy = PermissionPolicy(settings={"file_roots": [folder]})

            self.assertTrue(policy.check_path(Path(folder) / "a.txt").allowed)
            self.assertFalse(policy.check_path(Path("/etc/passwd")).allowed)

    def test_confirmation_denied_without_handler(self):
        policy = PermissionPolicy(confirm_handler=None, settings={"confirm_dangerous": True})
        self.assertFalse(policy.confirm("Datei überschreiben?").allowed)

    def test_confirmation_uses_handler(self):
        policy = PermissionPolicy(
            confirm_handler=lambda question: True,
            settings={"confirm_dangerous": True},
        )
        self.assertTrue(policy.confirm("Datei überschreiben?").allowed)


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_default_tools_registered(self):
        self.assertIn("calculator", self.registry.names())
        self.assertIn("current_time", self.registry.names())

    def test_unknown_tool_does_not_raise(self):
        result = self.registry.execute("gibt_es_nicht", {})
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.ok)

    def test_broken_tool_does_not_stop_jarvis(self):
        class BrokenTool(CurrentTimeTool):
            name = "kaputt"

            def run(self, arguments):
                raise RuntimeError("Absturz")

        self.registry.register(BrokenTool())
        result = self.registry.execute("kaputt", {})
        self.assertFalse(result.ok)

    def test_descriptions_contain_tool_names(self):
        self.assertIn("calculator", self.registry.describe())


class TestFileTools(unittest.TestCase):
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as folder:
            policy = PermissionPolicy(
                settings={"allow_file_write": True, "file_roots": [folder]}
            )
            target = Path(folder) / "notiz.txt"

            write = WriteFileTool(policy=policy).execute(
                {"path": str(target), "content": "Hallo Sir"}
            )
            self.assertTrue(write.ok, write.error)

            read = ReadFileTool(policy=policy).execute({"path": str(target)})
            self.assertIn("Hallo Sir", read.output)

    def test_overwrite_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "notiz.txt"
            target.write_text("alt", encoding="utf-8")

            policy = PermissionPolicy(
                confirm_handler=lambda question: False,
                settings={
                    "allow_file_write": True,
                    "file_roots": [folder],
                    "confirm_dangerous": True,
                },
            )

            result = WriteFileTool(policy=policy).execute(
                {"path": str(target), "content": "neu"}
            )

            self.assertFalse(result.ok)
            self.assertEqual(target.read_text(encoding="utf-8"), "alt")


if __name__ == "__main__":
    unittest.main()
