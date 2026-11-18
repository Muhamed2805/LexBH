"""Deterministic parser for the plain text of laws of Bosnia and Herzegovina.

The parser performs no I/O. It raises ``LawParseError`` only when no article exists and reports
every other problem as a diagnostic. When a line is ambiguous, the parser prefers leaving it in
the surrounding text over inventing a heading, because wrong structure leads to wrong citations.
"""

# ruff: noqa: RUF001

import re
from collections import Counter
from dataclasses import dataclass, replace

from lexbh.ingestion.models import (
    Article,
    ArticleParagraph,
    ArticlePoint,
    DiagnosticCode,
    DiagnosticSeverity,
    LawMetadata,
    LawParseError,
    ParseDiagnostic,
    ParsedLaw,
    ParseResult,
    PointKind,
    StructureHeading,
    StructureKind,
    UnassignedSpan,
)
from lexbh.ingestion.normalize import normalize_text

_CYRILLIC_LETTERS = "абвгдђежзијклљмнњопрстћуфхцчџш"
_LATIN_EQUIVALENTS = (
    "a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š".split()  # noqa: SIM905
)
_CYRILLIC_TO_LATIN = dict(zip(_CYRILLIC_LETTERS, _LATIN_EQUIVALENTS, strict=True))
_LATIN_ORDER = (
    "a b c č ć d dž đ e f g h i j k l lj m n nj o p q r s š t u v w x y z ž".split()  # noqa: SIM905
)
_LETTER = rf"(?:dž|lj|nj|[a-zčćđšž]|[{_CYRILLIC_LETTERS}])"
_LETTER_RE = re.compile(_LETTER, re.IGNORECASE)
_NOT_A_LETTER_NEXT = r"(?![^\W\d_])"

_ARTICLE_BASE = r"^(?:član(?:ak)?|clan(?:ak)?|члан(?:ак)?)\s+(?P<number>[0-9]+)"
_ARTICLE_BASE_RE = re.compile(_ARTICLE_BASE, re.IGNORECASE)
_ARTICLE_SUFFIX_RE = re.compile(
    _ARTICLE_BASE + rf"(?:(?P<attached>{_LETTER}{{1,3}})|\s*[.\-–]?\s*(?P<separated>{_LETTER}))"
    rf"{_NOT_A_LETTER_NEXT}",
    re.IGNORECASE,
)
_SEPARATED_CONJUNCTIONS = frozenset({"i", "и"})
_BARE_TAIL_RE = re.compile(r"^\s*\.?\s*$")
_PARAGRAPH_TAIL_RE = re.compile(r"^\s*\.?\s*(?=\([0-9]{1,3}\))")
_PARENTHESIZED_TAIL_RE = re.compile(r"^\s*\.?\s*\((?P<title>.+)\)$")
_INLINE_TAIL_RE = re.compile(r"^(?:\s*\.\s*(?:[-–—]\s+)?|\s*:\s*|\s+[-–—]\s+)(?P<title>\S.*)$")

_PARAGRAPH_RE = re.compile(r"^\(([0-9]{1,3})\)\s*")
_NUMBER_POINT_RE = re.compile(r"^([0-9]{1,3})\.?\)(?:\s+|$)")
_DOTTED_NUMBER_RE = re.compile(r"^([0-9]{1,3})\.\s+(?=\S)")
_LETTER_POINT_RE = re.compile(
    rf"^(?:\((?P<wrapped>{_LETTER})\)|(?P<plain>{_LETTER})\))(?:\s+|$)", re.IGNORECASE
)
_DASHES = "-–—−•·"
_DASH_POINT_RE = re.compile(rf"^[{_DASHES}](?:\s+|$)")
_TIGHT_DASH_RE = re.compile(rf"^[{_DASHES}](?=\S)")

_LATIN_ORDINAL_WORDS = (
    "PRV DRUG TREĆ TREC ČETVRT CETVRT PET ŠEST SEST SEDM OSM DEVET DESET JEDANAEST DVANAEST "
    "TRINAEST ČETRNAEST CETRNAEST PETNAEST ŠESNAEST SESNAEST SEDAMNAEST OSAMNAEST DEVETNAEST "
    "DVADESET"
)
_CYRILLIC_ORDINAL_WORDS = (
    "ПРВ ДРУГ ТРЕЋ ЧЕТВРТ ПЕТ ШЕСТ СЕДМ ОСМ ДЕВЕТ ДЕСЕТ ЈЕДАНАЕСТ ДВАНАЕСТ ТРИНАЕСТ ЧЕТРНАЕСТ "
    "ПЕТНАЕСТ ШЕСНАЕСТ СЕДАМНАЕСТ ОСАМНАЕСТ ДЕВЕТНАЕСТ ДВАДЕСЕТ"
)
_LATIN_ORDINAL_STEMS = _LATIN_ORDINAL_WORDS.split()
_CYRILLIC_ORDINAL_STEMS = _CYRILLIC_ORDINAL_WORDS.split()
_SOFT_ORDINAL_STEMS = frozenset({"TREĆ", "TREC", "ТРЕЋ"})


def _ordinal_forms(latin: str, cyrillic: str, soft_latin: str, soft_cyrillic: str) -> list[str]:
    forms = [
        stem + (soft_latin if stem in _SOFT_ORDINAL_STEMS else latin)
        for stem in _LATIN_ORDINAL_STEMS
    ]
    forms.extend(
        stem + (soft_cyrillic if stem in _SOFT_ORDINAL_STEMS else cyrillic)
        for stem in _CYRILLIC_ORDINAL_STEMS
    )
    return forms


_MASCULINE_ORDINALS = _ordinal_forms("I", "И", "I", "И")
_FEMININE_ORDINALS = _ordinal_forms("A", "А", "A", "А")
_NEUTER_ORDINALS = _ordinal_forms("O", "О", "E", "Е")

_ROMAN = "[IVXLCDMІХ]+"
_CHAPTER_NUMERAL = rf"{_ROMAN}|[0-9]+"
_SECTION_NUMERAL = "[A-ZČĆĐŠŽ]|[А-ШЂЈЉЊЋЏ]|[0-9]+"
_TITLE_TAIL = r"\.?(?:\s*[.:–—-]?\s*(?P<title>\S.*))?$"
_STRUCTURE_LEVELS = (
    StructureKind.PART,
    StructureKind.DIVISION,
    StructureKind.CHAPTER,
    StructureKind.SECTION,
)


