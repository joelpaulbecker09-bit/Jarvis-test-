"""
JARVIS Rechner-Tool

Rechnet deterministisch über einen begrenzten AST-Interpreter.
Kein eval() auf Benutzereingaben.
"""

import ast
import math
import operator
from typing import Any, Callable, Dict, List

from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult

BINARY_OPERATORS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS: Dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

FUNCTIONS: Dict[str, Callable[..., float]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "floor": math.floor,
    "ceil": math.ceil,
}

CONSTANTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

MAX_POWER = 1000


def evaluate(expression: str) -> float:
    """
    Wertet einen mathematischen Ausdruck sicher aus.

    Erlaubt sind Zahlen, Grundrechenarten, Klammern, Konstanten (pi, e)
    und die Funktionen aus FUNCTIONS.
    """
    normalized = (
        expression.replace("^", "**")
        .replace(",", ".")
        .replace("×", "*")
        .replace("÷", "/")
        .strip()
    )

    tree = ast.parse(normalized, mode="eval")
    return _evaluate_node(tree.body)


def _evaluate_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Nur Zahlen sind erlaubt.")

    if isinstance(node, ast.BinOp):
        handler = BINARY_OPERATORS.get(type(node.op))
        if handler is None:
            raise ValueError("Nicht unterstützter Operator.")

        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER:
            raise ValueError("Exponent ist zu groß.")

        return handler(left, right)

    if isinstance(node, ast.UnaryOp):
        handler = UNARY_OPERATORS.get(type(node.op))
        if handler is None:
            raise ValueError("Nicht unterstützter Operator.")
        return handler(_evaluate_node(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise ValueError("Nicht unterstützte Funktion.")
        arguments = [_evaluate_node(argument) for argument in node.args]
        return FUNCTIONS[node.func.id](*arguments)

    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise ValueError(f"Unbekannter Name: {node.id}")

    raise ValueError("Ausdruck ist nicht erlaubt.")


class CalculatorTool(Tool):
    name = "calculator"
    description = "Berechnet einen mathematischen Ausdruck, z. B. '12 * (3 + 4)'."
    parameters: List[ToolParameter] = [
        ToolParameter(
            name="expression",
            description="Mathematischer Ausdruck",
        )
    ]
    risk = RiskLevel.SAFE

    def run(self, expression: str, **kwargs: Any) -> ToolResult:
        try:
            value = evaluate(expression)
        except ZeroDivisionError:
            return ToolResult.failure("Division durch null.")
        except (SyntaxError, ValueError, TypeError, OverflowError) as error:
            return ToolResult.failure(f"Ungültiger Ausdruck: {error}")

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        return ToolResult.success(f"{expression} = {value}", value=value)
