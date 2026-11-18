"""Tests for text normalization. All sample text is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import normalize_text

NO_BREAK_SPACE = chr(0x00A0)
FIGURE_SPACE = chr(0x2007)
NARROW_NO_BREAK_SPACE = chr(0x202F)
SOFT_HYPHEN = chr(0x00AD)
COMBINING_CARON = chr(0x030C)
PRECOMPOSED_C_CARON = chr(0x010D)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("prvi\r\ndrugi\rtreći", "prvi\ndrugi\ntreći"),
        (f"c{COMBINING_CARON}aj", f"{PRECOMPOSED_C_CARON}aj"),
        (f"izmišljeni{NO_BREAK_SPACE}tekst", "izmišljeni tekst"),
        (f"izmišljeni{FIGURE_SPACE}tekst", "izmišljeni tekst"),
        (f"izmišljeni{NARROW_NO_BREAK_SPACE}tekst", "izmišljeni tekst"),
        (f"iz{SOFT_HYPHEN}mišljeni", "izmišljeni"),
        (f"c{SOFT_HYPHEN}{COMBINING_CARON}aj", f"{PRECOMPOSED_C_CARON}aj"),
        ("red  \t\nsljedeći ", "red\nsljedeći"),
        (f"red{NO_BREAK_SPACE}\nsljedeći", "red\nsljedeći"),
    ],
)
def test_normalizes_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


@pytest.mark.parametrize("code_point", [0xFEFF, 0x200B, 0x200C, 0x200D, 0x2060])
def test_removes_invisible_characters(code_point: int) -> None:
    assert normalize_text(f"iz{chr(code_point)}mišljeni") == "izmišljeni"


@pytest.mark.parametrize("code_point", [0x000B, 0x000C, 0x0085, 0x2028, 0x2029])
def test_converts_line_separators_to_line_feeds(code_point: int) -> None:
    assert normalize_text(f"prvi{chr(code_point)}drugi") == "prvi\ndrugi"


@pytest.mark.parametrize("text", ["Члан 5а", "pod-\nnaslov"])
def test_never_transliterates_or_joins_hyphenated_words(text: str) -> None:
    assert normalize_text(text) == text


def test_is_idempotent() -> None:
    raw = f"c{COMBINING_CARON}{NO_BREAK_SPACE}red \r\n{SOFT_HYPHEN}sljedeći\r"
    once = normalize_text(raw)

    assert normalize_text(once) == once