@dataclass(frozen=True, slots=True)
class _StructurePattern:
    kind: StructureKind
    pattern: re.Pattern[str]
    title_case: bool


def _either(words: list[str]) -> str:
    return "|".join(words)


def _capitalized(words: list[str]) -> list[str]:
    return [word.capitalize() for word in words]


def _any_case(words: list[str]) -> list[str]:
    return [form for word in words for form in (word.capitalize(), word.lower())]


def _keyword_patterns(
    kind: StructureKind, keywords: list[str], ordinals: list[str], numeral: str
) -> list[_StructurePattern]:
    upper = rf"(?:{_either(keywords)})\s+(?:{_either(ordinals)}|{numeral})"
    title = rf"(?:{_either(_capitalized(keywords))})\s+(?:{_either(_any_case(ordinals))}|{numeral})"
    return [
        _StructurePattern(kind, re.compile(rf"^(?P<label>{upper})\b{_TITLE_TAIL}"), False),
        _StructurePattern(kind, re.compile(rf"^(?P<label>{title})\b{_TITLE_TAIL}"), True),
    ]


def _leading_part_patterns() -> list[_StructurePattern]:
    keywords = ["DIO", "ДИО"]
    upper = rf"(?:{_either(_MASCULINE_ORDINALS)}|{_ROMAN})\.?\s+(?:{_either(keywords)})"
    title = (
        rf"(?:{_either(_any_case(_MASCULINE_ORDINALS))}|{_ROMAN})\.?\s+"
        rf"(?:{_either(_any_case(keywords))})"
    )
    return [
        _StructurePattern(
            StructureKind.PART, re.compile(rf"^(?P<label>{upper})\b{_TITLE_TAIL}"), False
        ),
        _StructurePattern(
            StructureKind.PART, re.compile(rf"^(?P<label>{title})\b{_TITLE_TAIL}"), True
        ),
    ]


_STRUCTURE_PATTERNS = (
    *_keyword_patterns(StructureKind.PART, ["DIO", "ДИО"], _MASCULINE_ORDINALS, _ROMAN),
    *_leading_part_patterns(),
    *_keyword_patterns(
        StructureKind.CHAPTER, ["GLAVA", "ГЛАВА"], _FEMININE_ORDINALS, _CHAPTER_NUMERAL
    ),
    *_keyword_patterns(
        StructureKind.CHAPTER, ["POGLAVLJE", "ПОГЛАВЉЕ"], _NEUTER_ORDINALS, _CHAPTER_NUMERAL
    ),
    *_keyword_patterns(
        StructureKind.SECTION, ["ODJELJAK", "ОДЈЕЉАК"], _MASCULINE_ORDINALS, _SECTION_NUMERAL
    ),
)
_ROMAN_DIVISION_RE = re.compile(r"^(?P<label>[IVXІХ]+)(?:\.\s*|\s*[-–—]\s*|\s+)(?P<title>\S.*)$")
_SMALL_ROMAN_RE = re.compile(r"X{0,3}(?:IX|IV|V?I{0,3})")
_ROMAN_LOOKALIKES = str.maketrans({"І": "I", "Х": "X"})
_LAW_TITLE_PREFIXES = ("ZAKON", "ЗАКОН")

_DATE = r"[0-9]{1,2}\.\s*(?:[0-9]{1,2}\.|[^\W\d_]+)\s*[0-9]{4}\.?"
_NUMBER_VALUE_RE = re.compile(r"^(?:broj|број)\s*:\s*(?P<value>.*)$", re.IGNORECASE)
_DATE_IN_VALUE_RE = re.compile(_DATE)
_VALUE_WORD_RE = re.compile(r"[^\W\d_]+")
_NUMBER_VALUE_WORDS = frozenset({"od", "dana", "godine", "god", "од", "дана", "године", "год"})
_SHORT_NUMBER_RE = re.compile(r"^(?:br|бр)\.\s*\S*[0-9]\S*$", re.IGNORECASE)
_ASSEMBLY_NUMBER_RE = re.compile(
    r"^(?P<body>[^\W\d_]+)(?:\s+[^\W\d_]+){0,2}\s+(?:broj|број)\s+\S*[0-9]\S*$", re.IGNORECASE
)
_SIGNATORY_RE = re.compile(
    r"^(?:predsjedavajuć[ia]|predsjednik|predsjednica|"
    r"председавајућ[иа]|предсједавајућ[иа]|председник|председница|предсједник|предсједница)\b",
    re.IGNORECASE,
)
_PLACE_DATE_RE = re.compile(
    r"^[^\W\d_]+(?:[ -][^\W\d_]+){0,3},\s*(?:(?:dana|дана)\s+)?"
    rf"{_DATE}(?:\s*(?:godine|године)\.?)?$",
    re.IGNORECASE,
)
_DATE_LINE_RE = re.compile(
    rf"^(?:(?:dana|дана)\s+)?{_DATE}(?:\s*(?:godine|године)\.?)?$", re.IGNORECASE
)

_TERMINAL_PUNCTUATION = ".,:;!?"
_QUOTATION_MARKS = "\"'„“”«»‘’‚"
_QUOTE_CLOSERS = {"„": '“”"', "«": "»"}
_LINE_QUOTE_CLOSERS = {'"': '"', "“": "”", "»": "«"}
_QUOTE_EDGE_MARKS = '„“”«»"'
_BARE_LAW_TITLES = frozenset({"ZAKON", "ЗАКОН"})
_MAX_TITLE_ABOVE_LENGTH = 80
_MAX_TITLE_LENGTH = 120
_MAX_TITLE_ABOVE_LINES = 2
_MAX_TITLE_BELOW_LINES = 3
_MIN_TITLE_LETTERS = 2

