"""Inspect how the parser reads a local law text file. This tool only reads its input."""

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from itertools import pairwise
from pathlib import Path
from typing import NoReturn, TextIO

from pydantic import ValidationError

from lexbh.ingestion.models import (
    Article,
    DiagnosticCode,
    DiagnosticSeverity,
    Jurisdiction,
    LawMetadata,
    LawParseError,
    ParsedLaw,
    ParseResult,
    PointKind,
    StructureKind,
)
from lexbh.ingestion.normalize import normalize_text
from lexbh.ingestion.parser import parse_law

_EXIT_CLEAN = 0
_EXIT_FINDINGS = 1
_EXIT_FAILURE = 2

_REPLACEMENT_CHARACTER = chr(0xFFFD)
_MAX_EXCERPT_LENGTH = 100
_LONGEST_ARTICLE_COUNT = 5
_MAX_LISTED_GAPS = 20
_NO_VALUE = "-"


class _CliError(Exception):
    """A failure that ends the run with exit code 2."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _CliError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m lexbh.ingestion.cli",
        description="Show how the LexBH parser reads a law text file.",
        allow_abbrev=False,
    )
    parser.add_argument("path", type=Path, help="text file to inspect")
    parser.add_argument("--law-id", required=True, help="lowercase slug of the law")
    parser.add_argument("--title", required=True, help="official title of the law")
    parser.add_argument(
        "--jurisdiction",
        required=True,
        choices=[jurisdiction.value for jurisdiction in Jurisdiction],
        help="jurisdiction of the law",
    )
    parser.add_argument(
        "--encoding", default="utf-8-sig", help="Python codec name (default: utf-8-sig)"
    )
    parser.add_argument("--articles", action="store_true", help="add a document outline")
    return parser


def _write(stream: TextIO, text: str) -> None:
    """Write text, escaping every character that the stream cannot encode."""
    encoding = stream.encoding or "utf-8"
    stream.write(text.encode(encoding, "backslashreplace").decode(encoding))


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _build_metadata(law_id: str, title: str, jurisdiction: str) -> LawMetadata:
    try:
        return LawMetadata(law_id=law_id, title=title, jurisdiction=Jurisdiction(jurisdiction))
    except ValidationError as error:
        problems = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        ]
        raise _CliError(f"invalid metadata: {'; '.join(problems)}") from error


def _read_text(path: Path, encoding: str) -> str:
    try:
        raw = path.read_bytes()
    except (OSError, ValueError) as error:
        raise _CliError(f"cannot read {path}: {error}") from error
    try:
        text = raw.decode(encoding)
    except UnicodeError as error:
        raise _CliError(
            f"cannot decode {path} as {encoding}: {error}; try --encoding cp1250"
        ) from error
    except (LookupError, ValueError) as error:
        raise _CliError(f"cannot read {path}: unknown encoding {encoding!r}") from error

    normalized = normalize_text(text)
    position = normalized.find(_REPLACEMENT_CHARACTER)
    if position >= 0:
        line = normalized.count("\n", 0, position) + 1
        raise _CliError(f"{path} contains U+FFFD at line {line}; the text is already damaged")
    return text


def _count_lines(source: str) -> int:
    return source.count("\n") + (1 if source and not source.endswith("\n") else 0)


def _count_non_whitespace(text: str) -> int:
    return sum(not character.isspace() for character in text)


def _count_points(article: Article) -> int:
    return sum(len(paragraph.points) for paragraph in article.paragraphs)


def _count_assigned(law: ParsedLaw) -> int:
    """Measure the spans themselves, so that a coverage gap in the parser stays visible."""
    source = law.source_text
    spans = [(0, law.preamble_end), (law.closing_start, len(source))]
    spans.extend((heading.start, heading.end) for heading in law.structure_headings)
    spans.extend((article.start, article.end) for article in law.articles)
    assigned = bytearray(len(source))
    for start, end in spans:
        assigned[start:end] = b"\x01" * (end - start)
    return sum(
        bool(flag) and not character.isspace()
        for flag, character in zip(assigned, source, strict=True)
    )


def _percentage(part: int, whole: int) -> str:
    """Round down, so that 100.00% always means complete coverage."""
    hundredths = part * 10_000 // whole
    return f"{hundredths // 100}.{hundredths % 100:02d}%"


def _excerpt(source: str, offset: int) -> str:
    return _one_line(source[offset : offset + _MAX_EXCERPT_LENGTH])


def _section(title: str, rows: Iterable[str]) -> list[str]:
    return [title, *(f"  {row}" for row in rows), ""]


def _joined_or_none(values: Iterable[object]) -> str:
    return ", ".join(str(value) for value in values) or "none"


def _file_section(path: Path, encoding: str, source: str) -> list[str]:
    return _section(
        "File",
        [
            f"path: {path}",
            f"encoding: {encoding}",
            f"characters: {len(source)}",
            f"lines: {_count_lines(source)}",
        ],
    )


def _format_missing_numbers(numbers: set[int]) -> str:
    """Describe the gaps between article numbers without expanding them."""
    gaps = [(low + 1, high - 1) for low, high in pairwise(sorted(numbers)) if high - low > 1]
    if not gaps:
        return "none"
    total = sum(last - first + 1 for first, last in gaps)
    listed = [
        str(first) if first == last else f"{first}-{last}"
        for first, last in gaps[:_MAX_LISTED_GAPS]
    ]
    hidden = len(gaps) - len(listed)
    if hidden:
        listed.append(f"+{hidden} more gaps")
    return f"{', '.join(listed)} ({total} total)"


def _articles_section(law: ParsedLaw) -> list[str]:
    articles = law.articles
    missing = _format_missing_numbers({article.number for article in articles})
    suffixed = [article.label for article in articles if article.suffix is not None]
    titled = sum(article.title is not None for article in articles)
    return _section(
        "Articles",
        [
            f"count: {len(articles)}",
            f"first: {articles[0].label}",
            f"last: {articles[-1].label}",
            f"missing numbers: {missing}",
            f"suffixed: {_joined_or_none(suffixed)}",
            f"with title: {titled}",
        ],
    )


def _paragraphs_section(law: ParsedLaw) -> list[str]:
    paragraphs = [item for article in law.articles for item in article.paragraphs]
    numbered = sum(paragraph.number is not None for paragraph in paragraphs)
    return _section(
        "Paragraphs",
        [f"numbered: {numbered}", f"unnumbered: {len(paragraphs) - numbered}"],
    )


def _points_section(law: ParsedLaw) -> list[str]:
    counts = Counter(
        point.kind
        for article in law.articles
        for paragraph in article.paragraphs
        for point in paragraph.points
    )
    return _section("Points", [f"{kind.value}: {counts[kind]}" for kind in PointKind])


def _structure_section(law: ParsedLaw) -> list[str]:
    counts = Counter(heading.kind for heading in law.structure_headings)
    return _section(
        "Structure headings", [f"{kind.value}: {counts[kind]}" for kind in StructureKind]
    )


def _coverage_section(law: ParsedLaw) -> list[str]:
    unassigned = sum(_count_non_whitespace(span.text) for span in law.unassigned)
    total = _count_non_whitespace(law.source_text)
    return _section(
        "Coverage",
        [
            f"preamble characters: {len(law.preamble)}",
            f"closing characters: {len(law.closing_text)}",
            f"unassigned spans: {len(law.unassigned)}",
            f"unassigned non-whitespace characters: {unassigned}",
            f"assigned non-whitespace characters: {_percentage(_count_assigned(law), total)}",
        ],
    )


def _diagnostics_section(result: ParseResult) -> list[str]:
    counts = Counter(item.code for item in result.diagnostics)
    rows = [f"{code.value}: {counts[code]}" for code in DiagnosticCode]
    source = result.law.source_text
    rows.extend(
        f"{item.severity.value} {item.code.value} line {item.line}: {item.message}"
        f" | {_excerpt(source, item.offset)}"
        for item in result.diagnostics
    )
    return _section("Diagnostics", rows)


def _article_measures(article: Article) -> str:
    return (
        f"paragraphs: {len(article.paragraphs)}, points: {_count_points(article)}, "
        f"characters: {len(article.text)}"
    )


def _longest_section(law: ParsedLaw) -> list[str]:
    longest = sorted(law.articles, key=lambda article: len(article.text), reverse=True)
    return _section(
        "Longest articles",
        [
            f"{article.label} | {_article_measures(article)}"
            for article in longest[:_LONGEST_ARTICLE_COUNT]
        ],
    )


def _outline_section(law: ParsedLaw) -> list[str]:
    rows = [
        (
            heading.start,
            f"[{heading.kind.value}] {heading.label or _NO_VALUE} | {heading.title or _NO_VALUE}",
        )
        for heading in law.structure_headings
    ]
    rows.extend(
        (
            article.start,
            f"{article.label} | {article.title or _NO_VALUE} | {_article_measures(article)}",
        )
        for article in law.articles
    )
    return _section("Outline", [row for _, row in sorted(rows, key=lambda item: item[0])])


def _render_report(result: ParseResult, path: Path, encoding: str, *, outline: bool) -> str:
    law = result.law
    lines = [
        *_file_section(path, encoding, law.source_text),
        *_articles_section(law),
        *_paragraphs_section(law),
        *_points_section(law),
        *_structure_section(law),
        *_coverage_section(law),
        *_diagnostics_section(result),
        *_longest_section(law),
    ]
    if outline:
        lines.extend(_outline_section(law))
    return "\n".join(lines).rstrip("\n") + "\n"


def _inspect(args: argparse.Namespace) -> int:
    metadata = _build_metadata(args.law_id, args.title, args.jurisdiction)
    text = _read_text(args.path, args.encoding)
    try:
        result = parse_law(text, metadata)
    except LawParseError as error:
        raise _CliError(f"cannot parse {args.path}: {error}") from error

    report = _render_report(result, args.path, args.encoding, outline=args.articles)
    _write(sys.stdout, report)
    has_error = any(item.severity is DiagnosticSeverity.ERROR for item in result.diagnostics)
    return _EXIT_FINDINGS if has_error or result.law.unassigned else _EXIT_CLEAN


def main(argv: Sequence[str] | None = None) -> int:
    """Run the inspection and return the process exit code."""
    try:
        return _inspect(_build_parser().parse_args(argv))
    except _CliError as error:
        _write(sys.stderr, f"error: {_one_line(str(error))}\n")
        return _EXIT_FAILURE
    except SystemExit:  # Raised by argparse only after it has printed --help.
        return _EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
