"""Adversarial parser inputs. All legal text in this module is invented."""

# ruff: noqa: RUF001

from pathlib import Path

import pytest

from lexbh.ingestion import (
    DiagnosticCode,
    ParsedLaw,
    ParseResult,
    PointKind,
    StructureKind,
)
from tests.unit.ingestion.helpers import (
    CYRILLIC_FIXTURE,
    LATIN_FIXTURE,
    METADATA,
    parse,
    parse_fixture,
)

T2 = "\n\nČlan 2.\nDrugi tekst."
AM = "Član 1.\nDodaju se članovi koji glase:\n"

CASES = {
    1: "\ufeffČlan 1.\nPrvi tekst." + T2,
    2: "\u200bČlan 1.\nPrvi tekst." + T2,
    3: "Član 1.\x0bPrvi tekst." + T2,
    4: "Član 1. Predmet zakona\nPrvi tekst." + T2,
    5: "Član 1: Predmet zakona\nPrvi tekst." + T2,
    6: "Član 1. (1) Prvi stav.\n(2) Drugi stav." + T2,
    7: "Član 1.\nOvo se primjenjuje kako propisuje\nčlan 5.\nNastavak teksta." + T2,
    8: "Član 1.\nOvo se primjenjuje kako propisuju\nčlan 5. i\nčlan 6. ovog zakona." + T2,
    9: (
        "Član 1.\nDodaju se novi članovi koji glase:\n„Član 7a.\nPrvi dodani tekst.\n\n"
        "Član 7b.\nDrugi dodani tekst.“" + T2
    ),
    10: "Član 12.\nPrvi.\n\nČlan 12aa.\nDrugi.",
    11: "Član 1.\nPrvi tekst.\nČlan 5. Zakona o zvonima primjenjuje se\nna sve obveznike.",
    12: "ZAKON O ZVONIMA\nČlan 1.\nPrvi tekst.",
    13: "Član 1.\n(Predmet i cilj\novog zakona)\n(1) Tekst.",
    14: "Član 1.\n\n(Predmet)\n\n(1) Tekst.",
    15: "Član 1.\nPrvi tekst.\n\nII. NADZOR\n\nČlan 2.\nDrugi.",
    16: "Član 1.\nPrvi tekst.\n\nII. NADZOR\nČlan 2.\nDrugi.",
    17: "Član 1.\nPrvi tekst.\n\nII - NADZOR\n\nČlan 2.\nDrugi.",
    18: "Član 1.\nPrvi tekst.\n\nGlava II\nNadzor\n\nČlan 2.\nDrugi.",
    19: "Član 1.\nPrvi tekst.\n\nGLAVA DRUGA\nNADZOR\n\nČlan 2.\nDrugi.",
    20: "Član 1.\nPrvi tekst.\n\nNadzor nad radom\n\nČlan 2.\nDrugi.",
    21: "Član 1.\nPrvi tekst.\n\nNadzor nad radom\nizmišljenog ureda\nČlan 2.\nDrugi.",
    22: "Član 1.\nPrvi tekst.\n\nkoji nema veliko slovo\nČlan 2.\nDrugi.",
    23: (
        "Član 1.\n(1) Primjenjuje se na:\na) prvo,\nb) drugo.\nOva odredba važi uvijek.\n"
        "(2) Drugi stav."
    ),
    24: "Član 1.\nPrimjenjuje se na:\n— prvo,\n— drugo.",
    25: "Član 1.\nPrimjenjuje se na:\n-prvo,\n-drugo.",
    26: "Član 1.\nPrimjenjuje se na:\n• prvo,\n• drugo.",
    27: "Član 1.\nZnačenje izraza:\n1. prvo,\n2. drugo.",
    28: "Član 1.\nZakon stupa na snagu\n1. januara 2030. godine.",
    29: (
        "Član 1.\nPrvi tekst.\n\nPSBiH broj 12/30\n7. aprila 2030. godine\nSarajevo\n\n"
        "Predsjedavajući\nFiktivnog doma"
    ),
    30: "Član 1.\nPrvi tekst.\n\n12. 3. 2030. godine\nSarajevo",
    31: "Član 1.\nKomisija je mala.\nBroj: pet članova je dovoljan za rad.",
    32: "DIO PRVI\n\nVažan uvodni tekst.\n\nČlan 1.\nPrvi.",
    33: "Član 1.\nPrvi.\n\nGLAVA II\n\nVažan tekst bez mjesta.\n\nČlan 2.\nDrugi.",
    34: "Član 1.\nNaziv „Zvono je upisan.\n\nČlan 2.\nDrugi tekst“ kraj.",
    35: AM + "„Član 7a.\nPrvi.\n\nČlan 7b.\nDrugi.“" + T2,
    36: AM + "“Član 7a.\nPrvi.\n\nČlan 7b.\nDrugi.”" + T2,
    37: AM + "»Član 7a.\nPrvi.\n\nČlan 7b.\nDrugi.«" + T2,
    38: "Član 1.\nNaziv „Zvono“ je upisan." + T2,
    39: "ZAKON\n\nO FIKTIVNIM ZVONIMA\n\nČlan 1.\nPrvi tekst.",
    40: "ЗАКОН\n\nО ФИКТИВНИМ ЗВОНИМА\n\nЧлан 1.\nПрви текст.",
    41: "ZAKON O ZVONIMA\n\nOPŠTE ODREDBE\n\nČlan 1.\nPrvi tekst.",
    42: "Član 1.\nPrimjenjuje se:\na) iz člana 5.\nZakona o zvonima,\nb) drugo.",
    43: (
        "Član 1.\n(1) Primjenjuje se na:\na) prvo,\nb) drugo.\nOva odredba važi uvijek.\n"
        "(2) Drugi stav."
    ),
}