_SEVERITIES = {
    DiagnosticCode.DUPLICATE_ARTICLE: DiagnosticSeverity.ERROR,
    DiagnosticCode.ARTICLE_NUMBER_GAP: DiagnosticSeverity.WARNING,
    DiagnosticCode.ARTICLE_OUT_OF_ORDER: DiagnosticSeverity.WARNING,
    DiagnosticCode.PARAGRAPH_NUMBER_GAP: DiagnosticSeverity.WARNING,
    DiagnosticCode.EMPTY_ARTICLE: DiagnosticSeverity.WARNING,
    DiagnosticCode.UNASSIGNED_TEXT: DiagnosticSeverity.WARNING,
    DiagnosticCode.UNTERMINATED_QUOTE: DiagnosticSeverity.WARNING,
    DiagnosticCode.QUOTED_HEADING: DiagnosticSeverity.WARNING,
}


@dataclass(frozen=True, slots=True)
class _Line:
    number: int
    start: int
    end: int
    content: str
    content_start: int
    quoted: bool = False
    heading_blocked: bool = False
    in_closed_quotation: bool = False

    @property
    def is_blank(self) -> bool:
        return not self.content


@dataclass(frozen=True, slots=True)
class _HeadingParts:
    number: int
    raw_suffix: str | None
    title: str | None
    has_inline_title: bool
    paragraph_column: int | None


@dataclass(frozen=True, slots=True)
class _ArticleDraft:
    number: int
    suffix: str | None
    suffix_rank: tuple[int, ...]
    title: str | None
    first_index: int
    heading_index: int
    body_index: int
    paragraph_column: int | None


@dataclass(frozen=True, slots=True)
class _StructureDraft:
    heading: StructureHeading
    first_index: int
    next_index: int


@dataclass(frozen=True, slots=True)
class _StructureParts:
    kind: StructureKind
    label: str
    title: str | None
    title_case: bool


@dataclass(frozen=True, slots=True)
class _PointMarker:
    kind: PointKind
    label: str
    length: int


@dataclass(slots=True)
class _ParagraphDraft:
    number: int | None
    lines: list[_Line]
    text_start: int


@dataclass(slots=True)
class _ScanState:
    law_title: str
    consumed_through: int = -1
    follows_structure: bool = False
    has_article: bool = False


_Event = _ArticleDraft | _StructureDraft
_PointGroup = tuple[_PointMarker, list[_Line]]


def parse_law(text: str, metadata: LawMetadata) -> ParseResult:
    """Parse the plain text of a law into structured articles and diagnostics."""
    source = normalize_text(text)
    lines, diagnostics = _mark_quotations(_split_lines(source))
    all_events = _scan(lines, metadata.title, diagnostics)
    drafts = [event for event in all_events if isinstance(event, _ArticleDraft)]
    if not drafts:
        raise LawParseError("No article heading was found in the text.")

    closing_index = _find_closing(lines, drafts[-1].body_index)
    events = [event for event in all_events if event.first_index < closing_index]
    diagnostics.extend(_sequence_diagnostics(drafts, lines))
    article_ids = _article_ids(drafts, metadata.law_id)

    articles: list[Article] = []
    path: dict[StructureKind, StructureHeading] = {}
    for position, event in enumerate(events):
        if isinstance(event, _StructureDraft):
            _advance_path(path, event.heading)
            continue
        following = events[position + 1].first_index if position + 1 < len(events) else len(lines)
        article, article_diagnostics = _build_article(
            event,
            article_ids[len(articles)],
            tuple(path[kind] for kind in _STRUCTURE_LEVELS if kind in path),
            lines,
            min(following, closing_index),
            source,
        )
        articles.append(article)
        diagnostics.extend(article_diagnostics)

    unassigned, unassigned_diagnostics = _unassigned_spans(events, lines, closing_index, source)
    diagnostics.extend(unassigned_diagnostics)

    preamble_end = len(source[: lines[events[0].first_index].content_start].rstrip())
    closing_start = (
        lines[closing_index].content_start if closing_index < len(lines) else len(source)
    )
    law = ParsedLaw(
        metadata=metadata,
        source_text=source,
        preamble=source[:preamble_end].strip(),
        preamble_end=preamble_end,
        structure_headings=tuple(
            event.heading for event in events if isinstance(event, _StructureDraft)
        ),
        articles=tuple(articles),
        closing_text=source[closing_start:].strip(),
        closing_start=closing_start,
        unassigned=unassigned,
    )
    ordered = sorted(diagnostics, key=lambda item: (item.offset, item.code.value, item.message))
    return ParseResult(law=law, diagnostics=tuple(ordered))


def _split_lines(source: str) -> list[_Line]:
    lines: list[_Line] = []
    offset = 0
    for number, raw in enumerate(source.split("\n"), start=1):
        content = raw.lstrip()
        end = offset + len(raw)
        lines.append(_Line(number, offset, end, content, end - len(content)))
        offset = end + 1
    return lines


def _advance_quotes(content: str, column: int, stack: list[tuple[str, int]]) -> int | None:
    """Track open quotations and return the column where the outermost one closes."""
    for position in range(column, len(content)):
        character = content[position]
        if character in _QUOTE_CLOSERS:
            stack.append((character, position))
        elif stack and character in _QUOTE_CLOSERS[stack[-1][0]]:
            stack.pop()
            if not stack:
                return position
    return None


def _find_quote_close(
    lines: list[_Line], start: int, stack: list[tuple[str, int]]
) -> tuple[int, int] | None:
    for index in range(start, len(lines)):
        column = _advance_quotes(lines[index].content, 0, stack)
        if column is not None:
            return index, column
    return None


def _opens_line_quote(content: str) -> bool:
    """Report whether a quotation that opens at the line start stays open past this line."""
    opener = content[0]
    closer = _LINE_QUOTE_CLOSERS[opener]
    if opener == closer:
        return content.count(opener) % 2 == 1
    return content.count(opener) > content.count(closer)


def _find_line_close(lines: list[_Line], start: int, closer: str) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].content.endswith(closer):
            return index
    return None


def _is_fully_quoted(content: str) -> bool:
    closers = _QUOTE_CLOSERS.get(content[:1]) or _LINE_QUOTE_CLOSERS.get(content[:1])
    return closers is not None and len(content) > 1 and content[-1] in closers


