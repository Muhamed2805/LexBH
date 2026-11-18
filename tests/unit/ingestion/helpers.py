"""Shared helpers for parser tests. All legal text in these tests is fictional."""

from pathlib import Path

from lexbh.ingestion import Article, Jurisdiction, LawMetadata, ParseResult, parse_law

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "laws"
LATIN_FIXTURE = FIXTURES / "fictional_law_latin.txt"
CYRILLIC_FIXTURE = FIXTURES / "fictional_law_cyrillic.txt"

METADATA = LawMetadata(
    law_id="fiktivni-zakon",
    title="Fiktivni zakon, izmišljen za testove",
    jurisdiction=Jurisdiction.BIH,
)


def parse(text: str) -> ParseResult:
    return parse_law(text, METADATA)


def parse_fixture(path: Path) -> ParseResult:
    return parse(path.read_text(encoding="utf-8"))


def single_article(text: str) -> Article:
    articles = parse(text).law.articles
    assert len(articles) == 1
    return articles[0]
