"""Text normalization applied before parsing.

Normalization never transliterates the text and never joins hyphenated words.
"""

import re
import unicodedata

_LINE_BREAKS = re.compile(r"\r\n?")
_NO_BREAK_SPACE = 0x00A0
_FIGURE_SPACE = 0x2007
_NARROW_NO_BREAK_SPACE = 0x202F
_SOFT_HYPHEN = 0x00AD
_INVISIBLE_CHARACTERS = (0xFEFF, 0x200B, 0x200C, 0x200D, 0x2060)
_LINE_SEPARATORS = (0x000B, 0x000C, 0x0085, 0x2028, 0x2029)
_CHARACTER_MAP: dict[int, str | None] = {
    _NO_BREAK_SPACE: " ",
    _FIGURE_SPACE: " ",
    _NARROW_NO_BREAK_SPACE: " ",
    _SOFT_HYPHEN: None,
    **dict.fromkeys(_INVISIBLE_CHARACTERS),
    **dict.fromkeys(_LINE_SEPARATORS, "\n"),
}


def normalize_text(text: str) -> str:
    """Return the canonical form of ``text`` that all parser offsets refer to."""
    unified = _LINE_BREAKS.sub("\n", text).translate(_CHARACTER_MAP)
    composed = unicodedata.normalize("NFC", unified)
    return "\n".join(line.rstrip() for line in composed.split("\n"))