def _mark_quotations(lines: list[_Line]) -> tuple[list[_Line], list[ParseDiagnostic]]:
    """Protect quoted lines. An unclosed quotation protects only its first line."""
    inside: set[int] = set()
    blocked: set[int] = set()
    closed: set[int] = set()
    diagnostics: list[ParseDiagnostic] = []

    def report_unterminated(index: int, column: int) -> None:
        blocked.add(index)
        if column == 0:
            inside.add(index)
        line = lines[index]
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNTERMINATED_QUOTE,
                "A quotation is opened here and never closed.",
                line,
                line.content_start + column,
            )
        )

    index = 0
    column = 0
    while index < len(lines):
        content = lines[index].content
        line_closer = _LINE_QUOTE_CLOSERS.get(content[:1]) if column == 0 else None
        if line_closer is not None and _opens_line_quote(content):
            line_close = _find_line_close(lines, index + 1, line_closer)
            if line_close is None:
                report_unterminated(index, 0)
                index += 1
            else:
                inside.update(range(index, line_close + 1))
                blocked.update(range(index, line_close + 1))
                closed.update(range(index, line_close + 1))
                index = line_close + 1
            continue
        if line_closer is not None and line_closer in content[1:]:
            column = content.rindex(line_closer) + 1
            continue

        stack: list[tuple[str, int]] = []
        closed_column = _advance_quotes(content, column, stack)
        if closed_column is not None:
            column = closed_column + 1
            continue
        if not stack:
            index += 1
            column = 0
            continue

        opener_column = stack[0][1]
        close = _find_quote_close(lines, index + 1, stack)
        if close is None:
            report_unterminated(index, opener_column)
            index += 1
            column = 0
            continue
        close_index, close_column = close
        blocked.update(range(index, close_index + 1))
        closed.update(range(index, close_index + 1))
        inside.update(range(index + 1, close_index + 1))
        if opener_column == 0:
            inside.add(index)
        index = close_index
        column = close_column + 1

    marked = [
        replace(
            line,
            quoted=position in inside,
            heading_blocked=position in blocked,
            in_closed_quotation=position in closed,
        )
        for position, line in enumerate(lines)
    ]
    return marked, diagnostics


def _is_quoted_heading(lines: list[_Line], index: int, state: _ScanState) -> bool:
    """Report whether a quoted line would be an article heading without its quotation."""
    line = lines[index]
    if not line.in_closed_quotation and not _is_fully_quoted(line.content):
        return False
    unquoted = line.content.strip(_QUOTE_EDGE_MARKS)
    return _accepted_heading(lines, index, state, unquoted) is not None


def _scan(lines: list[_Line], law_title: str, diagnostics: list[ParseDiagnostic]) -> list[_Event]:
    """Find every article and structure heading, in source order."""
    events: list[_Event] = []
    state = _ScanState(law_title=law_title)
    index = 0
    while index < len(lines):
        if _is_quoted_heading(lines, index, state):
            message = "An article heading inside a quotation was not treated as an article."
            diagnostics.append(_diagnostic(DiagnosticCode.QUOTED_HEADING, message, lines[index]))
        if lines[index].is_blank or lines[index].heading_blocked:
            index += 1
            continue
        article = _match_article(lines, index, state)
        if article is not None:
            events.append(article)
            index = article.body_index
            state.consumed_through = index - 1
            state.follows_structure = False
            state.has_article = True
            continue
        structure = _match_any_structure(lines, index, state)
        if structure is not None:
            events.append(structure)
            index = structure.next_index
            state.consumed_through = index - 1
            state.follows_structure = True
            continue
        index += 1
    return events


def _match_any_structure(
    lines: list[_Line], index: int, state: _ScanState
) -> _StructureDraft | None:
    return (
        _match_keyword_structure(lines, index, state)
        or _match_roman_division(lines, index, state)
        or _match_unnumbered_division(lines, index, state)
    )


def _previous_allows_heading(lines: list[_Line], index: int, state: _ScanState) -> bool:
    if index == 0:
        return True
    previous = lines[index - 1]
    if previous.is_blank or previous.content[-1] in _TERMINAL_PUNCTUATION:
        return True
    return index - 1 == state.consumed_through and state.follows_structure


def _next_starts_lowercase(lines: list[_Line], index: int) -> bool:
    for line in lines[index + 1 :]:
        if not line.is_blank:
            return line.content[0].islower()
    return False


def _accepted_heading(
    lines: list[_Line], index: int, state: _ScanState, content: str
) -> _HeadingParts | None:
    """Read a heading from the content of a line, if its surrounding lines allow one."""
    heading = _parse_heading(content)
    if heading is None:
        return None
    if content[0].islower() and index > 0 and not lines[index - 1].is_blank:
        return None
    needs_clear_start = heading.has_inline_title or heading.paragraph_column is not None
    if needs_clear_start and not _previous_allows_heading(lines, index, state):
        return None
    if heading.has_inline_title and _next_starts_lowercase(lines, index):
        return None
    return heading


def _match_article(lines: list[_Line], index: int, state: _ScanState) -> _ArticleDraft | None:
    heading = _accepted_heading(lines, index, state, lines[index].content)
    if heading is None:
        return None

    title = heading.title
    body_index = index + 1
    first_index = index
    if title is None and heading.paragraph_column is None:
        below = _title_below(lines, body_index)
        if below is not None:
            title, body_index = below
    if title is None:
        above = _title_above(lines, index, state)
        if above is not None:
            title, first_index = above

    raw_suffix = heading.raw_suffix
    return _ArticleDraft(
        number=heading.number,
        suffix=_canonical_suffix(raw_suffix) if raw_suffix else None,
        suffix_rank=_suffix_rank(raw_suffix) if raw_suffix else (),
        title=title,
        first_index=first_index,
        heading_index=index,
        body_index=body_index,
        paragraph_column=heading.paragraph_column,
    )