def short_ids(result: ParseResult) -> list[str]:
    return [article.id.removeprefix(f"{METADATA.law_id}:") for article in result.law.articles]


def paragraph_suffixes(result: ParseResult, article: int = 0) -> list[str]:
    paragraphs = result.law.articles[article].paragraphs
    return [paragraph.id.rsplit(":", 1)[1] for paragraph in paragraphs]


def assert_second_article_follows_first_text(result: ParseResult) -> None:
    assert short_ids(result) == ["cl-1", "cl-2"]
    assert result.law.articles[0].text.endswith("Prvi tekst.")
    assert result.law.articles[1].paragraphs[0].text == "Drugi."


def assert_covered_exactly_once(law: ParsedLaw) -> None:
    source = law.source_text
    spans = [(0, law.preamble_end), (law.closing_start, len(source))]
    spans.extend((item.start, item.end) for item in law.structure_headings)
    spans.extend((item.start, item.end) for item in law.articles)
    spans.extend((item.start, item.end) for item in law.unassigned)

    owners = [0] * len(source)
    for start, end in spans:
        for position in range(start, end):
            owners[position] += 1

    uncovered = [
        position
        for position, character in enumerate(source)
        if not character.isspace() and owners[position] != 1
    ]
    assert uncovered == []
    assert law.preamble == source[: law.preamble_end].strip()
    assert law.closing_text == source[law.closing_start :].strip()
    assert all(item.text == source[item.start : item.end] for item in law.unassigned)


@pytest.mark.parametrize("number", sorted(CASES))
def test_coverage_invariant_holds_for_adversarial_input(number: int) -> None:
    assert_covered_exactly_once(parse(CASES[number]).law)


@pytest.mark.parametrize("path", [LATIN_FIXTURE, CYRILLIC_FIXTURE])
def test_coverage_invariant_holds_for_fixture(path: Path) -> None:
    assert_covered_exactly_once(parse_fixture(path).law)


def test_there_are_43_adversarial_cases() -> None:
    assert sorted(CASES) == list(range(1, 44))


def test_case_01_byte_order_mark() -> None:
    assert short_ids(parse(CASES[1])) == ["cl-1", "cl-2"]


def test_case_02_zero_width_space() -> None:
    assert short_ids(parse(CASES[2])) == ["cl-1", "cl-2"]


