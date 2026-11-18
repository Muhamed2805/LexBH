"""Layouts that plain text exports of laws produce. Every legal text here is fictional."""

# ruff: noqa: RUF001

import pytest

from lexbh.ingestion import ArticlePoint, Jurisdiction, LawMetadata, ParseResult, parse_law

METADATA = LawMetadata(
    law_id="fiktivni-zakon", title="Fiktivni zakon", jurisdiction=Jurisdiction.BIH
)


def parse(text: str) -> ParseResult:
    return parse_law(text, METADATA)


def division_labels(text: str) -> list[str]:
    return [heading.label for heading in parse(text).law.structure_headings]


def article_titles(text: str) -> list[str | None]:
    return [article.title for article in parse(text).law.articles]


def point_labels(text: str) -> list[list[str]]:
    """Return the point labels of every paragraph of the first article."""
    paragraphs = parse(text).law.articles[0].paragraphs
    return [[point.label for point in paragraph.points] for paragraph in paragraphs]


@pytest.mark.parametrize("dash", ["-", "–", "—"])
def test_dashed_division_after_a_sentence_needs_no_blank_line(dash: str) -> None:
    text = f"Član 1.\nPrva odredba.\nIII {dash} IZMIŠLJENO ZVONO\nČlan 2.\nDruga odredba."

    first, second = parse(text).law.articles

    assert first.text.endswith("Prva odredba.")
    assert [(item.label, item.title) for item in second.structure_path] == [
        ("III", "IZMIŠLJENO ZVONO")
    ]


@pytest.mark.parametrize(
    "line",
    [
        "III - Izmišljeno zvono zvoni tiho",
        "II. NADZOR",
    ],
)
def test_only_an_uppercase_dashed_division_follows_a_sentence(line: str) -> None:
    text = f"Član 1.\nPrva.\n{line}\nDruga.\nIV - PRAVI NASLOV\nČlan 2.\nTreća."

    assert division_labels(text) == ["IV"]
    assert line in parse(text).law.articles[0].text


def test_dashed_division_needs_a_finished_sentence_above() -> None:
    text = "Član 1.\nPrva bez kraja\nIII - IZMIŠLJENO\nDruga.\nIV - PRAVI NASLOV\nČlan 2.\nTreća."

    assert division_labels(text) == ["IV"]


def test_dashed_division_inside_quoted_amending_text_is_ignored() -> None:
    text = (
        "Član 1.\nDodaje se tekst:\n„Prva.\nIII - IZMIŠLJENO\nDruga.“\n"
        "Završna rečenica.\nIV - PRAVI NASLOV\nČlan 2.\nTreća."
    )

    assert division_labels(text) == ["IV"]


@pytest.mark.parametrize("ending", [".", ";", ":"])
def test_title_directly_after_finished_text_belongs_to_the_next_article(ending: str) -> None:
    text = f"Član 1.\nPrva odredba{ending}\nProbni rad\nČlan 2.\nDruga odredba."

    first, second = parse(text).law.articles

    assert first.text.endswith(f"Prva odredba{ending}")
    assert second.title == "Probni rad"
    assert second.text.startswith("Probni rad\nČlan 2.")


def test_two_line_title_after_a_sentence_may_wrap_to_lowercase() -> None:
    text = "Član 1.\nPrva.\nPrvi red naslova\ndrugi red naslova\nČlan 2.\nDruga."

    assert article_titles(text) == [None, "Prvi red naslova drugi red naslova"]


def test_title_after_a_sentence_may_have_a_blank_line_below_it() -> None:
    text = "Član 1.\nPrva.\nPrvi red naslova\ndrugi red naslova\n\nČlan 2.\nDruga."

    assert article_titles(text) == [None, "Prvi red naslova drugi red naslova"]


def test_title_directly_after_a_structure_heading_is_kept() -> None:
    text = "Član 1.\nPrva.\nIII - IZMIŠLJENO\nProbni rad\nČlan 2.\nDruga."

    assert article_titles(text) == [None, "Probni rad"]