def _parse_heading(content: str) -> _HeadingParts | None:
    """Read an article heading line, trying a suffix first and then no suffix."""
    suffixed = _ARTICLE_SUFFIX_RE.match(content)
    if suffixed is not None:
        separated = suffixed["separated"]
        if separated is None or separated.lower() not in _SEPARATED_CONJUNCTIONS:
            raw_suffix = suffixed["attached"] or separated
            parts = _heading_tail(content, suffixed.end(), int(suffixed["number"]), raw_suffix)
            if parts is not None:
                return parts
    base = _ARTICLE_BASE_RE.match(content)
    if base is None:
        return None
    return _heading_tail(content, base.end(), int(base["number"]), None)


def _heading_tail(
    content: str, end: int, number: int, raw_suffix: str | None
) -> _HeadingParts | None:
    tail = content[end:]
    if _BARE_TAIL_RE.match(tail):
        return _HeadingParts(number, raw_suffix, None, False, None)

    paragraph = _PARAGRAPH_TAIL_RE.match(tail)
    if paragraph is not None:
        column = end + paragraph.end()
        marker = _PARAGRAPH_RE.match(content[column:])
        rest = content[column + marker.end() :] if marker is not None else ""
        if rest and rest[0].islower():
            return None
        return _HeadingParts(number, raw_suffix, None, False, column)

    parenthesized = _PARENTHESIZED_TAIL_RE.match(tail)
    if parenthesized is not None:
        inner = parenthesized["title"]
        if inner.strip() and _is_balanced(inner) and not _is_marker(f"({inner})"):
            return _HeadingParts(number, raw_suffix, inner.strip(), False, None)
        return None

    inline = _INLINE_TAIL_RE.match(tail)
    if inline is not None and _is_inline_title(inline["title"]):
        return _HeadingParts(number, raw_suffix, inline["title"], True, None)
    return None


def _is_inline_title(title: str) -> bool:
    return (
        title[0].isupper()
        and len(title) <= _MAX_TITLE_LENGTH
        and title[-1] not in _TERMINAL_PUNCTUATION
        and sum(character.isalpha() for character in title) >= _MIN_TITLE_LETTERS
    )


def _is_balanced(value: str) -> bool:
    depth = 0
    for character in value:
        depth += (character == "(") - (character == ")")
        if depth < 0:
            return False
    return depth == 0


def _title_below(lines: list[_Line], start: int) -> tuple[str, int] | None:
    """Read a parenthesized title of up to three lines, after any blank lines."""
    index = start
    while index < len(lines) and lines[index].is_blank:
        index += 1
    if index >= len(lines):
        return None
    first = lines[index]
    if first.heading_blocked or not first.content.startswith("(") or _is_marker(first.content):
        return None

    collected: list[str] = []
    for position in range(index, min(index + _MAX_TITLE_BELOW_LINES, len(lines))):
        line = lines[position]
        if line.is_blank or line.heading_blocked:
            return None
        if position > index and _is_marker(line.content):
            return None
        collected.append(line.content)
        joined = " ".join(collected)
        if joined.endswith(")") and _is_balanced(joined):
            inner = joined[1:-1].strip()
            is_title = (
                inner and _is_balanced(joined[1:-1]) and inner[-1] not in _TERMINAL_PUNCTUATION
            )
            return (inner, position + 1) if is_title else None
    return None


def _is_marker(content: str) -> bool:
    return _PARAGRAPH_RE.match(content) is not None or _point_marker(content) is not None


def _is_heading_like(content: str) -> bool:
    return (
        _parse_heading(content) is not None
        or _structure_parts(content) is not None
        or _division_parts(content) is not None
    )


def _is_title_line(line: _Line) -> bool:
    content = line.content
    return (
        not line.heading_blocked
        and len(content) <= _MAX_TITLE_ABOVE_LENGTH
        and content[-1] not in _TERMINAL_PUNCTUATION
        and content[0] not in _QUOTATION_MARKS
        and not _is_marker(content)
        and not _is_heading_like(content)
    )


def _is_law_title(content: str, law_title: str) -> bool:
    return content.startswith(_LAW_TITLE_PREFIXES) or content.casefold() == law_title.casefold()


def _continues_centered_title(lines: list[_Line], index: int, state: _ScanState) -> bool:
    """Report whether an uppercase line completes a law title that starts with a bare ZAKON."""
    if state.has_article or not _is_fully_uppercase(lines[index].content):
        return False
    for line in reversed(lines[:index]):
        if not line.is_blank:
            return line.content in _BARE_LAW_TITLES
    return False


def _title_above(
    lines: list[_Line], heading_index: int, state: _ScanState
) -> tuple[str, int] | None:
    """Read a title of one or two lines above a heading, across any blank lines."""
    floor = state.consumed_through
    last = heading_index - 1
    while last > floor and lines[last].is_blank:
        last -= 1
    if last <= floor:
        return None
    first = last
    while first - 1 > floor and not lines[first - 1].is_blank:
        first -= 1
    if last - first + 1 > _MAX_TITLE_ABOVE_LINES:
        return None

    boundary = first - 1
    follows_heading = boundary == floor and state.follows_structure
    if boundary >= 0 and not lines[boundary].is_blank and not follows_heading:
        return None

    if _continues_centered_title(lines, first, state):
        return None

    block = lines[first : last + 1]
    if not block[0].content[0].isupper() or not all(_is_title_line(line) for line in block):
        return None
    if not state.has_article and any(
        _is_law_title(line.content, state.law_title) for line in block
    ):
        return None
    return " ".join(line.content for line in block), first


def _structure_parts(content: str) -> _StructureParts | None:
    for candidate in _STRUCTURE_PATTERNS:
        match = candidate.pattern.match(content)
        if match is None:
            continue
        title = match["title"]
        if title is None:
            return _StructureParts(candidate.kind, match["label"], None, candidate.title_case)
        letters = [character for character in title if character.isalpha()]
        if letters and letters[0].isupper() and title[-1] not in _TERMINAL_PUNCTUATION:
            return _StructureParts(candidate.kind, match["label"], title, candidate.title_case)
    return None


def _is_fully_uppercase(content: str) -> bool:
    return any(character.isalpha() for character in content) and content == content.upper()