def test_case_03_vertical_tab() -> None:
    assert short_ids(parse(CASES[3])) == ["cl-1", "cl-2"]


def test_case_04_inline_title_after_period() -> None:
    result = parse(CASES[4])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert result.law.articles[0].title == "Predmet zakona"


def test_case_05_inline_title_after_colon() -> None:
    result = parse(CASES[5])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert result.law.articles[0].title == "Predmet zakona"


def test_case_06_paragraph_on_heading_line() -> None:
    result = parse(CASES[6])
    first = result.law.articles[0].paragraphs[0]

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert paragraph_suffixes(result) == ["st-1", "st-2"]
    assert result.law.source_text[first.start :].startswith("(1) Prvi stav.")
    assert first.text == "Prvi stav."


def test_case_07_lowercase_reference_is_not_a_heading() -> None:
    result = parse(CASES[7])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert "član 5.\nNastavak teksta." in result.law.articles[0].text


def test_case_08_lowercase_references_are_not_headings() -> None:
    result = parse(CASES[8])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert "član 6. ovog zakona." in result.law.articles[0].text


def test_case_09_quoted_articles_stay_in_enclosing_article() -> None:
    result = parse(CASES[9])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert "Član 7b." in result.law.articles[0].text


def test_case_10_attached_double_letter_suffix() -> None:
    assert short_ids(parse(CASES[10])) == ["cl-12", "cl-12aa"]


def test_case_11_sentence_with_capital_is_not_an_inline_title() -> None:
    result = parse(CASES[11])

    assert short_ids(result) == ["cl-1"]
    assert "na sve obveznike." in result.law.articles[0].text


def test_case_12_law_title_stays_in_preamble() -> None:
    law = parse(CASES[12]).law

    assert law.articles[0].title is None
    assert "ZAKON" in law.preamble


def test_case_13_parenthesized_title_on_two_lines() -> None:
    result = parse(CASES[13])

    assert result.law.articles[0].title == "Predmet i cilj ovog zakona"
    assert paragraph_suffixes(result) == ["st-1"]


def test_case_14_parenthesized_title_after_blank_line() -> None:
    result = parse(CASES[14])

    assert result.law.articles[0].title == "Predmet"
    assert paragraph_suffixes(result) == ["st-1"]


def test_case_15_roman_division_with_period() -> None:
    result = parse(CASES[15])
    division = result.law.articles[1].structure_path[-1]

    assert_second_article_follows_first_text(result)
    assert (division.kind, division.label, division.title) == (
        StructureKind.DIVISION,
        "II",
        "NADZOR",
    )


def test_case_16_roman_division_directly_above_heading() -> None:
    result = parse(CASES[16])
    second = result.law.articles[1]

    assert_second_article_follows_first_text(result)
    assert (second.structure_path[-1].kind, second.structure_path[-1].label) == (
        StructureKind.DIVISION,
        "II",
    )
    assert second.title is None


def test_case_17_roman_division_with_dash() -> None:
    result = parse(CASES[17])
    division = result.law.articles[1].structure_path[-1]

    assert_second_article_follows_first_text(result)
    assert (division.kind, division.label) == (StructureKind.DIVISION, "II")


def test_case_18_title_case_chapter_with_title_below() -> None:
    result = parse(CASES[18])
    chapter = result.law.articles[1].structure_path[-1]

    assert_second_article_follows_first_text(result)
    assert (chapter.kind, chapter.title) == (StructureKind.CHAPTER, "Nadzor")


def test_case_19_feminine_ordinal_chapter() -> None:
    result = parse(CASES[19])
    chapter = result.law.articles[1].structure_path[-1]

    assert_second_article_follows_first_text(result)
    assert (chapter.kind, chapter.title) == (StructureKind.CHAPTER, "NADZOR")


def test_case_20_title_separated_by_blank_line() -> None:
    result = parse(CASES[20])

    assert_second_article_follows_first_text(result)
    assert result.law.articles[1].title == "Nadzor nad radom"


