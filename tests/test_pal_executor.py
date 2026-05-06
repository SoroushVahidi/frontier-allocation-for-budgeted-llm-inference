from __future__ import annotations

from experiments.pal_executor import execute_pal_code


def test_executes_simple_arithmetic_and_extracts_answer() -> None:
    r = execute_pal_code("a=3\nb=5\nanswer=a*b\nprint(answer)")
    assert r.pal_parse_ok is True
    assert r.pal_safety_ok is True
    assert r.pal_exec_ok is True
    assert r.pal_answer_normalized == "15"


def test_rejects_import_os() -> None:
    r = execute_pal_code("import os\nanswer=1\nprint(answer)")
    assert r.pal_parse_ok is True
    assert r.pal_safety_ok is False
    assert "import" in r.pal_error_message_sanitized


def test_rejects_open_read_write() -> None:
    r = execute_pal_code("f=open('x.txt','w')\nanswer=1\nprint(answer)")
    assert r.pal_safety_ok is False
    assert "open" in r.pal_error_message_sanitized


def test_rejects_eval_exec() -> None:
    r1 = execute_pal_code("answer=eval('2+2')\nprint(answer)")
    r2 = execute_pal_code("exec('answer=4')\nprint(answer)")
    assert r1.pal_safety_ok is False
    assert r2.pal_safety_ok is False


def test_rejects_attribute_and_dunder_access() -> None:
    r1 = execute_pal_code("answer=(1).__class__\nprint(answer)")
    r2 = execute_pal_code("__x=1\nanswer=__x\nprint(answer)")
    assert r1.pal_safety_ok is False
    assert r2.pal_safety_ok is False


def test_rejects_loops_functions_classes() -> None:
    r1 = execute_pal_code("for i in [1,2]:\n  pass\nanswer=1\nprint(answer)")
    r2 = execute_pal_code("def f():\n  return 1\nanswer=f()\nprint(answer)")
    r3 = execute_pal_code("class A:\n  pass\nanswer=1\nprint(answer)")
    assert r1.pal_safety_ok is False
    assert r2.pal_safety_ok is False
    assert r3.pal_safety_ok is False


def test_handles_division_and_negative_numbers() -> None:
    r = execute_pal_code("x=-9\ny=2\nanswer=x/y\nprint(answer)")
    assert r.pal_exec_ok is True
    assert r.pal_answer_normalized == "-4.5"


def test_captures_print_answer() -> None:
    r = execute_pal_code("x=7\nanswer=x+1\nprint(answer)")
    assert "8" in r.pal_stdout
    assert r.pal_answer_normalized == "8"


def test_allows_safe_int_float_conversion() -> None:
    r = execute_pal_code("x=float('6.0')\nanswer=int(x)\nprint(answer)")
    assert r.pal_parse_ok is True
    assert r.pal_safety_ok is True
    assert r.pal_exec_ok is True
    assert r.pal_answer_normalized == "6"


def test_sanitizes_error_messages() -> None:
    r = execute_pal_code("answer=1/0\nprint(answer)")
    assert r.pal_exec_ok is False
    assert "\n" not in r.pal_error_message_sanitized
    assert len(r.pal_error_message_sanitized) <= 240
