"""Parsing of legal texts into structured articles with exact source offsets."""

from lexbh.ingestion.models import (
    Article,
    ArticleParagraph,
    ArticlePoint,
    DiagnosticCode,
    DiagnosticSeverity,
    Jurisdiction,
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
from lexbh.ingestion.parser import parse_law

__all__ = [
    "Article",
    "ArticleParagraph",
    "ArticlePoint",
    "DiagnosticCode",
    "DiagnosticSeverity",
    "Jurisdiction",
    "LawMetadata",
    "LawParseError",
    "ParseDiagnostic",
    "ParseResult",
    "ParsedLaw",
    "PointKind",
    "StructureHeading",
    "StructureKind",
    "UnassignedSpan",
    "normalize_text",
    "parse_law",
]
