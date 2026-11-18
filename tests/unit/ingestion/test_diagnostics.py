"""Tests for parser diagnostics. All legal text is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import DiagnosticCode, DiagnosticSeverity
from tests.unit.ingestion.helpers import parse

CASES = [
    (
        DiagnosticCode.DUPLICATE_ARTICLE,
        DiagnosticSeverity.ERROR,
        "Član 1.\nPrva.\n\nČlan 1.\nDruga.",
        4,
    ),
    (
        DiagnosticCode.ARTICLE_NUMBER_GAP,
        DiagnosticSeverity.WARNING,
        "Član 1.\nPrva.\n\nČlan 3.\nTreća.",
        4,
    ),
    (
        DiagnosticCode.ARTICLE_OUT_OF_ORDER,
        DiagnosticSeverity.WARNING,
        "Član 1.\nPrva.\n\nČlan 2.\nDruga.\n\nČlan 2a.\nUmetnuta.\n\nČlan 1a.\nKasna.",
        10,
    ),
    (
        DiagnosticCode.PARAGRAPH_NUMBER_GAP,
        DiagnosticSeverity.WARNING,
        "Član 1.\n(1) Prvi.\n(3) Treći.",
        3,
    ),
    (
        DiagnosticCode.EMPTY_ARTICLE,
        DiagnosticSeverity.WARNING,
        "Član 1.\n\nČlan 2.\nDruga.",
        1,
    ),
    (
        DiagnosticCode.UNASSIGNED_TEXT,
        DiagnosticSeverity.WARNING,
        "DIO PRVI\n\nIzmišljeni tekst bez mjesta.\n\nČlan 1.\nPrva.",
        3,
    ),
    (
        DiagnosticCode.UNTERMINATED_QUOTE,
        DiagnosticSeverity.WARNING,
        "Član 1.\n„Izmišljeni navod bez kraja.\nDruga rečenica.",
        2,
    ),
    (
        DiagnosticCode.QUOTED_HEADING,
        DiagnosticSeverity.WARNING,
        "Član 1.\n„Član 7a.\nIzmišljeni dodani tekst.“",
        2,
    ),
]


def test_cases_cover_every_diagnostic_code() -> None:
    assert {case[0] for case in CASES} == set(DiagnosticCode)


@pytest.mark.parametrize(("code", "severity", "text", "line"), CASES)
def test_reports_diagnostic(
    code: DiagnosticCode, severity: DiagnosticSeverity, text: str, line: int
) -> None:
    result = parse(text)

    assert [item.code for item in result.diagnostics] == [code]
    diagnostic = result.diagnostics[0]
    assert (diagnostic.severity, diagnostic.line) == (severity, line)
    source = result.law.source_text
    assert source[diagnostic.offset :].startswith(source.split("\n")[line - 1])


def test_duplicate_article_keeps_both_with_unique_ids() -> None:
    articles = parse("Član 1.\n(1) Prva.\n\nČlan 1.\n(1) Druga.\n\nČlan 1.\nTreća.").law.articles

    assert [article.id for article in articles] == [
        "fiktivni-zakon:cl-1",
        "fiktivni-zakon:cl-1-dup-2",
        "fiktivni-zakon:cl-1-dup-3",
    ]
    assert articles[1].paragraphs[0].id == "fiktivni-zakon:cl-1-dup-2:st-1"


def test_inserted_articles_do_not_report_a_gap() -> None:
    result = parse("Član 1.\nPrva.\n\nČlan 1a.\nDruga.\n\nČlan 1b.\nTreća.\n\nČlan 2.\nČetvrta.")

    assert result.diagnostics == ()


def test_cyrillic_suffixes_follow_cyrillic_alphabet_order() -> None:
    text = "Члан 1.\nА.\n\nЧлан 1г.\nБ.\n\nЧлан 1д.\nВ."

    assert parse(text).diagnostics == ()


def test_missing_first_article_reports_a_gap() -> None:
    result = parse("Član 3.\nTreća.")

    assert [item.code for item in result.diagnostics] == [DiagnosticCode.ARTICLE_NUMBER_GAP]


def test_first_paragraph_must_be_number_one() -> None:
    result = parse("Član 1.\n(2) Drugi.")

    assert [item.code for item in result.diagnostics] == [DiagnosticCode.PARAGRAPH_NUMBER_GAP]


def test_repeated_paragraph_number_gets_unique_id() -> None:
    result = parse("Član 1.\n(1) Prvi.\n(1) Ponovljeni.")

    assert [paragraph.id for paragraph in result.law.articles[0].paragraphs] == [
        "fiktivni-zakon:cl-1:st-1",
        "fiktivni-zakon:cl-1:st-1-dup-2",
    ]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.PARAGRAPH_NUMBER_GAP]