def test_case_21_title_on_two_lines() -> None:
    result = parse(CASES[21])

    assert_second_article_follows_first_text(result)
    assert result.law.articles[1].title == "Nadzor nad radom izmišljenog ureda"


def test_case_22_lowercase_line_is_never_a_title() -> None:
    result = parse(CASES[22])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert result.law.articles[1].title is None
    assert result.law.articles[0].text.endswith("koji nema veliko slovo")


def test_case_23_sentence_after_list_does_not_join_last_point() -> None:
    result = parse(CASES[23])
    paragraph = result.law.articles[0].paragraphs[0]

    assert paragraph.points[-1].label == "b"
    assert paragraph.points[-1].text == "drugo."
    assert paragraph.text.endswith("Ova odredba važi uvijek.")
    assert paragraph_suffixes(result) == ["st-1", "st-2"]


@pytest.mark.parametrize("number", [24, 25, 26])
def test_cases_24_to_26_dash_points(number: int) -> None:
    points = parse(CASES[number]).law.articles[0].paragraphs[0].points

    assert [point.kind for point in points] == [PointKind.DASH, PointKind.DASH]
    assert [point.text for point in points] == ["prvo,", "drugo."]


def test_case_27_dotted_number_points() -> None:
    points = parse(CASES[27]).law.articles[0].paragraphs[0].points

    assert [(point.kind, point.label) for point in points] == [
        (PointKind.NUMBER, "1"),
        (PointKind.NUMBER, "2"),
    ]


def test_case_28_date_is_not_a_number_point() -> None:
    law = parse(CASES[28]).law

    assert law.articles[0].paragraphs[0].points == ()
    assert law.articles[0].text.endswith("1. januara 2030. godine.")
    assert law.closing_text == ""


def test_case_29_assembly_number_starts_closing() -> None:
    law = parse(CASES[29]).law

    assert law.closing_text.startswith("PSBiH broj 12/30")
    assert law.articles[0].text.endswith("Prvi tekst.")


def test_case_30_standalone_date_starts_closing() -> None:
    law = parse(CASES[30]).law

    assert law.closing_text.startswith("12. 3. 2030.")
    assert law.articles[0].text.endswith("Prvi tekst.")


def test_case_31_sentence_after_broj_stays_in_article() -> None:
    law = parse(CASES[31]).law

    assert law.articles[0].text.endswith("Broj: pet članova je dovoljan za rad.")
    assert law.closing_text == ""


def assert_unassigned(result: ParseResult, text: str) -> None:
    span = result.law.unassigned[0]

    assert [item.text for item in result.law.unassigned] == [text]
    assert result.law.source_text[span.start : span.end] == text
    assert DiagnosticCode.UNASSIGNED_TEXT in [item.code for item in result.diagnostics]


def test_case_32_text_after_first_structure_heading() -> None:
    assert_unassigned(parse(CASES[32]), "Važan uvodni tekst.")


def test_case_33_text_between_chapter_and_article() -> None:
    assert_unassigned(parse(CASES[33]), "Važan tekst bez mjesta.")


def quoted_heading_lines(result: ParseResult) -> list[int]:
    return [item.line for item in result.diagnostics if item.code is DiagnosticCode.QUOTED_HEADING]


def test_case_34_stray_quotation_reports_the_hidden_article() -> None:
    result = parse(CASES[34])

    assert short_ids(result) == ["cl-1"]
    assert quoted_heading_lines(result) == [4]
    assert "Član 2." in result.law.articles[0].text


def test_case_35_every_quoted_heading_is_reported() -> None:
    result = parse(CASES[35])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert quoted_heading_lines(result) == [3, 6]
    assert "Član 7b." in result.law.articles[0].text


@pytest.mark.parametrize("number", [36, 37])
def test_cases_36_and_37_line_start_quotation_styles(number: int) -> None:
    result = parse(CASES[number])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert "Član 7b." in result.law.articles[0].text


def test_case_38_closed_inline_quotation_hides_nothing() -> None:
    result = parse(CASES[38])

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert quoted_heading_lines(result) == []