@pytest.mark.parametrize(
    "block",
    [
        "mala slova na početku",
        "Naslov sa zarezom,",
        "Naslov sa tačkom i zarezom;",
        "Naslov sa dvotačkom:",
        "Naslov sa tačkom.",
        "Zarez iznad,\nNaslov",
        "(1) Izmišljeni stav",
        "a) izmišljena tačka",
        "- izmišljena alineja",
        "GLAVA I",
        "Naslov\na. izmišljena tačka",
        "Naslov\n1. izmišljena tačka",
        "Naslov\n- izmišljena alineja",
        "Prvi red\ndrugi red\ntreći red",
    ],
)
def test_invalid_block_after_a_sentence_is_not_a_title(block: str) -> None:
    text = f"Član 1.\nPrva.\n{block}\nČlan 2.\nDruga.\nPravi naslov\nČlan 3.\nTreća."

    assert article_titles(text) == [None, None, "Pravi naslov"]


def test_text_directly_under_a_heading_stays_in_that_article() -> None:
    text = "Član 1.\nTekst bez tačke\nČlan 2.\nDruga.\nPravi naslov\nČlan 3.\nTreća."

    law = parse(text).law

    assert law.articles[0].text.endswith("Tekst bez tačke")
    assert [article.title for article in law.articles] == [None, None, "Pravi naslov"]


def test_division_title_continues_on_a_second_uppercase_line() -> None:
    text = (
        "Član 1.\nPrva.\n\nVIII - IZMIŠLJENI IZUMI I\nTEHNIČKA ZVONA\n"
        "Postupak sa zvonom\nČlan 2.\nDruga."
    )

    result = parse(text)
    second = result.law.articles[1]

    assert second.structure_path[-1].title == "IZMIŠLJENI IZUMI I TEHNIČKA ZVONA"
    assert second.title == "Postupak sa zvonom"
    assert result.law.unassigned == ()
    assert result.diagnostics == ()


def test_division_title_takes_only_one_extra_line() -> None:
    text = "Član 1.\nPrva.\n\nII - PRVI RED\nDRUGI RED\nTREĆI RED\nČlan 2.\nDruga."

    second = parse(text).law.articles[1]

    assert second.structure_path[-1].title == "PRVI RED DRUGI RED"
    assert second.title == "TREĆI RED"


def test_structure_heading_does_not_continue_a_division_title() -> None:
    text = (
        "Član 1.\nPrva.\n\nI - PRVI RED\nDRUGI RED\nČlan 2.\nDruga.\n\n"
        "II - TREĆI RED\nGLAVA I\nČlan 3.\nTreća."
    )

    headings = parse(text).law.structure_headings

    assert [(item.label, item.title) for item in headings] == [
        ("I", "PRVI RED DRUGI RED"),
        ("II", "TREĆI RED"),
        ("GLAVA I", None),
    ]


def test_quoted_line_does_not_continue_a_division_title() -> None:
    text = (
        "I - PRVI RED\nDRUGI RED\nČlan 1.\nPrva.\n\n"
        "II - TREĆI RED\nČETVRTI „RED\nPETI“ RED\n\nČlan 2.\nDruga."
    )

    headings = parse(text).law.structure_headings

    assert [item.title for item in headings] == ["PRVI RED DRUGI RED", "TREĆI RED"]


def test_closing_line_does_not_continue_a_division_title() -> None:
    text = "I - PRVI RED\nDRUGI RED\nČlan 1.\nPrva.\n\nII - TREĆI RED\nBROJ: 01-02/30"

    law = parse(text).law

    assert [item.title for item in law.structure_headings] == [
        "PRVI RED DRUGI RED",
        "TREĆI RED",
    ]
    assert law.closing_text == "BROJ: 01-02/30"


@pytest.mark.parametrize(
    "items",
    [
        "a. prva;\nb. druga;\nc. treća.",
        "a.prva;\nb.druga;\nc.treća.",
        "a. prva;\n\nb. druga;\n\nc. treća.",
    ],
)
def test_dotted_letters_are_points(items: str) -> None:
    assert point_labels(f"Član 1.\n(1) Uvod:\n{items}") == [["a", "b", "c"]]


def test_dotted_letters_have_the_same_ids_as_parenthesized_letters() -> None:
    dotted = parse("Član 1.\n(1) Uvod:\na. prva;\nb. druga.").law.articles[0]
    parenthesized = parse("Član 1.\n(1) Uvod:\na) prva;\nb) druga.").law.articles[0]

    assert [point.id for point in dotted.paragraphs[0].points] == [
        point.id for point in parenthesized.paragraphs[0].points
    ]
    assert [point.text for point in dotted.paragraphs[0].points] == ["prva;", "druga."]


