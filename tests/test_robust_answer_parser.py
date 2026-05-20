from __future__ import annotations

from experiments.robust_answer_parser import (
    CONF_AMBIGUOUS,
    CONF_HIGH,
    CONF_LOW,
    answers_equivalent,
    canonicalize_answer,
    parse_final_answer,
)


def test_hashes_simple() -> None:
    c = canonicalize_answer("work... #### 42")
    assert c.canonical_value == "42"
    assert c.cue_type == "hashes"
    assert c.confidence == CONF_HIGH


def test_hashes_currency_with_commas() -> None:
    c = canonicalize_answer("Result:\n#### $1,234.50")
    assert c.canonical_value == "1234.5"
    assert c.unit == "usd"


def test_boxed_fraction() -> None:
    c = canonicalize_answer(r"Hence \\boxed{3/4}")
    assert c.canonical_value == "0.75"
    assert c.numeric_type == "fraction"


def test_explicit_answer_phrase() -> None:
    c = canonicalize_answer("After solving, the answer is 12 dollars.")
    assert c.canonical_value == "12"
    assert c.unit == "usd"


def test_final_cue_beats_earlier_numbers() -> None:
    txt = "2 + 2 = 4. We tried 10 first. Final answer: 17"
    c = canonicalize_answer(txt)
    assert c.canonical_value == "17"
    assert c.cue_type == "final_answer_colon"


def test_last_arithmetic_line_low_confidence_without_cue() -> None:
    c = canonicalize_answer("Step 1\n8 + 4 = 12")
    assert c.canonical_value == "12"
    assert c.confidence == CONF_LOW


def test_ambiguous_or_statement() -> None:
    d = parse_final_answer("I think it is 18 or 20")
    assert d.selected is not None
    assert d.ambiguous is True
    assert d.confidence == CONF_AMBIGUOUS


def test_percentage() -> None:
    c = canonicalize_answer("Therefore the answer is 12%")
    assert c.canonical_value == "0.12"
    assert c.unit == "percent"


def test_decimal_fraction_equivalence() -> None:
    assert answers_equivalent("0.75", "3/4") is True


def test_currency_cents_equivalence() -> None:
    assert answers_equivalent("50 cents", "$0.50") is True


def test_negative_numbers() -> None:
    c = canonicalize_answer("Final answer: -12")
    assert c.canonical_value == "-12"


def test_thousands_separator() -> None:
    c = canonicalize_answer("#### 12,345")
    assert c.canonical_value == "12345"


def test_output_has_no_gold_fields() -> None:
    d = parse_final_answer("#### 42")
    payload = d.selected.__dict__ if d.selected is not None else {}
    lowered = " ".join(payload.keys()).lower()
    assert "gold" not in lowered
    assert "exact_match" not in lowered