@pytest.mark.parametrize(
    ("number", "first", "second"),
    [(39, "ZAKON", "O FIKTIVNIM ZVONIMA"), (40, "ЗАКОН", "О ФИКТИВНИМ ЗВОНИМА")],
)
def test_cases_39_and_40_centered_law_title_stays_in_preamble(
    number: int, first: str, second: str
) -> None:
    law = parse(CASES[number]).law

    assert first in law.preamble
    assert second in law.preamble
    assert law.articles[0].structure_path == ()
    assert law.articles[0].title is None


def test_case_41_complete_law_title_keeps_the_division() -> None:
    division = parse(CASES[41]).law.articles[0].structure_path[0]

    assert (division.kind, division.label, division.title) == (
        StructureKind.DIVISION,
        "",
        "OPŠTE ODREDBE",
    )


def test_case_42_later_marker_keeps_the_list_open() -> None:
    points = parse(CASES[42]).law.articles[0].paragraphs[0].points

    assert [point.label for point in points] == ["a", "b"]
    assert "Zakona o zvonima," in points[0].text


def test_case_43_sentence_after_the_last_point_still_ends_the_list() -> None:
    points = parse(CASES[43]).law.articles[0].paragraphs[0].points

    assert points[-1].label == "b"
    assert points[-1].text == "drugo."


@pytest.mark.parametrize("line", ["Član 5 i", "Члан 5 и", "Član 5-i", "Član 5.i", "Član 5 I"])
def test_separated_conjunction_is_never_a_suffix(line: str) -> None:
    assert short_ids(parse(f"Član 1.\nPrvi.\n\n{line}\nDrugi.")) == ["cl-1"]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [("Član 5aaa", "cl-5aaa"), ("Члан 5аа.", "cl-5aa"), ("Član 5b", "cl-5b")],
)
def test_attached_suffix_accepts_up_to_three_letters(heading: str, expected: str) -> None:
    assert short_ids(parse(f"{heading}\nPrvi.")) == [expected]


@pytest.mark.parametrize("line", ["Član 5aaaa", "Član 5 aa", "Član 5-aa", "Član 5.aa"])
def test_longer_or_separated_suffixes_are_not_headings(line: str) -> None:
    assert short_ids(parse(f"Član 1.\nPrvi.\n\n{line}\nDrugi.")) == ["cl-1"]


def test_lowercase_heading_counts_after_blank_line() -> None:
    assert short_ids(parse("Član 1.\nPrvi.\n\nčlan 2.\nDrugi.")) == ["cl-1", "cl-2"]


@pytest.mark.parametrize(
    "line",
    [
        "Član 2. predmet zakona",
        "Član 2. Predmet zakona.",
        f"Član 2. {'P' * 121}",
    ],
)
def test_invalid_inline_titles_are_not_headings(line: str) -> None:
    assert short_ids(parse(f"Član 1.\nPrvi.\n\n{line}\nDrugi.")) == ["cl-1"]


def test_inline_title_needs_a_clear_start() -> None:
    assert short_ids(parse("Član 1.\nTekst bez kraja\nČlan 2. Naslov\nDrugi.")) == ["cl-1"]


def test_inline_title_with_dash() -> None:
    assert parse("Član 1 - Predmet zakona\nPrvi.").law.articles[0].title == "Predmet zakona"


@pytest.mark.parametrize(
    "quote",
    [
        "«Član 7a.\nDodani tekst.»",
        '"Član 7a.\nDodani tekst.\n\nČlan 7b.\nKraj."',
        "„GLAVA II\n\nČlan 7a.\nDodani tekst.”",
    ],
)
def test_quoted_blocks_stay_in_enclosing_article(quote: str) -> None:
    result = parse(f"Član 1.\nDodaje se:\n{quote}\n\nČlan 2.\nDrugi.")

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert "Član 7a." in result.law.articles[0].text
    assert result.law.articles[1].structure_path == ()
    expected = [DiagnosticCode.QUOTED_HEADING] * quote.count("Član 7")
    assert [item.code for item in result.diagnostics] == expected