@pytest.mark.parametrize(
    ("items", "labels"),
    [
        ("a. prva;\nb. druga;\nc. treća;\nd. četvrta.", ["a", "b", "c", "d"]),
        ("a. prva;\nb. druga;\nc. treća;\nč. četvrta.", ["a", "b", "c", "č"]),
        ("а. прва;\nб. друга;\nв. трећа.", ["a", "b", "v"]),
    ],
)
def test_dotted_letters_follow_the_alphabet_of_the_list(items: str, labels: list[str]) -> None:
    assert point_labels(f"Član 1.\n(1) Uvod:\n{items}") == [labels]


def test_skipped_letter_continues_the_previous_point() -> None:
    article = parse("Član 1.\n(1) Uvod:\na. prva;\nc. preskočena;\nb. druga.").law.articles[0]

    first, second = article.paragraphs[0].points
    assert (first.label, second.label) == ("a", "b")
    assert first.text == "prva;\nc. preskočena;"


@pytest.mark.parametrize(
    "line",
    [
        "b. pogrešan početak.",
        "a.d. Izmišljeno zvono posluje.",
        "a. d. Izmišljeno zvono posluje.",
        "a.5 izmišljenih zvona.",
        "A. Izmišljenić potpisuje.",
    ],
)
def test_text_that_only_resembles_a_dotted_letter_is_not_a_point(line: str) -> None:
    text = f"Član 1.\n(1) Uvod:\n{line}\n(2) Uvod:\na. prva;\nb. druga."

    assert point_labels(text) == [[], ["a", "b"]]


def test_lone_dotted_letter_after_a_sentence_is_plain_text() -> None:
    text = "Član 1.\n(1) Izmišljeni citat iz člana 5.\na. nastavak citata.\n(2) Uvod:\na. prva."

    assert point_labels(text) == [[], ["a"]]


def test_abbreviation_with_the_next_letter_is_not_a_point() -> None:
    text = "Član 1.\n(1) Uvod:\na. prva;\nb. druga;\nc.d. Izmišljeno zvono."

    assert point_labels(text) == [["a", "b"]]


def test_next_number_needs_no_space_after_its_dot() -> None:
    article = parse("Član 1.\n(1) Uvod:\n1. prva,\n2.druga,\n3. treća.").law.articles[0]

    points = article.paragraphs[0].points
    assert [point.label for point in points] == ["1", "2", "3"]
    assert points[1].text == "druga,"


@pytest.mark.parametrize("wrapped", ["38. stav 5.),", "30.)", "38.stav 5.),"])
def test_wrapped_citation_inside_a_numbered_list_is_a_continuation(wrapped: str) -> None:
    text = f"Član 1.\n(1) Uvod:\n1. prva (izmišljeni član\n{wrapped}\n2.druga."

    points = parse(text).law.articles[0].paragraphs[0].points

    assert [point.label for point in points] == ["1", "2"]
    assert wrapped in points[0].text


@pytest.mark.parametrize("line", ["2.5 posto izmišljene stope,", "2.03.2030. godine,"])
def test_decimal_or_date_is_not_the_next_number(line: str) -> None:
    text = f"Član 1.\n(1) Uvod:\n1. prva\n{line}\n2.druga."

    first, second = parse(text).law.articles[0].paragraphs[0].points

    assert (first.label, second.label) == ("1", "2")
    assert first.text == f"prva\n{line}"


def test_number_without_a_space_cannot_start_a_list() -> None:
    text = "Član 1.\n(1) Uvod:\n1.prva.\n(2) Uvod:\n1. prva;\n2.druga."

    assert point_labels(text) == [[], ["1", "2"]]


CITATION_ENDINGS = """
    član člana članu članom članova članovima čl čl.
    članak članka članku
    stav stava stavu stavom stavova st st.
    stavak stavka stavku
    tačka tačke tački tačku tačkom tač tač.
    točka točke točki točku točkom
    alineja alineje alineji alineju alinejom al al.
    broj broja br br.
    члан члана члану чланом чланова члановима чл чл.
    чланак чланка чланку
    став става ставу ставом ставова ст ст.
    ставак ставка ставку
    тачка тачке тачки тачку тачком тач тач.
    точка точке точки точку точком
    алинеја алинеје алинеји алинеју алинејом ал ал.
    број броја бр бр.
    ČLAN Član STAVA TAČKE ČL. ЧЛАН Члан СТАВА ТАЧКЕ ЧЛ.
"""
CITATION_WORDS = CITATION_ENDINGS.split()