def _division_parts(content: str) -> tuple[str, str] | None:
    match = _ROMAN_DIVISION_RE.match(content)
    if match is None:
        return None
    numeral = match["label"].translate(_ROMAN_LOOKALIKES)
    title = match["title"]
    if (
        _SMALL_ROMAN_RE.fullmatch(numeral) is None
        or not _is_fully_uppercase(title)
        or title[-1] in _TERMINAL_PUNCTUATION
    ):
        return None
    return match["label"], title


def _match_keyword_structure(
    lines: list[_Line], index: int, state: _ScanState
) -> _StructureDraft | None:
    line = lines[index]
    parts = _structure_parts(line.content)
    if parts is None:
        return None
    if parts.title_case:
        if not _previous_allows_heading(lines, index, state):
            return None
        if parts.title is not None and _next_starts_lowercase(lines, index):
            return None

    title = parts.title
    end = line.end
    next_index = index + 1
    if title is None and next_index < len(lines):
        following = lines[next_index]
        is_title = _is_structure_title_below(following, parts.title_case)
        if is_title and not _is_closing_line(lines, next_index):
            title = following.content
            end = following.end
            next_index += 1
    heading = StructureHeading(
        kind=parts.kind, label=parts.label, title=title, start=line.content_start, end=end
    )
    return _StructureDraft(heading=heading, first_index=index, next_index=next_index)


def _is_structure_title_below(line: _Line, title_case: bool) -> bool:
    content = line.content
    if not content or line.heading_blocked or _is_marker(content) or _is_heading_like(content):
        return False
    if not title_case:
        return _is_fully_uppercase(content)
    return (
        content[0].isupper()
        and len(content) <= _MAX_TITLE_LENGTH
        and content[-1] not in _TERMINAL_PUNCTUATION
    )


def _match_roman_division(
    lines: list[_Line], index: int, state: _ScanState
) -> _StructureDraft | None:
    if index > 0 and not lines[index - 1].is_blank:
        return None
    if _continues_centered_title(lines, index, state):
        return None
    line = lines[index]
    parts = _division_parts(line.content)
    if parts is None:
        return None
    label, title = parts
    heading = StructureHeading(
        kind=StructureKind.DIVISION,
        label=label,
        title=title,
        start=line.content_start,
        end=line.end,
    )
    return _StructureDraft(heading=heading, first_index=index, next_index=index + 1)


def _match_unnumbered_division(
    lines: list[_Line], index: int, state: _ScanState
) -> _StructureDraft | None:
    if index > 0 and not lines[index - 1].is_blank:
        return None
    line = lines[index]
    content = line.content
    if (
        not _is_fully_uppercase(content)
        or sum(character.isalpha() for character in content) < _MIN_TITLE_LETTERS
        or len(content) > _MAX_TITLE_LENGTH
        or content[-1] in _TERMINAL_PUNCTUATION
        or content[0] in _QUOTATION_MARKS
        or _is_marker(content)
        or (not state.has_article and _is_law_title(content, state.law_title))
        or _continues_centered_title(lines, index, state)
        or not _precedes_article(lines, index + 1)
    ):
        return None
    heading = StructureHeading(
        kind=StructureKind.DIVISION,
        label="",
        title=content,
        start=line.content_start,
        end=line.end,
    )
    return _StructureDraft(heading=heading, first_index=index, next_index=index + 1)


def _precedes_article(lines: list[_Line], start: int) -> bool:
    """Report whether only an optional article title separates this line from a heading."""
    title_lines = 0
    for line in lines[start:]:
        if line.is_blank:
            continue
        if line.heading_blocked:
            return False
        if _parse_heading(line.content) is not None:
            return True
        title_lines += 1
        if title_lines > _MAX_TITLE_ABOVE_LINES or not _is_title_line(line):
            return False
    return False


def _advance_path(path: dict[StructureKind, StructureHeading], heading: StructureHeading) -> None:
    """Replace the heading at its level and clear every lower level."""
    level = _STRUCTURE_LEVELS.index(heading.kind)
    for kind in _STRUCTURE_LEVELS[level + 1 :]:
        path.pop(kind, None)
    path[heading.kind] = heading


def _find_closing(lines: list[_Line], start_index: int) -> int:
    for index in range(start_index, len(lines)):
        if _is_closing_line(lines, index):
            return index
    return len(lines)


def _is_number_value(value: str) -> bool:
    """Accept a registry number, and reject a sentence that happens to contain a digit."""
    if not any(character.isdigit() for character in value):
        return False
    words = _VALUE_WORD_RE.findall(_DATE_IN_VALUE_RE.sub(" ", value))
    return not any(
        word.islower() and len(word) > 1 and word not in _NUMBER_VALUE_WORDS for word in words
    )


def _is_assembly_number(content: str) -> bool:
    match = _ASSEMBLY_NUMBER_RE.match(content)
    if match is None:
        return False
    body: str = match["body"]
    return sum(character.isupper() for character in body) >= _MIN_TITLE_LETTERS


def _is_closing_line(lines: list[_Line], index: int) -> bool:
    line = lines[index]
    content = line.content
    if not content or line.heading_blocked:
        return False
    number = _NUMBER_VALUE_RE.match(content)
    if number is not None:
        return _is_number_value(number["value"])
    if _SHORT_NUMBER_RE.match(content) or _is_assembly_number(content):
        return True
    if content[0].isupper() and _PLACE_DATE_RE.match(content):
        return True

    previous = lines[index - 1].content if index > 0 else ""
    follows_complete_text = not previous or previous[-1] in _TERMINAL_PUNCTUATION
    if _DATE_LINE_RE.match(content):
        return follows_complete_text
    if not _SIGNATORY_RE.match(content) or content[-1] in _TERMINAL_PUNCTUATION:
        return False
    return follows_complete_text


def _unassigned_spans(
    events: list[_Event], lines: list[_Line], closing_index: int, source: str
) -> tuple[tuple[UnassignedSpan, ...], list[ParseDiagnostic]]:
    """Collect text that follows a structure heading but precedes the next element."""
    spans: list[UnassignedSpan] = []
    diagnostics: list[ParseDiagnostic] = []
    for position, event in enumerate(events):
        if not isinstance(event, _StructureDraft):
            continue
        following = events[position + 1].first_index if position + 1 < len(events) else len(lines)
        block: list[_Line] = []
        for line in [*lines[event.next_index : min(following, closing_index)], None]:
            if line is not None and not line.is_blank:
                block.append(line)
            elif block:
                start, end = block[0].content_start, block[-1].end
                spans.append(UnassignedSpan(start=start, end=end, text=source[start:end]))
                message = "This text does not belong to any article."
                diagnostics.append(_diagnostic(DiagnosticCode.UNASSIGNED_TEXT, message, block[0]))
                block = []
    return tuple(spans), diagnostics


