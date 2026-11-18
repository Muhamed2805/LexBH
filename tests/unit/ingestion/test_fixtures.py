"""End-to-end tests over the fictional law fixtures."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from lexbh.ingestion import Jurisdiction, LawMetadata, ParsedLaw, PointKind, StructureKind
from tests.unit.ingestion.helpers import (
    CYRILLIC_FIXTURE,
    LATIN_FIXTURE,
    METADATA,
    parse,
    parse_fixture,
)

FIXTURES = [LATIN_FIXTURE, CYRILLIC_FIXTURE]


def element_ids(law: ParsedLaw) -> list[str]:
    ids: list[str] = []
    for article in law.articles:
        ids.append(article.id)
        for paragraph in article.paragraphs:
            ids.append(paragraph.id)
            ids.extend(point.id for point in paragraph.points)
    return ids


@pytest.mark.parametrize("path", FIXTURES)
def test_fixture_is_marked_as_fictional(path: Path) -> None:
    first_line = path.read_text(encoding="utf-8").splitlines()[0].lower()

    assert "fiktivni tekst" in first_line or "фиктивни текст" in first_line
    assert "nije stvarni zakon" in first_line or "није стварни закон" in first_line


@pytest.mark.parametrize("path", FIXTURES)
def test_fixture_parses_without_diagnostics(path: Path) -> None:
    assert parse_fixture(path).diagnostics == ()


@pytest.mark.parametrize("path", FIXTURES)
def test_fixture_covers_required_features(path: Path) -> None:
    law = parse_fixture(path).law
    paragraphs = [item for article in law.articles for item in article.paragraphs]
    points = [item for paragraph in paragraphs for item in paragraph.points]
    kinds = {heading.kind for article in law.articles for heading in article.structure_path}

    assert law.preamble
    assert law.closing_text
    assert kinds == set(StructureKind)
    assert {point.kind for point in points} == set(PointKind)
    assert {paragraph.number is None for paragraph in paragraphs} == {True, False}
    assert {"a", "b"} <= {article.suffix for article in law.articles}


def test_latin_and_cyrillic_fixtures_produce_the_same_ids() -> None:
    latin = parse_fixture(LATIN_FIXTURE).law
    cyrillic = parse_fixture(CYRILLIC_FIXTURE).law

    assert element_ids(latin) == element_ids(cyrillic)
    assert [article.label for article in latin.articles] == [
        article.label for article in cyrillic.articles
    ]
    assert [[item.kind for item in article.structure_path] for article in latin.articles] == [
        [item.kind for item in article.structure_path] for article in cyrillic.articles
    ]


@pytest.mark.parametrize("path", FIXTURES)
def test_element_ids_are_unique(path: Path) -> None:
    ids = element_ids(parse_fixture(path).law)

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("path", FIXTURES)
def test_offset_invariant_holds_for_every_element(path: Path) -> None:
    law = parse_fixture(path).law
    source = law.source_text

    for article in law.articles:
        assert article.text == source[article.start : article.end]
        assert article.text == article.text.strip()
        for heading in article.structure_path:
            span = source[heading.start : heading.end]
            assert span.startswith(heading.label)
            assert heading.title is None or span.endswith(heading.title)
        for paragraph in article.paragraphs:
            span = source[paragraph.start : paragraph.end]
            assert article.start <= paragraph.start <= paragraph.end <= article.end
            assert span.endswith(paragraph.text)
            for point in paragraph.points:
                point_span = source[point.start : point.end]
                assert paragraph.start <= point.start <= point.end <= paragraph.end
                assert point.text
                assert point_span.endswith(point.text)


@pytest.mark.parametrize("path", FIXTURES)
def test_crlf_input_matches_lf_input(path: Path) -> None:
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")

    assert parse(text.replace("\n", "\r\n")) == parse(text)
    assert parse(text.replace("\n", "\r")) == parse(text)


@pytest.mark.parametrize("path", FIXTURES)
def test_repeated_parsing_returns_equal_results(path: Path) -> None:
    assert parse_fixture(path) == parse_fixture(path)


@pytest.mark.parametrize("path", FIXTURES)
def test_closing_block_stays_out_of_last_fixture_article(path: Path) -> None:
    law = parse_fixture(path).law
    last = law.articles[-1]

    assert last.number == 14
    assert len(last.paragraphs) == 1
    assert law.source_text.rstrip().endswith(law.closing_text)
    assert law.source_text[last.end :].strip() == law.closing_text


def test_metadata_is_passed_through_unchanged() -> None:
    assert parse_fixture(LATIN_FIXTURE).law.metadata == METADATA


@pytest.mark.parametrize("law_id", ["Zakon", "zakon o zvonima", "-zakon", "zakon-", ""])
def test_law_id_must_be_a_lowercase_slug(law_id: str) -> None:
    with pytest.raises(ValidationError):
        LawMetadata(law_id=law_id, title="Fiktivni zakon", jurisdiction=Jurisdiction.RS)


def test_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        METADATA.title = "Promijenjen fiktivni naslov"  # type: ignore[misc]
