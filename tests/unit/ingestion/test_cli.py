"""Tests for the law inspection CLI. All legal text in this module is fictional."""

import io
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

from lexbh.ingestion.cli import main
from tests.unit.ingestion.helpers import CYRILLIC_FIXTURE, LATIN_FIXTURE

METADATA_ARGS = ["--law-id", "fiktivni-zakon", "--title", "Fiktivni zakon", "--jurisdiction", "BIH"]
FICTIONAL_LAW = "Član 1.\nIzmišljeni tekst o zvonima.\n\nČlan 2.\nŠesto izmišljeno zvono.\n"
REPLACEMENT_CHARACTER = chr(0xFFFD)


def run(path: Path, *extra: str) -> int:
    return main([str(path), *METADATA_ARGS, *extra])


def write_law(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "fiktivni_zakon.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


def law_with_numbers(numbers: Iterable[int]) -> str:
    return "\n\n".join(f"Član {number}.\nIzmišljena odredba." for number in numbers)


def section(report: str, title: str) -> list[str]:
    """Return the rows of one report section, without their indentation."""
    rows = f"\n{report}".split(f"\n{title}\n", 1)[1]
    return [row.strip() for row in rows.split("\n\n", 1)[0].splitlines()]


def assert_single_line_failure(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
    return captured.err


@pytest.mark.parametrize("path", [LATIN_FIXTURE, CYRILLIC_FIXTURE])
def test_fixture_report_exits_clean(path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(path) == 0

    articles = section(capsys.readouterr().out, "Articles")
    assert "count: 18" in articles
    assert "first: Član 1" in articles
    assert "last: Član 14" in articles
    assert "suffixed: Član 12a, Član 12b, Član 13a, Član 13b" in articles


def test_report_sections_appear_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    run(LATIN_FIXTURE, "--articles")
    lines = capsys.readouterr().out.splitlines()

    positions = [
        lines.index(title)
        for title in (
            "File",
            "Articles",
            "Paragraphs",
            "Points",
            "Structure headings",
            "Coverage",
            "Diagnostics",
            "Longest articles",
            "Outline",
        )
    ]
    assert positions == sorted(positions)


def test_bom_and_cp1250_produce_the_same_articles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with_bom = tmp_path / "bom.txt"
    with_bom.write_bytes(FICTIONAL_LAW.encode("utf-8-sig"))
    legacy = tmp_path / "legacy.txt"
    legacy.write_bytes(FICTIONAL_LAW.encode("cp1250"))

    assert run(with_bom) == 0
    bom_report = capsys.readouterr().out
    assert run(legacy, "--encoding", "cp1250") == 0
    legacy_report = capsys.readouterr().out

    assert "count: 2" in section(bom_report, "Articles")
    assert bom_report.split("\nArticles\n")[1] == legacy_report.split("\nArticles\n")[1]


def test_invalid_utf8_suggests_cp1250(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes(FICTIONAL_LAW.encode("cp1250"))

    assert run(path) == 2

    error = assert_single_line_failure(capsys)
    assert str(path) in error
    assert "utf-8-sig" in error
    assert "--encoding cp1250" in error


@pytest.mark.parametrize(
    ("text", "line"),
    [
        (f"Član 1.\nPrvi{REPLACEMENT_CHARACTER} tekst.", 2),
        (f"Član 1.\r\nPrvi tekst.\r\nTreći{REPLACEMENT_CHARACTER} red.", 3),
        (f"Član 1.\rPrvi tekst.\rTreći{REPLACEMENT_CHARACTER} red.", 3),
    ],
)
def test_replacement_character_reports_its_line(
    text: str, line: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(write_law(tmp_path, text)) == 2

    assert f"line {line}" in assert_single_line_failure(capsys)


def test_missing_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path / "nepostojeci.txt") == 2

    assert_single_line_failure(capsys)


def test_directory_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path) == 2

    assert_single_line_failure(capsys)


def test_unknown_encoding_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(write_law(tmp_path, FICTIONAL_LAW), "--encoding", "izmisljeni-kodek") == 2

    assert "izmisljeni-kodek" in assert_single_line_failure(capsys)


def test_text_without_article_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(write_law(tmp_path, "Izmišljeni tekst bez ijednog člana.")) == 2

    assert_single_line_failure(capsys)


@pytest.mark.parametrize(("flag", "value"), [("--law-id", "Neispravan ID"), ("--title", "")])
def test_invalid_metadata_exits_2(
    flag: str, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_law(tmp_path, FICTIONAL_LAW)

    assert main([str(path), *METADATA_ARGS, flag, value]) == 2

    assert "invalid metadata" in assert_single_line_failure(capsys)


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["zakon.txt", "--law-id", "fiktivni-zakon"],
        ["zakon.txt", "--law-id", "a", "--title", "b", "--jurisdiction", "NEPOSTOJECA"],
        ["zakon.txt", *METADATA_ARGS, "--nepoznato"],
    ],
)
def test_usage_errors_exit_2_on_one_line(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 2

    assert_single_line_failure(capsys)


def test_abbreviated_flag_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(write_law(tmp_path, FICTIONAL_LAW), "--art") == 2

    assert "--art" in assert_single_line_failure(capsys)


def test_help_prints_usage_to_stdout_and_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0

    captured = capsys.readouterr()
    assert captured.out.startswith("usage: ")
    assert captured.err == ""


@pytest.mark.parametrize(
    ("text", "lines"),
    [
        ("Član 1.\nIzmišljena odredba.\n", 2),
        ("Član 1.\nIzmišljena odredba.", 2),
        ("Član 1.\n\nIzmišljena odredba.\n", 3),
    ],
)
def test_file_section_counts_lines_exactly(
    text: str, lines: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(write_law(tmp_path, text))

    assert f"lines: {lines}" in section(capsys.readouterr().out, "File")


def test_paragraph_counts_are_exact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = "Član 1.\n(1) Prvi.\n(2) Drugi.\n(3) Treći.\n\nČlan 2.\nIzmišljena odredba."

    run(write_law(tmp_path, text))

    assert section(capsys.readouterr().out, "Paragraphs") == ["numbered: 3", "unnumbered: 1"]


def test_titled_article_count_is_exact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = "Član 1.\n(Naslov)\nPrva.\n\nČlan 2.\nDruga.\n\nČlan 3.\nTreća."

    run(write_law(tmp_path, text))

    articles = section(capsys.readouterr().out, "Articles")
    assert "count: 3" in articles
    assert "with title: 1" in articles


def test_preamble_and_closing_lengths_are_exact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "Izmišljeni uvod.\n\nČlan 1.\nPrva.\n\nBroj: 01-02/30"

    run(write_law(tmp_path, text))

    coverage = section(capsys.readouterr().out, "Coverage")
    assert "preamble characters: 16" in coverage
    assert "closing characters: 14" in coverage


def test_unassigned_span_count_is_not_the_article_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "DIO PRVI\n\nPrvi višak.\n\nDrugi višak.\n\nČlan 1.\nPrva."

    assert run(write_law(tmp_path, text)) == 1

    report = capsys.readouterr().out
    assert "count: 1" in section(report, "Articles")
    assert "unassigned spans: 2" in section(report, "Coverage")


def test_warning_only_input_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_law(tmp_path, "Član 1.\nPrva.\n\nČlan 3.\nTreća.")

    assert run(path) == 0

    assert "ARTICLE_NUMBER_GAP: 1" in section(capsys.readouterr().out, "Diagnostics")


def test_duplicate_article_is_an_error_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_law(tmp_path, "Član 1.\nPrva.\n\nČlan 1.\nDruga.")

    assert run(path) == 1

    rows = section(capsys.readouterr().out, "Diagnostics")
    assert any(row.startswith("error DUPLICATE_ARTICLE line 4:") for row in rows)


def test_unassigned_text_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    orphan = "Izmišljeni tekst bez mjesta."
    path = write_law(tmp_path, f"DIO PRVI\n\n{orphan}\n\nČlan 1.\nPrva.")

    assert run(path) == 1

    coverage = section(capsys.readouterr().out, "Coverage")
    assert "unassigned spans: 1" in coverage
    assert f"unassigned non-whitespace characters: {len(orphan.replace(' ', ''))}" in coverage


def test_coverage_percentage_never_rounds_up_to_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orphan = "Tekst."
    text = f"DIO PRVI\n\n{orphan}\n\nČlan 1.\n" + "Izmišljeno zvono. " * 10_000
    total = len("".join(text.split()))
    assert 0.99995 <= (total - len(orphan)) / total < 1

    assert run(write_law(tmp_path, text)) == 1

    assert "assigned non-whitespace characters: 99.99%" in section(
        capsys.readouterr().out, "Coverage"
    )


def test_complete_coverage_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    run(LATIN_FIXTURE)

    assert "assigned non-whitespace characters: 100.00%" in section(
        capsys.readouterr().out, "Coverage"
    )


def test_missing_article_numbers_are_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_law(tmp_path, "Član 2.\nDruga.\n\nČlan 5.\nPeta.\n\nČlan 7.\nSedma.")

    run(path)

    assert "missing numbers: 3-4, 6 (3 total)" in section(capsys.readouterr().out, "Articles")


def test_consecutive_article_numbers_report_no_gaps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(write_law(tmp_path, law_with_numbers([4, 5, 6])))

    assert "missing numbers: none" in section(capsys.readouterr().out, "Articles")


def test_huge_article_number_does_not_expand_the_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(write_law(tmp_path, law_with_numbers([1, 999_999_999_999]))) == 0

    assert "missing numbers: 2-999999999998 (999999999997 total)" in section(
        capsys.readouterr().out, "Articles"
    )


def test_exactly_twenty_gaps_are_all_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(write_law(tmp_path, law_with_numbers(range(1, 42, 2))))

    gaps = ", ".join(str(number) for number in range(2, 41, 2))
    assert f"missing numbers: {gaps} (20 total)" in section(capsys.readouterr().out, "Articles")


def test_gaps_beyond_twenty_are_summarized(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(write_law(tmp_path, law_with_numbers(range(1, 65, 3))))

    gaps = ", ".join(f"{number}-{number + 1}" for number in range(2, 60, 3))
    assert f"missing numbers: {gaps}, +1 more gaps (42 total)" in section(
        capsys.readouterr().out, "Articles"
    )


def test_excerpts_are_short_and_stay_on_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_law(tmp_path, "Član 1.\nPrva.\n\nČlan 3.\n" + "Izmišljeno zvono " * 20)

    run(path)

    rows = section(capsys.readouterr().out, "Diagnostics")
    row = next(item for item in rows if item.startswith("warning ARTICLE_NUMBER_GAP"))
    excerpt = row.split(" | ", 1)[1]
    assert excerpt.startswith("Član 3. Izmišljeno zvono")
    assert len(excerpt) <= 100


def test_longest_articles_are_sorted_and_limited_to_five(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repeats = {1: 3, 2: 7, 3: 1, 4: 5, 5: 2, 6: 6, 7: 4}
    articles = [f"Član {number}.\n{'Zvono. ' * count}" for number, count in repeats.items()]
    path = write_law(tmp_path, "\n\n".join(articles))

    run(path)

    rows = section(capsys.readouterr().out, "Longest articles")
    assert [row.split(" | ")[0] for row in rows] == [
        "Član 2",
        "Član 6",
        "Član 4",
        "Član 7",
        "Član 1",
    ]
    assert rows[0] == "Član 2 | paragraphs: 1, points: 0, characters: 56"


def test_outline_lists_headings_and_articles_in_document_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "DIO PRVI\n\nČlan 1.\nPrva.\n\nGLAVA II\nNADZOR\n\nNaslov člana\nČlan 2.\n(1) Druga."
    path = write_law(tmp_path, text)

    assert run(path, "--articles") == 0

    assert section(capsys.readouterr().out, "Outline") == [
        "[part] DIO PRVI | -",
        "Član 1 | - | paragraphs: 1, points: 0, characters: 13",
        "[chapter] GLAVA II | NADZOR",
        "Član 2 | Naslov člana | paragraphs: 1, points: 0, characters: 31",
    ]


def test_outline_is_absent_without_the_flag(capsys: pytest.CaptureFixture[str]) -> None:
    run(LATIN_FIXTURE)

    assert "Outline" not in capsys.readouterr().out.splitlines()


def test_stdout_that_cannot_encode_the_text_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="ascii")
    monkeypatch.setattr(sys, "stdout", stream)

    assert run(LATIN_FIXTURE) == 0

    stream.flush()
    assert "Član 1".encode("ascii", "backslashreplace") in buffer.getvalue()


def test_tool_writes_no_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_law(tmp_path, FICTIONAL_LAW)
    monkeypatch.chdir(tmp_path)
    before = {item: item.stat().st_mtime_ns for item in tmp_path.rglob("*")}

    assert run(path, "--articles") == 0

    assert {item: item.stat().st_mtime_ns for item in tmp_path.rglob("*")} == before
    assert path.read_bytes() == FICTIONAL_LAW.encode("utf-8")