def _canonical_letter(raw: str) -> str:
    lowered = raw.lower()
    return _CYRILLIC_TO_LATIN.get(lowered, lowered)


def _canonical_suffix(raw: str) -> str:
    return "".join(_canonical_letter(letter) for letter in _LETTER_RE.findall(raw))


def _suffix_rank(raw: str) -> tuple[int, ...]:
    """Rank suffix letters in the alphabet of their own script, because the orders differ."""
    ranks: list[int] = []
    for letter in _LETTER_RE.findall(raw.lower()):
        if letter in _CYRILLIC_TO_LATIN:
            ranks.append(_CYRILLIC_LETTERS.index(letter) + 1)
        elif letter in _LATIN_ORDER:
            ranks.append(_LATIN_ORDER.index(letter) + 1)
        else:
            ranks.append(len(_LATIN_ORDER) + 1)
    return tuple(ranks)


def _diagnostic(
    code: DiagnosticCode, message: str, line: _Line, offset: int | None = None
) -> ParseDiagnostic:
    return ParseDiagnostic(
        code=code,
        severity=_SEVERITIES[code],
        message=message,
        line=line.number,
        offset=line.content_start if offset is None else offset,
    )


def _article_label(draft: _ArticleDraft) -> str:
    return f"Član {draft.number}{draft.suffix or ''}"


def _article_ids(drafts: list[_ArticleDraft], law_id: str) -> list[str]:
    seen: Counter[tuple[int, str | None]] = Counter()
    ids: list[str] = []
    for draft in drafts:
        key = (draft.number, draft.suffix)
        seen[key] += 1
        base = f"{law_id}:cl-{draft.number}{draft.suffix or ''}"
        ids.append(base if seen[key] == 1 else f"{base}-dup-{seen[key]}")
    return ids


def _sequence_diagnostics(drafts: list[_ArticleDraft], lines: list[_Line]) -> list[ParseDiagnostic]:
    diagnostics: list[ParseDiagnostic] = []
    seen: set[tuple[int, str | None]] = set()
    highest: tuple[int, tuple[int, ...]] = (0, ())
    for draft in drafts:
        line = lines[draft.heading_index]
        label = _article_label(draft)
        key = (draft.number, draft.suffix)
        if key in seen:
            message = f"{label} appears more than once."
            diagnostics.append(_diagnostic(DiagnosticCode.DUPLICATE_ARTICLE, message, line))
            continue
        seen.add(key)
        order = (draft.number, draft.suffix_rank)
        if order < highest:
            message = f"{label} appears after a higher article number."
            diagnostics.append(_diagnostic(DiagnosticCode.ARTICLE_OUT_OF_ORDER, message, line))
            continue
        if draft.number > highest[0] + 1:
            message = f"Expected article number {highest[0] + 1}, found {draft.number}."
            diagnostics.append(_diagnostic(DiagnosticCode.ARTICLE_NUMBER_GAP, message, line))
        highest = order
    return diagnostics


def _build_article(
    draft: _ArticleDraft,
    article_id: str,
    structure_path: tuple[StructureHeading, ...],
    lines: list[_Line],
    limit: int,
    source: str,
) -> tuple[Article, list[ParseDiagnostic]]:
    body = lines[draft.body_index : limit]
    if draft.paragraph_column is not None:
        heading_line = lines[draft.heading_index]
        column = heading_line.content_start + draft.paragraph_column
        body = [
            replace(heading_line, content=source[column : heading_line.end], content_start=column),
            *body,
        ]
    paragraphs, diagnostics = _build_paragraphs(body, article_id, source)
    heading_end = lines[draft.body_index - 1].end
    start = lines[draft.first_index].content_start
    end = paragraphs[-1].end if paragraphs else heading_end
    if not paragraphs:
        message = f"{_article_label(draft)} has no text."
        diagnostics.append(
            _diagnostic(DiagnosticCode.EMPTY_ARTICLE, message, lines[draft.heading_index])
        )
    article = Article(
        id=article_id,
        number=draft.number,
        suffix=draft.suffix,
        label=_article_label(draft),
        title=draft.title,
        structure_path=structure_path,
        paragraphs=paragraphs,
        text=source[start:end],
        start=start,
        end=end,
    )
    return article, diagnostics


def _build_paragraphs(
    body: list[_Line], article_id: str, source: str
) -> tuple[tuple[ArticleParagraph, ...], list[ParseDiagnostic]]:
    paragraphs: list[ArticleParagraph] = []
    diagnostics: list[ParseDiagnostic] = []
    seen_numbers: Counter[int] = Counter()
    previous_number = 0
    for ordinal, draft in enumerate(_group_paragraphs(body), start=1):
        if draft.number is None:
            paragraph_id = f"{article_id}:p-{ordinal}"
        else:
            seen_numbers[draft.number] += 1
            occurrence = seen_numbers[draft.number]
            paragraph_id = f"{article_id}:st-{draft.number}"
            if occurrence > 1:
                paragraph_id = f"{paragraph_id}-dup-{occurrence}"
            if draft.number != previous_number + 1:
                message = f"Expected paragraph number {previous_number + 1}, found {draft.number}."
                diagnostics.append(
                    _diagnostic(DiagnosticCode.PARAGRAPH_NUMBER_GAP, message, draft.lines[0])
                )
            previous_number = draft.number
        paragraphs.append(_build_paragraph(draft, paragraph_id, ordinal, source))
    return tuple(paragraphs), diagnostics