def test_quoted_paragraph_markers_do_not_create_paragraphs() -> None:
    result = parse("Član 1.\n(1) Dodaje se:\n„(1) Novi stav.\n(2) Drugi novi stav.“\n(2) Stvarni.")

    assert paragraph_suffixes(result) == ["st-1", "st-2"]
    assert result.law.articles[0].paragraphs[1].text == "Stvarni."


@pytest.mark.parametrize("opener", ["„", "«", '"'])
def test_unterminated_quote_protects_only_its_first_line(opener: str) -> None:
    result = parse(f"Član 1.\n{opener}Član 7a.\nTekst.\n\nČlan 2.\nDrugi.")

    assert short_ids(result) == ["cl-1", "cl-2"]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.UNTERMINATED_QUOTE]


@pytest.mark.parametrize(
    ("heading", "kind"),
    [
        ("Glava II", StructureKind.CHAPTER),
        ("Poglavlje II", StructureKind.CHAPTER),
        ("Dio prvi", StructureKind.PART),
        ("Dio I", StructureKind.PART),
        ("Odjeljak A", StructureKind.SECTION),
        ("Глава II", StructureKind.CHAPTER),
        ("Поглавље II", StructureKind.CHAPTER),
        ("Дио први", StructureKind.PART),
        ("Одјељак А", StructureKind.SECTION),
    ],
)
def test_title_case_structure_keywords(heading: str, kind: StructureKind) -> None:
    found = parse(f"{heading}\n\nČlan 1.\nPrvi.").law.articles[0].structure_path[0]

    assert (found.kind, found.label) == (kind, heading)


@pytest.mark.parametrize(
    ("heading", "kind"),
    [
        ("GLAVA DRUGA", StructureKind.CHAPTER),
        ("GLAVA TREĆA", StructureKind.CHAPTER),
        ("GLAVA DVADESETA", StructureKind.CHAPTER),
        ("POGLAVLJE DRUGO", StructureKind.CHAPTER),
        ("POGLAVLJE TREĆE", StructureKind.CHAPTER),
        ("ODJELJAK DRUGI", StructureKind.SECTION),
        ("DIO DVADESETI", StructureKind.PART),
        ("ГЛАВА ДРУГА", StructureKind.CHAPTER),
        ("ПОГЛАВЉЕ ДРУГО", StructureKind.CHAPTER),
        ("ПОГЛАВЉЕ ТРЕЋЕ", StructureKind.CHAPTER),
        ("ОДЈЕЉАК ДРУГИ", StructureKind.SECTION),
        ("ДИО ДВАДЕСЕТИ", StructureKind.PART),
    ],
)
def test_ordinal_words_use_the_correct_gender(heading: str, kind: StructureKind) -> None:
    found = parse(f"{heading}\n\nČlan 1.\nPrvi.").law.articles[0].structure_path[0]

    assert (found.kind, found.label) == (kind, heading)


@pytest.mark.parametrize("heading", ["GLAVA DRUGI", "POGLAVLJE DRUGA", "ODJELJAK DRUGA"])
def test_ordinal_words_in_the_wrong_gender_are_not_keyword_headings(heading: str) -> None:
    path = parse(f"{heading}\n\nČlan 1.\nPrvi.").law.articles[0].structure_path

    assert [item.kind for item in path] == [StructureKind.DIVISION]
    assert path[0].label == ""


def test_division_sits_between_part_and_chapter() -> None:
    text = "DIO PRVI\n\nGLAVA I\n\nČlan 1.\nPrvi.\n\nII. NADZOR\n\nČlan 2.\nDrugi."

    articles = parse(text).law.articles

    assert [item.kind for item in articles[0].structure_path] == [
        StructureKind.PART,
        StructureKind.CHAPTER,
    ]
    assert [item.label for item in articles[1].structure_path] == ["DIO PRVI", "II"]


def test_roman_division_must_follow_a_blank_line() -> None:
    result = parse("Član 1.\nPrvi tekst.\nII. NADZOR\n\nČlan 2.\nDrugi.")

    assert result.law.articles[1].structure_path == ()
    assert "II. NADZOR" in result.law.articles[0].text