def first_paragraph_points(text: str) -> tuple[ArticlePoint, ...]:
    return parse(text).law.articles[0].paragraphs[0].points


@pytest.mark.parametrize("word", CITATION_WORDS)
def test_number_after_a_citation_word_continues_the_point(word: str) -> None:
    text = f"Član 1.\n(1) Kazni se:\n1. ko krši {word}\n2. ovog zakona,\n2. ko ne prijavi."

    first, second = first_paragraph_points(text)

    assert first.text == f"ko krši {word}\n2. ovog zakona,"
    assert (second.label, second.text) == ("2", "ko ne prijavi.")


@pytest.mark.parametrize("word", CITATION_WORDS)
def test_letter_after_a_citation_word_continues_the_point(word: str) -> None:
    text = f"Član 1.\n(1) Kazni se:\na. ko krši {word}\nb. ovog stava;\nb. ko ne prijavi."

    first, second = first_paragraph_points(text)

    assert first.text == f"ko krši {word}\nb. ovog stava;"
    assert (second.label, second.text) == ("b", "ko ne prijavi.")


def test_wrapped_citation_with_the_next_number_inside_parentheses() -> None:
    items = "\n".join(f"{number}. izmišljena obaveza," for number in range(1, 37))
    text = (
        f"Član 1.\n(1) Kazni se:\n{items}\n37. ko krši pravilo (član\n38. stav 5.),\n"
        "38. ko ne prijavi."
    )

    points = first_paragraph_points(text)

    assert [point.label for point in points] == [str(number) for number in range(1, 39)]
    assert points[36].text == "ko krši pravilo (član\n38. stav 5.),"
    assert points[37].text == "ko ne prijavi."


def test_wrapped_citation_with_the_next_letter() -> None:
    text = "Član 1.\n(1) Kazni se:\na. ko krši odredbu iz tačke\nb. ovog stava;\nb. ko ne prijavi."

    first, second = first_paragraph_points(text)

    assert first.text == "ko krši odredbu iz tačke\nb. ovog stava;"
    assert (second.label, second.text) == ("b", "ko ne prijavi.")


@pytest.mark.parametrize(
    ("wrapped", "next_item"),
    [
        ("2.ovog zakona,", "2. ko ne prijavi."),
        ("2.) ovog zakona,", "2. ko ne prijavi."),
    ],
)
def test_other_dotted_number_forms_wrap_a_citation(wrapped: str, next_item: str) -> None:
    text = f"Član 1.\n(1) Kazni se:\n1. ko krši član\n{wrapped}\n{next_item}"

    first, second = first_paragraph_points(text)

    assert first.text == f"ko krši član\n{wrapped}"
    assert (second.label, second.text) == ("2", "ko ne prijavi.")


def test_letter_without_a_space_wraps_a_citation() -> None:
    text = "Član 1.\n(1) Kazni se:\na. ko krši tačku\nb.ovog stava;\nb. ko ne prijavi."

    first, second = first_paragraph_points(text)

    assert first.text == "ko krši tačku\nb.ovog stava;"
    assert (second.label, second.text) == ("b", "ko ne prijavi.")


def test_cyrillic_wrapped_citations_continue_their_points() -> None:
    numbers = "Члан 1.\n(1) Кажњава се:\n1. ко крши члан\n2. овог закона,\n2. ко не пријави."
    letters = "Члан 1.\n(1) Кажњава се:\nа. ко крши тачку\nб. овог става;\nб. ко не пријави."

    first_number, second_number = first_paragraph_points(numbers)
    first_letter, second_letter = first_paragraph_points(letters)

    assert first_number.text == "ко крши члан\n2. овог закона,"
    assert second_number.text == "ко не пријави."
    assert first_letter.text == "ко крши тачку\nб. овог става;"
    assert (second_letter.label, second_letter.text) == ("b", "ко не пријави.")


