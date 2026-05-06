from __future__ import annotations

import ast
import contextlib
import io
from dataclasses import dataclass
from typing import Any


@dataclass
class PALExecutionResult:
    pal_parse_ok: bool
    pal_safety_ok: bool
    pal_exec_ok: bool
    pal_stdout: str
    pal_answer_raw: str
    pal_answer_normalized: str
    pal_error_type: str
    pal_error_message_sanitized: str


_ALLOWED_BUILTINS: dict[str, Any] = {
    "print": print,
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
_ALLOWED_NODES = (
    ast.Module,
    ast.Assign,
    ast.Expr,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Tuple,
    ast.List,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
)
_DISALLOWED_NAMES = {
    "eval",
    "exec",
    "open",
    "input",
    "compile",
    "globals",
    "locals",
    "vars",
    "dir",
    "__import__",
    "os",
    "sys",
    "subprocess",
}


def _sanitize_error(exc: Exception) -> tuple[str, str]:
    et = type(exc).__name__
    msg = str(exc)
    for token in ("\n", "\r", "\t"):
        msg = msg.replace(token, " ")
    msg = " ".join(msg.split())
    if len(msg) > 240:
        msg = msg[:240]
    return et, msg


def _normalize_numeric(v: Any) -> str:
    if isinstance(v, bool):
        return ""
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    s = str(v).strip().replace(",", "")
    if not s:
        return ""
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return ""


def _extract_numeric_from_stdout(stdout: str) -> str:
    lines = [x.strip() for x in str(stdout or "").splitlines() if x.strip()]
    if not lines:
        return ""
    return _normalize_numeric(lines[-1])


class _PALSafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.error: str = ""

    def fail(self, msg: str) -> None:
        if not self.error:
            self.error = msg

    def generic_visit(self, node: ast.AST) -> None:
        if self.error:
            return
        if not isinstance(node, _ALLOWED_NODES):
            self.fail(f"disallowed_ast_node:{type(node).__name__}")
            return
        super().generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        self.fail("attribute_access_disallowed")

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        self.fail("subscript_disallowed")

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        self.fail("import_disallowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self.fail("import_from_disallowed")

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self.fail("while_disallowed")

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self.fail("for_disallowed")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.fail("function_def_disallowed")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.fail("class_def_disallowed")

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        self.fail("lambda_disallowed")

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.fail("if_disallowed")

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self.fail("try_disallowed")

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        self.fail("with_disallowed")

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        name = str(node.id or "")
        if name.startswith("__"):
            self.fail("dunder_name_disallowed")
            return
        if name in _DISALLOWED_NAMES:
            self.fail(f"disallowed_name:{name}")
            return
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:  # noqa: N802
        if not isinstance(node.op, _ALLOWED_BINOPS):
            self.fail("binop_disallowed")
            return
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:  # noqa: N802
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            self.fail("unaryop_disallowed")
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if not isinstance(node.func, ast.Name):
            self.fail("call_target_disallowed")
            return
        fn = str(node.func.id or "")
        if fn not in _ALLOWED_BUILTINS:
            self.fail(f"call_disallowed:{fn}")
            return
        self.generic_visit(node)


def execute_pal_code(code: str) -> PALExecutionResult:
    raw_code = str(code or "")
    if not raw_code.strip():
        return PALExecutionResult(False, False, False, "", "", "", "ValueError", "empty_code")
    try:
        tree = ast.parse(raw_code, mode="exec")
    except Exception as exc:
        et, msg = _sanitize_error(exc)
        return PALExecutionResult(False, False, False, "", "", "", et, msg)

    visitor = _PALSafetyVisitor()
    visitor.visit(tree)
    if visitor.error:
        return PALExecutionResult(True, False, False, "", "", "", "SafetyError", visitor.error)

    glb = {"__builtins__": dict(_ALLOWED_BUILTINS)}
    loc: dict[str, Any] = {}
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(compile(tree, "<pal>", "exec"), glb, loc)  # noqa: S102
    except Exception as exc:
        et, msg = _sanitize_error(exc)
        out = stdout.getvalue()
        return PALExecutionResult(True, True, False, out, "", "", et, msg)

    out = stdout.getvalue()
    ans = _normalize_numeric(loc.get("answer"))
    if not ans:
        ans = _extract_numeric_from_stdout(out)
    if not ans:
        return PALExecutionResult(True, True, False, out, "", "", "ValueError", "no_numeric_answer_extracted")
    return PALExecutionResult(True, True, True, out, ans, ans, "", "")
