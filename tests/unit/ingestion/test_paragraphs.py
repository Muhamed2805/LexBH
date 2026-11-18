"""Tests for paragraphs and points. All legal text is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import PointKind
from tests.unit.ingestion.helpers import single_article


def test_numbered_paragraphs_collect_following_lines() -> None:
    article = single_article(
        "Član 1.\n(1) Prvi stav koji se\nnastavlja u novom redu.\n\nI poslije praznog reda.\n"
        "(2) Drugi stav."
    )

    first, second = article.paragraphs
    assert (first.id, first.number, first.ordinal) == ("fiktivni-zakon:cl-1:st-1", 1, 1)
    assert first.text == "Prvi stav koji se\nnastavlja u novom redu.\n\nI poslije praznog reda."
    assert (second.id, second.number, second.text) == (
        "fiktivni-zakon:cl-1:st-2",
        2,
        "Drugi stav.",
    )


def test_blank_line_blocks_are_unnumbered_paragraphs() -> None:
    article = single_article("Član 1.\nPrvi blok\nu dva reda.\n\nDrugi blok.")

    first, second = article.paragraphs
    assert (first.id, first.number, first.ordinal) == ("fiktivni-zakon:cl-1:p-1", None, 1)
    assert first.text == "Prvi blok\nu dva reda."
    assert (second.id, second.ordinal, second.text) == (
        "fiktivni-zakon:cl-1:p-2",
        2,
        "Drugi blok.",
    )


def test_text_before_first_marker_is_an_unnumbered_paragraph() -> None:
    article = single_article("Član 1.\nUvodni tekst.\n(1) Prvi stav.")

    assert [paragraph.number for paragraph in article.paragraphs] == [None, 1]


@pytest.mark.parametrize(
    ("line", "kind", "label", "suffix"),
    [
        ("a) tekst", PointKind.LETTER, "a", "t-a"),
        ("(a) tekst", PointKind.LETTER, "a", "t-a"),
        ("а) tekst", PointKind.LETTER, "a", "t-a"),
        ("б) tekst", PointKind.LETTER, "b", "t-b"),
        ("в) tekst", PointKind.LETTER, "v", "t-v"),
        ("ж) tekst", PointKind.LETTER, "ž", "t-ž"),
        ("љ) tekst", PointKind.LETTER, "lj", "t-lj"),
        ("џ) tekst", PointKind.LETTER, "dž", "t-dž"),
        ("č) tekst", PointKind.LETTER, "č", "t-č"),
        ("dž) tekst", PointKind.LETTER, "dž", "t-dž"),
        ("1) tekst", PointKind.NUMBER, "1", "t-1"),
        ("1.) tekst", PointKind.NUMBER, "1", "t-1"),
        ("- tekst", PointKind.DASH, "-", "al-1"),
        ("– tekst", PointKind.DASH, "-", "al-1"),
    ],
)
def test_recognizes_point_types(line: str, kind: PointKind, label: str, suffix: str) -> None:
    article = single_article(f"Član 1.\n(1) Uvod:\n{line}")

    point = article.paragraphs[0].points[0]
    assert (point.kind, point.label, point.text) == (kind, label, "tekst")
    assert point.id == f"fiktivni-zakon:cl-1:st-1:{suffix}"


def test_wrapped_lines_continue_the_current_point() -> None:
    article = single_article("Član 1.\n(1) Uvod:\na) prva tačka koja\nse nastavlja,\nb) druga.")

    first, second = article.paragraphs[0].points
    assert first.text == "prva tačka koja\nse nastavlja,"
    assert second.text == "druga."


def test_blank_line_ends_the_current_point() -> None:
    article = single_article("Član 1.\n(1) Uvod:\na) tačka.\n\nZavršni tekst stava.")

    paragraph = article.paragraphs[0]
    assert paragraph.points[0].text == "tačka."
    assert paragraph.text.endswith("Završni tekst stava.")


def test_dash_ids_use_ordinals() -> None:
    article = single_article("Član 1.\n(1) Uvod:\n- prva,\n– druga.")

    assert [point.id for point in article.paragraphs[0].points] == [
        "fiktivni-zakon:cl-1:st-1:al-1",
        "fiktivni-zakon:cl-1:st-1:al-2",
    ]


def test_points_in_unnumbered_paragraph_use_paragraph_id() -> None:
    article = single_article("Član 1.\nUvod:\na) tačka.")

    assert article.paragraphs[0].points[0].id == "fiktivni-zakon:cl-1:p-1:t-a"


def test_list_separated_by_blank_lines_stays_in_one_paragraph() -> None:
    article = single_article("Član 1.\nUvod:\n\na) prva,\n\nb) druga.\n\nNovi blok.")

    assert len(article.paragraphs) == 2
    assert [point.label for point in article.paragraphs[0].points] == ["a", "b"]


def test_repeated_point_labels_get_unique_ids() -> None:
    article = single_article("Član 1.\n(1) Uvod:\na) prva,\na) ponovljena.")

    assert [point.id for point in article.paragraphs[0].points] == [
        "fiktivni-zakon:cl-1:st-1:t-a",
        "fiktivni-zakon:cl-1:st-1:t-a-dup-2",
    ]