def _group_paragraphs(body: list[_Line]) -> list[_ParagraphDraft]:
    drafts: list[_ParagraphDraft] = []
    current: _ParagraphDraft | None = None
    for line in body:
        if line.quoted:
            if current is not None:
                current.lines.append(line)
            elif not line.is_blank:
                current = _ParagraphDraft(None, [line], line.content_start)
                drafts.append(current)
            continue
        marker = _PARAGRAPH_RE.match(line.content)
        if marker is not None:
            current = _ParagraphDraft(int(marker[1]), [line], line.content_start + marker.end())
            drafts.append(current)
        elif line.is_blank:
            if current is not None and current.number is None:
                current = None
            elif current is not None:
                current.lines.append(line)
        elif current is not None:
            current.lines.append(line)
        elif drafts and _continues_list(drafts[-1], line):
            current = drafts[-1]
            current.lines.append(line)
        else:
            current = _ParagraphDraft(None, [line], line.content_start)
            drafts.append(current)
    return drafts


def _continues_list(draft: _ParagraphDraft, line: _Line) -> bool:
    """Keep a list together when blank lines separate its points."""
    groups, last_marker = _scan_points(draft)
    previous = draft.lines[-1].content
    if _contextual_marker(line.content, previous, last_marker) is None:
        return False
    return bool(groups) or previous.endswith(":")


def _build_paragraph(
    draft: _ParagraphDraft, paragraph_id: str, ordinal: int, source: str
) -> ArticleParagraph:
    last = next(line for line in reversed(draft.lines) if not line.is_blank)
    text_start = _skip_whitespace(source, draft.text_start, last.end)
    return ArticleParagraph(
        id=paragraph_id,
        number=draft.number,
        ordinal=ordinal,
        text=source[text_start : last.end],
        points=_build_points(draft, paragraph_id, source),
        start=draft.lines[0].content_start,
        end=last.end,
    )


def _marker_follows(lines: list[_Line], start: int, last_marker: _PointMarker | None) -> bool:
    """Report whether a point marker appears at or after a line of the same paragraph."""
    for index in range(start, len(lines)):
        line = lines[index]
        if line.is_blank or line.quoted:
            continue
        if _contextual_marker(line.content, lines[index - 1].content, last_marker) is not None:
            return True
    return False


def _scan_points(draft: _ParagraphDraft) -> tuple[list[_PointGroup], _PointMarker | None]:
    """Group the lines of each point and return the marker that a next point would follow."""
    groups: list[_PointGroup] = []
    current: list[_Line] | None = None
    last_marker: _PointMarker | None = None
    previous = ""
    for index, line in enumerate(draft.lines):
        if line.is_blank:
            if not line.quoted:
                current = None
            continue
        if line.quoted:
            if current is not None:
                current.append(line)
            previous = line.content
            continue
        is_paragraph_marker_line = index == 0 and draft.number is not None
        marker = (
            None
            if is_paragraph_marker_line
            else _contextual_marker(line.content, previous, last_marker)
        )
        if marker is not None:
            current = [line]
            groups.append((marker, current))
            last_marker = marker
        elif current is not None:
            ends_list = current[-1].content.endswith(".") and line.content[0].isupper()
            if ends_list and not _marker_follows(draft.lines, index + 1, last_marker):
                current = None
                last_marker = None
            else:
                current.append(line)
        previous = line.content
    return groups, last_marker


def _build_points(
    draft: _ParagraphDraft, paragraph_id: str, source: str
) -> tuple[ArticlePoint, ...]:
    groups, _ = _scan_points(draft)
    points: list[ArticlePoint] = []
    seen_labels: Counter[str] = Counter()
    for ordinal, (marker, point_lines) in enumerate(groups, start=1):
        start = point_lines[0].content_start
        end = point_lines[-1].end
        text_start = _skip_whitespace(source, start + marker.length, end)
        points.append(
            ArticlePoint(
                id=_point_id(marker, ordinal, paragraph_id, seen_labels),
                kind=marker.kind,
                label=marker.label,
                ordinal=ordinal,
                text=source[text_start:end],
                start=start,
                end=end,
            )
        )
    return tuple(points)


def _point_id(
    marker: _PointMarker, ordinal: int, paragraph_id: str, seen_labels: Counter[str]
) -> str:
    if marker.kind is PointKind.DASH:
        return f"{paragraph_id}:al-{ordinal}"
    seen_labels[marker.label] += 1
    occurrence = seen_labels[marker.label]
    point_id = f"{paragraph_id}:t-{marker.label}"
    return point_id if occurrence == 1 else f"{point_id}-dup-{occurrence}"


def _point_marker(content: str) -> _PointMarker | None:
    """Recognize markers that are unambiguous without looking at surrounding lines."""
    number = _NUMBER_POINT_RE.match(content)
    if number is not None:
        return _PointMarker(PointKind.NUMBER, str(int(number[1])), number.end())
    letter = _LETTER_POINT_RE.match(content)
    if letter is not None:
        raw = letter["wrapped"] or letter["plain"]
        return _PointMarker(PointKind.LETTER, _canonical_letter(raw), letter.end())
    dash = _DASH_POINT_RE.match(content)
    if dash is not None:
        return _PointMarker(PointKind.DASH, "-", dash.end())
    return None


def _contextual_marker(
    content: str, previous: str, last_marker: _PointMarker | None
) -> _PointMarker | None:
    """Recognize every marker, including forms that depend on the preceding line or point."""
    marker = _point_marker(content)
    if marker is not None:
        return marker
    follows_colon = previous.endswith(":")
    tight_dash = _TIGHT_DASH_RE.match(content)
    if tight_dash is not None:
        follows_dash = last_marker is not None and last_marker.kind is PointKind.DASH
        return (
            _PointMarker(PointKind.DASH, "-", tight_dash.end())
            if (follows_colon or follows_dash)
            else None
        )
    dotted = _DOTTED_NUMBER_RE.match(content)
    if dotted is None:
        return None
    number = int(dotted[1])
    starts_list = number == 1 and follows_colon
    continues_list = (
        last_marker is not None
        and last_marker.kind is PointKind.NUMBER
        and number == int(last_marker.label) + 1
    )
    if starts_list or continues_list:
        return _PointMarker(PointKind.NUMBER, str(number), dotted.end())
    return None


def _skip_whitespace(source: str, start: int, end: int) -> int:
    while start < end and source[start].isspace():
        start += 1
    return start
