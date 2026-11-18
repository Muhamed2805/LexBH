"""Frozen domain models for parsed legal texts.

Every ``start`` and ``end`` is an offset into ``ParsedLaw.source_text``, the normalized text.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class LawParseError(ValueError):
    """Raised when a text contains no article."""


class Jurisdiction(StrEnum):
    BIH = "BIH"
    FBIH = "FBIH"
    RS = "RS"
    BD = "BD"


class StructureKind(StrEnum):
    PART = "part"
    DIVISION = "division"
    CHAPTER = "chapter"
    SECTION = "section"


class PointKind(StrEnum):
    LETTER = "letter"
    NUMBER = "number"
    DASH = "dash"


class DiagnosticSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(StrEnum):
    DUPLICATE_ARTICLE = "DUPLICATE_ARTICLE"
    ARTICLE_NUMBER_GAP = "ARTICLE_NUMBER_GAP"
    ARTICLE_OUT_OF_ORDER = "ARTICLE_OUT_OF_ORDER"
    PARAGRAPH_NUMBER_GAP = "PARAGRAPH_NUMBER_GAP"
    EMPTY_ARTICLE = "EMPTY_ARTICLE"
    UNASSIGNED_TEXT = "UNASSIGNED_TEXT"
    UNTERMINATED_QUOTE = "UNTERMINATED_QUOTE"
    QUOTED_HEADING = "QUOTED_HEADING"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


LawId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Offset = Annotated[int, Field(ge=0)]


class LawMetadata(_FrozenModel):
    """Facts about a law. Supplied by the caller and never guessed from the text."""

    law_id: LawId
    title: Annotated[str, StringConstraints(min_length=1)]
    jurisdiction: Jurisdiction
    gazette_citation: str | None = None
    published_on: date | None = None
    effective_from: date | None = None


class StructureHeading(_FrozenModel):
    """A structure heading, as written in the source. Unnumbered divisions have an empty label."""

    kind: StructureKind
    label: str
    title: str | None
    start: Offset
    end: Offset


class ArticlePoint(_FrozenModel):
    """A list item. ``text`` is the span without its marker."""

    id: str
    kind: PointKind
    label: str
    ordinal: int
    text: str
    start: Offset
    end: Offset


class ArticleParagraph(_FrozenModel):
    """A paragraph. ``text`` is the span without its marker and includes any points."""

    id: str
    number: int | None
    ordinal: int
    text: str
    points: tuple[ArticlePoint, ...]
    start: Offset
    end: Offset


class Article(_FrozenModel):
    """An article. ``text`` is the exact span, including its heading and title."""

    id: str
    number: int
    suffix: str | None
    label: str
    title: str | None
    structure_path: tuple[StructureHeading, ...]
    paragraphs: tuple[ArticleParagraph, ...]
    text: str
    start: Offset
    end: Offset


class ParseDiagnostic(_FrozenModel):
    """A problem found in the text. ``line`` is 1-based and ``offset`` is 0-based."""

    code: DiagnosticCode
    severity: DiagnosticSeverity
    message: str
    line: int
    offset: Offset


class UnassignedSpan(_FrozenModel):
    """Text that belongs to no preamble, heading, article, or closing block."""

    start: Offset
    end: Offset
    text: str


class ParsedLaw(_FrozenModel):
    """A parsed law.

    Every non-whitespace character of ``source_text`` belongs to exactly one of:
    ``source_text[:preamble_end]``, a structure heading, an article,
    ``source_text[closing_start:]``, or an unassigned span.
    """

    metadata: LawMetadata
    source_text: str
    preamble: str
    preamble_end: Offset
    structure_headings: tuple[StructureHeading, ...]
    articles: tuple[Article, ...]
    closing_text: str
    closing_start: Offset
    unassigned: tuple[UnassignedSpan, ...]


class ParseResult(_FrozenModel):
    law: ParsedLaw
    diagnostics: tuple[ParseDiagnostic, ...]