def test_uppercase_line_before_article_is_an_unnumbered_division() -> None:
    division = (
        parse("Član 1.\nPrvi.\n\nNADZOR\n\nČlan 2.\nDrugi.").law.articles[1].structure_path[0]
    )

    assert (division.kind, division.label, division.title) == (
        StructureKind.DIVISION,
        "",
        "NADZOR",
    )


@pytest.mark.parametrize("title", [METADATA.title, METADATA.title.upper(), "ЗАКОН О ЗВОНИМА"])
def test_law_title_above_first_article_stays_in_preamble(title: str) -> None:
    law = parse(f"{title}\nČlan 1.\nPrvi.").law

    assert law.articles[0].title is None
    assert law.articles[0].structure_path == ()
    assert law.preamble == title


def test_uppercase_line_starting_with_zakon_is_a_division_after_the_first_article() -> None:
    division = parse("Član 1.\nPrvi.\n\nZAKONSKE MJERE\n\nČlan 2.\nDrugi.").law.articles[1]

    assert [item.title for item in division.structure_path] == ["ZAKONSKE MJERE"]


@pytest.mark.parametrize("closing", ["Broj: 01-02/30", "PSBiH broj 12/30"])
def test_closing_line_is_never_the_title_of_a_structure_heading(closing: str) -> None:
    law = parse(f"Član 1.\nPrvi.\n\nGlava II\n{closing}").law

    assert law.closing_text == closing
    assert law.structure_headings[0].title is None
    assert_covered_exactly_once(law)


def test_three_lines_above_heading_are_not_a_title() -> None:
    result = parse("Član 1.\nPrvi.\n\nPrvi red\ndrugi red\ntreći red\nČlan 2.\nDrugi.")

    assert result.law.articles[1].title is None
    assert result.law.articles[0].text.endswith("treći red")


def test_parenthesized_title_spans_three_lines() -> None:
    article = parse("Član 1.\n(Prvi red\ndrugi red\ntreći red)\nTekst.").law.articles[0]

    assert article.title == "Prvi red drugi red treći red"


def test_parenthesized_text_over_three_lines_is_not_a_title() -> None:
    article = parse("Član 1.\n(Prvi red\ndrugi red\ntreći red\ncetvrti red)\nTekst.").law.articles[
        0
    ]

    assert article.title is None


@pytest.mark.parametrize("marker", ["-", "–", "—", "−", "•", "·"])
def test_dash_markers_with_a_space(marker: str) -> None:
    points = (
        parse(f"Član 1.\nUvod bez dvotačke\n{marker} tačka").law.articles[0].paragraphs[0].points
    )

    assert [point.kind for point in points] == [PointKind.DASH]


def test_tight_dash_needs_a_colon_or_a_dash_point() -> None:
    assert parse("Član 1.\nTekst bez dvotačke\n-prvo").law.articles[0].paragraphs[0].points == ()


@pytest.mark.parametrize(
    ("body", "labels"),
    [
        ("Značenje:\n2. prvo", []),
        ("Značenje:\n1. prvo,\n3. drugo.", ["1"]),
        ("Značenje:\n1) prvo,\n2. drugo.", ["1", "2"]),
    ],
)
def test_dotted_number_points_follow_strict_order(body: str, labels: list[str]) -> None:
    points = parse(f"Član 1.\n{body}").law.articles[0].paragraphs[0].points

    assert [point.label for point in points] == labels


@pytest.mark.parametrize(
    "line",
    ["Broj: 01-02/30", "Broj: 01-02/30 od 1. 2. 2030. godine", "Број: 01-02/30"],
)
def test_broj_with_registry_value_starts_closing(line: str) -> None:
    assert parse(f"Član 1.\nPrvi.\n\n{line}").law.closing_text == line


@pytest.mark.parametrize("line", ["Broj: 7 je dovoljan za rad.", "Broj: pet članova."])
def test_broj_in_a_sentence_stays_in_article(line: str) -> None:
    law = parse(f"Član 1.\nPrvi.\n\n{line}").law

    assert law.closing_text == ""
    assert law.articles[0].text.endswith(line)
