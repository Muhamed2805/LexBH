"""Tests for article heading recognition. All legal text is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import LawParseError
from tests.unit.ingestion.helpers import parse, single_article

BODY = "Izmišljena odredba."


@pytest.mark.parametrize(
    ("heading", "number", "suffix"),
    [
        ("Član 5", 5, None),
        ("Član 5.", 5, None),
        ("Član 5a", 5, "a"),
        ("Član 5a.", 5, "a"),
        ("Član 5.a", 5, "a"),
        ("Član 5 a", 5, "a"),
        ("Član 5-a", 5, "a"),
        ("Clan 5.", 5, None),
        ("Članak 5.", 5, None),
        ("Clanak 5.", 5, None),
        ("Члан 5.", 5, None),
        ("Чланак 5.", 5, None),
        ("Члан 5а", 5, "a"),
        ("Члан 12а", 12, "a"),
        ("Члан 12б.", 12, "b"),
        ("ČLAN 5.", 5, None),
        ("član 5.", 5, None),
        ("ČLANAK 5.", 5, None),
        ("CLAN 5.", 5, None),
        ("ЧЛАН 5.", 5, None),
        ("чланак 5.", 5, None),
        ("Član 5A.", 5, "a"),
    ],
)
def test_recognizes_heading_forms(heading: str, number: int, suffix: str | None) -> None:
    article = single_article(f"{heading}\n{BODY}")

    assert article.number == number
    assert article.suffix == suffix
    assert article.label == f"Član {number}{suffix or ''}"
    assert article.id == f"fiktivni-zakon:cl-{number}{suffix or ''}"
    assert article.paragraphs[0].text == BODY


def test_canonicalizes_cyrillic_suffix_to_latin() -> None:
    article = single_article("Члан 12а\nИзмишљена одредба.")

    assert (article.number, article.suffix, article.label) == (12, "a", "Član 12a")
    assert article.id == "fiktivni-zakon:cl-12a"


@pytest.mark.parametrize(
    ("heading", "suffix"),
    [("Члан 5в", "v"), ("Члан 5ж", "ž"), ("Члан 5љ", "lj"), ("Члан 5џ", "dž")],
)
def test_transliterates_every_cyrillic_suffix(heading: str, suffix: str) -> None:
    assert single_article(f"{heading}\n{BODY}").suffix == suffix


def test_reads_title_on_heading_line() -> None:
    article = single_article(f"Član 5. (Izmišljeni naslov)\n{BODY}")

    assert article.title == "Izmišljeni naslov"
    assert article.paragraphs[0].text == BODY


def test_reads_title_on_next_line() -> None:
    article = single_article(f"Član 5.\n(Izmišljeni naslov)\n{BODY}")

    assert article.title == "Izmišljeni naslov"
    assert len(article.paragraphs) == 1


def test_reads_short_title_on_line_above() -> None:
    text = f"Izmišljeni naslov\nČlan 1.\n{BODY}"

    article = single_article(text)

    assert article.title == "Izmišljeni naslov"
    assert article.text.startswith("Izmišljeni naslov\nČlan 1.")


@pytest.mark.parametrize(
    "line_above",
    [
        "Izmišljena rečenica sa tačkom.",
        "x" * 81,
        "(1) Izmišljeni stav",
        "a) izmišljena tačka",
        "- izmišljena alineja",
        "GLAVA I",
    ],
)
def test_rejects_invalid_title_above(line_above: str) -> None:
    articles = parse(f"Član 1.\nPrva odredba.\n\n{line_above}\nČlan 2.\n{BODY}").law.articles

    assert articles[1].title is None


def test_body_text_directly_above_heading_is_not_a_title() -> None:
    text = f"Član 1.\nPrva odredba koja se\nnastavlja bez interpunkcije\nČlan 2.\n{BODY}"

    articles = parse(text).law.articles

    assert articles[1].title is None
    assert articles[0].text.endswith("nastavlja bez interpunkcije")


@pytest.mark.parametrize(
    "line",
    [
        "Član 5. ovog zakona primjenjuje se na sve obveznike.",
        "„Član 5.",
        '"Član 5."',
    ],
)
def test_false_positive_headings_stay_in_body(line: str) -> None:
    article = single_article(f"Član 1.\nPrva odredba.\n{line}\nDruga odredba.")

    assert article.number == 1
    assert line in article.paragraphs[0].text


def test_raises_when_no_article_exists() -> None:
    with pytest.raises(LawParseError):
        parse("Izmišljeni tekst bez ijednog člana.")


def test_raises_on_empty_text() -> None:
    with pytest.raises(LawParseError):
        parse("")