@pytest.mark.parametrize("opening", ["(1) Kazni se:", "Kazni se:"])
def test_citation_continues_across_a_blank_line(opening: str) -> None:
    text = f"Član 1.\n{opening}\n1. ko krši član\n\n2. ovog zakona,\n2. ko ne prijavi."

    article = parse(text).law.articles[0]
    first, second = article.paragraphs[0].points

    assert len(article.paragraphs) == 1
    assert first.text == "ko krši član\n\n2. ovog zakona,"
    assert (second.label, second.text) == ("2", "ko ne prijavi.")


def test_citation_above_a_blank_line_is_not_a_following_point() -> None:
    text = "Član 1.\n(1) Uvod:\n1. prva.\nNapomena iz člana\n\n2. ovog zakona,"

    points = first_paragraph_points(text)

    assert [(point.label, point.text) for point in points] == [("1", "prva.")]


@pytest.mark.parametrize(
    "ending",
    [
        "ustav",
        "sastav",
        "ustava",
        "sastavu",
        "članstvo",
        "pod-član",
        "brojač",
        "устав",
        "састав",
        "člana.",
        "stavu.",
        "član,",
        "broj;",
    ],
)
def test_other_line_endings_keep_the_next_point_separate(ending: str) -> None:
    text = f"Član 1.\n(1) Uvod:\n1. izmišljeni {ending}\n2. drugo zvono"

    first, second = first_paragraph_points(text)

    assert first.text == f"izmišljeni {ending}"
    assert (second.label, second.text) == ("2", "drugo zvono")


@pytest.mark.parametrize("ending", ["ustav", "sastav", "устав"])
def test_longer_word_keeps_the_next_letter_separate(ending: str) -> None:
    text = f"Član 1.\n(1) Uvod:\na. izmišljeni {ending}\nb. drugo zvono"

    assert point_labels(text) == [["a", "b"]]


def test_unpunctuated_list_items_stay_separate_points() -> None:
    text = "Član 1.\n(1) Uvod:\n1. prvo zvono\n2. drugo zvono"

    first, second = first_paragraph_points(text)

    assert (first.label, first.text) == ("1", "prvo zvono")
    assert (second.label, second.text) == ("2", "drugo zvono")


ROMAN_RANGES = ["I - II", "V - VIII", "I – II", "V — VIII", "X - XL", "II - III - IV", "І - ІІ"]


@pytest.mark.parametrize("line", ROMAN_RANGES)
def test_roman_numeral_range_stays_article_text(line: str) -> None:
    text = f"Član 1.\nPrva.\n\n{line}\nDruga rečenica.\n\nČlan 2.\nTreća."

    law = parse(text).law

    assert law.structure_headings == ()
    assert law.unassigned == ()
    assert f"{line}\nDruga rečenica." in law.articles[0].text


@pytest.mark.parametrize("line", ROMAN_RANGES)
def test_roman_numeral_range_above_a_heading_is_not_a_title(line: str) -> None:
    law = parse(f"Član 1.\nPrva.\n\n{line}\nČlan 2.\nTreća.").law

    assert law.structure_headings == ()
    assert law.articles[1].title is None
    assert law.articles[0].text.endswith(line)


def test_roman_numeral_range_after_a_sentence_stays_article_text() -> None:
    law = parse("Član 1.\nPrva.\nV - VIII\nDruga.\n\nČlan 2.\nTreća.").law

    assert law.structure_headings == ()
    assert "V - VIII" in law.articles[0].text


def test_roman_numeral_range_does_not_continue_a_division_title() -> None:
    text = "Član 1.\nPrva.\n\nIII - NADZOR\nV - VIII\nČlan 2.\nDruga."

    headings = parse(text).law.structure_headings

    assert [(item.label, item.title) for item in headings] == [("III", "NADZOR")]


@pytest.mark.parametrize(
    ("line", "label", "title"),
    [
        ("III - NADZOR", "III", "NADZOR"),
        ("V - VIII ODREDBE", "V", "VIII ODREDBE"),
        ("I - II DIO", "I", "II DIO"),
    ],
)
def test_division_with_a_real_title_word_is_kept(line: str, label: str, title: str) -> None:
    headings = parse(f"Član 1.\nPrva.\n\n{line}\n\nČlan 2.\nDruga.").law.structure_headings

    assert [(item.label, item.title) for item in headings] == [(label, title)]
