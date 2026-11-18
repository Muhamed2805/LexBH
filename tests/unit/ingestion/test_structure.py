"""Tests for structure headings, preamble, and closing text. All legal text is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import StructureKind
from tests.unit.ingestion.helpers import parse, single_article

ARTICLE = "Član 1.\nIzmišljena odredba."


@pytest.mark.parametrize(
    ("heading", "kind", "label", "title"),
    [
        ("DIO PRVI", StructureKind.PART, "DIO PRVI", None),
        ("PRVI DIO", StructureKind.PART, "PRVI DIO", None),
        ("I. DIO", StructureKind.PART, "I. DIO", None),
        ("DIO I", StructureKind.PART, "DIO I", None),
        ("ДИО ПРВИ", StructureKind.PART, "ДИО ПРВИ", None),
        ("ПРВИ ДИО", StructureKind.PART, "ПРВИ ДИО", None),
        ("I. ДИО", StructureKind.PART, "I. ДИО", None),
        ("ДИО I", StructureKind.PART, "ДИО I", None),
        ("GLAVA I", StructureKind.CHAPTER, "GLAVA I", None),
        ("GLAVA I. NASLOV", StructureKind.CHAPTER, "GLAVA I", "NASLOV"),
        ("POGLAVLJE I", StructureKind.CHAPTER, "POGLAVLJE I", None),
        ("ГЛАВА I", StructureKind.CHAPTER, "ГЛАВА I", None),
        ("ГЛАВА I. НАСЛОВ", StructureKind.CHAPTER, "ГЛАВА I", "НАСЛОВ"),
        ("ПОГЛАВЉЕ I", StructureKind.CHAPTER, "ПОГЛАВЉЕ I", None),
        ("ODJELJAK A", StructureKind.SECTION, "ODJELJAK A", None),
        ("ODJELJAK 1", StructureKind.SECTION, "ODJELJAK 1", None),
        ("ОДЈЕЉАК А", StructureKind.SECTION, "ОДЈЕЉАК А", None),
        ("ОДЈЕЉАК 1", StructureKind.SECTION, "ОДЈЕЉАК 1", None),
    ],
)
def test_recognizes_structure_headings(
    heading: str, kind: StructureKind, label: str, title: str | None
) -> None:
    article = single_article(f"{heading}\n\n{ARTICLE}")

    found = article.structure_path[0]
    assert (found.kind, found.label, found.title) == (kind, label, title)


def test_reads_uppercase_title_on_next_line() -> None:
    law = parse(f"GLAVA I\nIZMIŠLJENI NASLOV\n\n{ARTICLE}").law

    heading = law.articles[0].structure_path[0]
    assert heading.title == "IZMIŠLJENI NASLOV"
    assert law.source_text[heading.start : heading.end] == "GLAVA I\nIZMIŠLJENI NASLOV"


def test_mixed_case_next_line_is_not_a_structure_title() -> None:
    article = single_article(f"GLAVA I\nIzmišljeni tekst\n\n{ARTICLE}")

    assert article.structure_path[0].title is None


@pytest.mark.parametrize(
    "line",
    ["GLAVA I ovog zakona se primjenjuje.", "Glava I ovog zakona se primjenjuje.", "DIO zakona"],
)
def test_body_lines_are_not_structure_headings(line: str) -> None:
    article = single_article(f"Član 1.\nPrva odredba.\n{line}")

    assert article.structure_path == ()
    assert line in article.text


def test_structure_path_replaces_and_clears_lower_levels() -> None:
    text = "\n\n".join(
        [
            "DIO PRVI",
            "GLAVA I",
            "ODJELJAK A",
            "Član 1.\nPrva.",
            "ODJELJAK B",
            "Član 2.\nDruga.",
            "GLAVA II",
            "Član 3.\nTreća.",
            "DIO DRUGI",
            "Član 4.\nČetvrta.",
        ]
    )

    paths = [
        [heading.label for heading in article.structure_path]
        for article in parse(text).law.articles
    ]

    assert paths == [
        ["DIO PRVI", "GLAVA I", "ODJELJAK A"],
        ["DIO PRVI", "GLAVA I", "ODJELJAK B"],
        ["DIO PRVI", "GLAVA II"],
        ["DIO DRUGI"],
    ]


def test_structure_heading_ends_previous_article() -> None:
    articles = parse("Član 1.\nPrva.\n\nGLAVA II\n\nČlan 2.\nDruga.").law.articles

    assert articles[0].text == "Član 1.\nPrva."


def test_preamble_stops_at_first_structure_heading() -> None:
    law = parse(f"Izmišljeni uvod.\n\nGLAVA I\n\n{ARTICLE}").law

    assert law.preamble == "Izmišljeni uvod."


def test_preamble_stops_at_first_article() -> None:
    assert parse(f"Izmišljeni uvod.\n\n{ARTICLE}").law.preamble == "Izmišljeni uvod."


@pytest.mark.parametrize(
    "closing",
    [
        "Broj: 01-02/30",
        "Број: 01-02/30",
        "Br. 01-02/30",
        "Бр. 01-02/30",
        "Predsjedavajući\nFiktivne skupštine",
        "Predsjednik\nFiktivne skupštine",
        "Председавајући\nФиктивне скупштине",
        "Предсједник\nФиктивне скупштине",
        "Sarajevo, 1. 2. 2030.",
        "Сарајево, 1. 2. 2030.",
    ],
)
def test_closing_block_stays_out_of_last_article(closing: str) -> None:
    law = parse(f"{ARTICLE}\n\n{closing}\n").law

    assert law.closing_text == closing
    assert law.articles[-1].text == ARTICLE
    assert len(law.articles[-1].paragraphs) == 1


def test_closing_block_follows_directly_after_body() -> None:
    law = parse(f"{ARTICLE}\nBroj: 01-02/30").law

    assert law.closing_text == "Broj: 01-02/30"
    assert law.articles[-1].text == ARTICLE


@pytest.mark.parametrize(
    "line",
    [
        "Predsjednik izmišljenog vijeća imenuje članove.",
        "br. 5 izmišljenog registra vodi se posebno.",
    ],
)
def test_sentences_resembling_closing_lines_stay_in_last_article(line: str) -> None:
    law = parse(f"{ARTICLE}\n\n{line}").law

    assert law.closing_text == ""
    assert line in law.articles[-1].text


def test_closing_marker_in_earlier_article_is_not_closing_text() -> None:
    law = parse("Član 1.\nBroj: 7 je izmišljen.\n\nČlan 2.\nDruga.").law

    assert law.closing_text == ""
    assert "Broj: 7 je izmišljen." in law.articles[0].text
