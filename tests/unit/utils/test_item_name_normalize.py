"""Unit tests for app/utils/item_name_normalize.py.

Implements tests/unit/utils/item_name_normalize.cases.md (revision 3), one test
per case (INN-N-69 / INN-N-70 are parametrized over their listed inputs, one
param id per input). Pure function: no database, no mocks (spec: "Externals to
mock: none"). Every non-ASCII code point is written with an explicit escape.
"""
import pytest

from app.utils.item_name_normalize import (
    MIN_SIMILAR_NAME_LENGTH,
    SIMILARITY_THRESHOLD,
    normalize_item_name,
)

# --------------------------------------------------------------------------- #
# Conventions -> helpers
# --------------------------------------------------------------------------- #

# Convention "f(x)" = normalize_item_name(x)
f = normalize_item_name


# Convention "returns exactly S" = result == S and type(result) is str
def assert_exact(result, expected):
    assert result == expected
    assert type(result) is str


# Convention "Code points" (all from the spec Notes)
CHAL = "\u099a\u09be\u09b2"          # U+09BE Mc
CHUL = "\u099a\u09c1\u09b2"          # U+09C1 Mn
CHIL = "\u099a\u09bf\u09b2"          # U+09BF Mc
CHOL = "\u099a\u09b2"                # letters only
RAB_ZWJ = "\u09b0\u200d\u09cd\u09af\u09be\u09ac"
RAB = "\u09b0\u09cd\u09af\u09be\u09ac"
PHRASE = "\u09ae\u09bf\u09a8\u09bf\u0995\u09c7\u099f \u099a\u09be\u09b2 \u09eb \u0995\u09c7\u099c\u09bf"
KEJI_5 = "\u09eb \u0995\u09c7\u099c\u09bf"
CAFE_PRE = "caf\u00e9"
CAFE_DEC = "cafe\u0301"
FW_BOLT = "\uff22\uff4f\uff4c\uff54"
FW_10MM = "\uff11\uff10 \uff4d\uff4d"
X_SQUARED = "x\u00b2"
FI_LIGATURE_FILE = "\ufb01le"
NBSP = "\u00a0"
SOFT_HYPHEN = "\u00ad"
ZWNJ = "\u200c"
ZWSP = "\u200b"
ENCLOSING_CIRCLE = "\u20dd"          # category Me
Q_ACUTE = "q\u0301"

BUG_180 = "BUG-180: Item-name normalization deletes Bengali vowel signs / combining marks"
BUG_181 = "BUG-181: Item-name normalization applies no Unicode normalization"
BUG_182 = "BUG-182: Number+unit gluing runs before punctuation removal"
BUG_183 = "BUG-183: Underscore kept while all other punctuation becomes a space"


# --------------------------------------------------------------------------- #
# normalize_item_name
# --------------------------------------------------------------------------- #


def test_inn_n_01__empty_string_returns_empty():
    """INN-N-01 \u2014 f("") returns exactly "".
    Rules: R1."""
    assert_exact(f(""), "")


def test_inn_n_02__none_returns_empty():
    """INN-N-02 \u2014 f(None) returns exactly "" without raising.
    Rules: R1; Errors (none)."""
    assert_exact(f(None), "")


def test_inn_n_03__single_char_kept():
    """INN-N-03 \u2014 non-empty side of R1: f("a") returns exactly "a".
    Rules: R1."""
    assert_exact(f("a"), "a")


def test_inn_n_04__uppercase_lowered():
    """INN-N-04 \u2014 f("SCREW") returns exactly "screw".
    Rules: R2."""
    assert_exact(f("SCREW"), "screw")


def test_inn_n_05__lower_not_casefold():
    """INN-N-05 \u2014 sharp s is kept (lower, not casefold).
    Rules: R2."""
    assert_exact(f("Stra\u00dfe"), "stra\u00dfe")


def test_inn_n_06__precomposed_accent_kept():
    """INN-N-06 \u2014 f("Caf\u00e9") (precomposed) returns exactly "caf\u00e9", length 4.
    Rules: R2."""
    assert_exact(f("Caf\u00e9"), "caf\u00e9")


@pytest.mark.xfail(strict=True, reason=BUG_181)
def test_inn_n_07__decomposed_accent_equals_precomposed():
    """INN-N-07 \u2014 decomposed "caf\u00e9" normalizes to precomposed "caf\u00e9", same as precomposed input.
    Rules: R2a [BUG-181]."""
    assert f(CAFE_DEC) == "caf\u00e9"
    assert f(CAFE_DEC) == f(CAFE_PRE)


@pytest.mark.xfail(strict=True, reason=BUG_181)
def test_inn_n_08__full_width_letters_folded():
    """INN-N-08 \u2014 full-width "\uff22\uff4f\uff4c\uff54" returns exactly "bolt".
    Rules: R2a [BUG-181]."""
    assert_exact(f(FW_BOLT), "bolt")


@pytest.mark.xfail(strict=True, reason=BUG_181)
def test_inn_n_09__superscript_folded():
    """INN-N-09 \u2014 "x\u00b2" returns exactly "x2".
    Rules: R2a [BUG-181]."""
    assert_exact(f(X_SQUARED), "x2")


@pytest.mark.xfail(strict=True, reason=BUG_181)
def test_inn_n_10__ligature_folded():
    """INN-N-10 \u2014 ligature "\ufb01le" returns exactly "file".
    Rules: R2a [BUG-181]."""
    assert_exact(f(FI_LIGATURE_FILE), "file")


@pytest.mark.xfail(strict=True, reason=BUG_181)
def test_inn_n_11__full_width_number_and_unit_glued():
    """INN-N-11 \u2014 full-width "\uff11\uff10 \uff4d\uff4d" returns exactly "10mm".
    Rules: R2a, R5 [BUG-181]."""
    assert_exact(f(FW_10MM), "10mm")


def test_inn_n_12__trim_and_collapse_spaces():
    """INN-N-12 \u2014 f("  Screw   Driver  ") returns exactly "screw driver".
    Rules: R3."""
    assert_exact(f("  Screw   Driver  "), "screw driver")


def test_inn_n_13__tab_and_newline_become_space():
    """INN-N-13 \u2014 f("x\\tY\\nz") returns exactly "x y z".
    Rules: R3."""
    assert_exact(f("x\tY\nz"), "x y z")


def test_inn_n_14__nbsp_becomes_plain_space():
    """INN-N-14 \u2014 NBSP inside becomes U+0020; no NBSP remains.
    Rules: R3."""
    result = f("a" + NBSP + "b")
    assert_exact(result, "a b")
    assert NBSP not in result


def test_inn_n_15__single_space_kept():
    """INN-N-15 \u2014 a single space (other side of "run") is kept, not removed.
    Rules: R3."""
    assert_exact(f("a b"), "a b")


def test_inn_n_16__mixed_whitespace_kinds():
    """INN-N-16 \u2014 mixed whitespace collapses; result has the Returns whitespace shape.
    Rules: R3; Returns."""
    result = f(NBSP + "\tA\u3000\u3000B\r\n")
    assert_exact(result, "a b")
    assert result == result.strip()
    assert "  " not in result
    assert all(ch == " " for ch in result if ch.isspace())


def test_inn_n_17__spaces_only_returns_empty():
    """INN-N-17 \u2014 f("  ") returns exactly "".
    Rules: R4."""
    assert_exact(f("  "), "")


def test_inn_n_18__mixed_whitespace_only_returns_empty():
    """INN-N-18 \u2014 whitespace-only mixed input returns exactly "".
    Rules: R4."""
    assert_exact(f(" \t\n" + NBSP + " "), "")


def test_inn_n_19__not_whitespace_only():
    """INN-N-19 \u2014 f(" a ") returns exactly "a".
    Rules: R4."""
    assert_exact(f(" a "), "a")


def test_inn_n_20__one_letter_unit_at_end_glued():
    """INN-N-20 \u2014 f("Screw Driver 22 m") returns exactly "screw driver 22m".
    Rules: R5."""
    assert_exact(f("Screw Driver 22 m"), "screw driver 22m")


def test_inn_n_21__unit_followed_by_space_glued():
    """INN-N-21 \u2014 f("10 mm Bolt") returns exactly "10mm bolt".
    Rules: R5."""
    assert_exact(f("10 mm Bolt"), "10mm bolt")


def test_inn_n_22__uppercase_unit_m_glued():
    """INN-N-22 \u2014 f("22 M") returns exactly "22m".
    Rules: R5."""
    assert_exact(f("22 M"), "22m")


def test_inn_n_23__uppercase_unit_kg_glued():
    """INN-N-23 \u2014 f("10 KG") returns exactly "10kg".
    Rules: R5."""
    assert_exact(f("10 KG"), "10kg")


def test_inn_n_24__three_letter_word_glued():
    """INN-N-24 \u2014 f("5 kgs") returns exactly "5kgs".
    Rules: R5."""
    assert_exact(f("5 kgs"), "5kgs")


def test_inn_n_25__four_letter_word_glued():
    """INN-N-25 \u2014 boundary: exactly 4 letters, f("5 pack") returns exactly "5pack".
    Rules: R5."""
    assert_exact(f("5 pack"), "5pack")


def test_inn_n_26__five_letter_word_not_glued():
    """INN-N-26 \u2014 boundary: exactly 5 letters, f("5 packs") returns exactly "5 packs".
    Rules: R5."""
    assert_exact(f("5 packs"), "5 packs")


def test_inn_n_27__six_letter_word_not_glued():
    """INN-N-27 \u2014 f("22 metres") returns exactly "22 metres".
    Rules: R5."""
    assert_exact(f("22 metres"), "22 metres")


def test_inn_n_28__short_word_ended_by_punctuation_glued():
    """INN-N-28 \u2014 f("5 kg-pack") returns exactly "5kg pack".
    Rules: R5."""
    assert_exact(f("5 kg-pack"), "5kg pack")


def test_inn_n_29__short_word_followed_by_digit_not_glued():
    """INN-N-29 \u2014 f("5 kg2") returns exactly "5 kg2".
    Rules: R5."""
    assert_exact(f("5 kg2"), "5 kg2")


def test_inn_n_30__short_word_at_end_glued():
    """INN-N-30 \u2014 f("5 kg") returns exactly "5kg".
    Rules: R5."""
    assert_exact(f("5 kg"), "5kg")


def test_inn_n_31__every_occurrence_glued():
    """INN-N-31 \u2014 f("10 mm, 20 mm") returns exactly "10mm 20mm".
    Rules: R5."""
    assert_exact(f("10 mm, 20 mm"), "10mm 20mm")


def test_inn_n_32__chained_numbers_glued():
    """INN-N-32 \u2014 f("2 x 3 m") returns exactly "2x 3m".
    Rules: R5."""
    assert_exact(f("2 x 3 m"), "2x 3m")


def test_inn_n_33__non_unit_word_glued_pro():
    """INN-N-33 \u2014 any short word is glued (intended per Q4): "iphone 15pro max".
    Rules: R5."""
    assert_exact(f("iPhone 15 pro max"), "iphone 15pro max")


def test_inn_n_34__non_unit_word_glued_and():
    """INN-N-34 \u2014 any short word is glued (intended per Q4): "size 10and up".
    Rules: R5."""
    assert_exact(f("Size 10 and up"), "size 10and up")


def test_inn_n_35__number_ends_alphanumeric_token():
    """INN-N-35 \u2014 f("Model X5 pro") returns exactly "model x5pro".
    Rules: R5."""
    assert_exact(f("Model X5 pro"), "model x5pro")


def test_inn_n_36__no_number_before_short_word():
    """INN-N-36 \u2014 f("Model X pro") returns exactly "model x pro" (not glued).
    Rules: R5."""
    assert_exact(f("Model X pro"), "model x pro")


def test_inn_n_37__decimal_number_glues_last_group():
    """INN-N-37 \u2014 f("1.5 mm") returns exactly "1 5mm".
    Rules: R5, R6."""
    assert_exact(f("1.5 mm"), "1 5mm")


def test_inn_n_38__arabic_indic_digit_glued():
    """INN-N-38 \u2014 f("\u0662 kg") returns exactly "\u0662kg".
    Rules: R5."""
    assert_exact(f("\u0662 kg"), "\u0662kg")


def test_inn_n_39__bengali_digit_glued():
    """INN-N-39 \u2014 f("\u09eb kg") returns exactly "\u09ebkg".
    Rules: R5."""
    assert_exact(f("\u09eb kg"), "\u09ebkg")


def test_inn_n_40__bengali_unit_not_glued():
    """INN-N-40 \u2014 bug-independent part: a number is not glued to a non-ASCII word.
    Rules: R5."""
    result = f(KEJI_5)
    assert result.startswith("\u09eb \u0995")
    assert "\u09eb\u0995" not in result


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_41__bengali_unit_marks_kept():
    """INN-N-41 \u2014 f("\u09eb \u0995\u09c7\u099c\u09bf") returns exactly "\u09eb \u0995\u09c7\u099c\u09bf".
    Rules: R5, R6a [BUG-180]."""
    assert_exact(f(KEJI_5), "\u09eb \u0995\u09c7\u099c\u09bf")


@pytest.mark.xfail(strict=True, reason=BUG_182)
def test_inn_n_42__hyphen_separator_glued():
    """INN-N-42 \u2014 f("Bolt 10-mm") returns exactly "bolt 10mm".
    Rules: R5a [BUG-182]."""
    assert_exact(f("Bolt 10-mm"), "bolt 10mm")


@pytest.mark.xfail(strict=True, reason=BUG_182)
def test_inn_n_43__dot_separator_glued():
    """INN-N-43 \u2014 f("Bolt 10.mm") returns exactly "bolt 10mm".
    Rules: R5a [BUG-182]."""
    assert_exact(f("Bolt 10.mm"), "bolt 10mm")


@pytest.mark.xfail(strict=True, reason=BUG_182)
def test_inn_n_44__spaced_slash_separator_glued():
    """INN-N-44 \u2014 f("Bolt 10 / mm") returns exactly "bolt 10mm".
    Rules: R5a [BUG-182]."""
    assert_exact(f("Bolt 10 / mm"), "bolt 10mm")


def test_inn_n_45__bug_independent_variants_glued():
    """INN-N-45 \u2014 "Bolt 10mm" and "Bolt 10 mm" both return exactly "bolt 10mm".
    Rules: R5a, R5."""
    assert_exact(f("Bolt 10mm"), "bolt 10mm")
    assert_exact(f("Bolt 10 mm"), "bolt 10mm")


@pytest.mark.xfail(strict=True, reason=BUG_182)
def test_inn_n_46__parentheses_glued():
    """INN-N-46 \u2014 f("Size 5 (pack)") returns exactly "size 5pack".
    Rules: R5a [BUG-182]."""
    assert_exact(f("Size 5 (pack)"), "size 5pack")


@pytest.mark.xfail(strict=True, reason=f"{BUG_182}; {BUG_183}")
def test_inn_n_47__underscore_separator_glued():
    """INN-N-47 \u2014 f("Bolt 10_mm") returns exactly "bolt 10mm".
    Rules: R5a, R6c [BUG-182, BUG-183]."""
    assert_exact(f("Bolt 10_mm"), "bolt 10mm")


def test_inn_n_48__hyphen_becomes_space():
    """INN-N-48 \u2014 f("Screw-Driver") returns exactly "screw driver".
    Rules: R6."""
    assert_exact(f("Screw-Driver"), "screw driver")


def test_inn_n_49__dot_becomes_space():
    """INN-N-49 \u2014 f("Screw.Driver") returns exactly "screw driver".
    Rules: R6."""
    assert_exact(f("Screw.Driver"), "screw driver")


def test_inn_n_50__parentheses_become_space():
    """INN-N-50 \u2014 f("Bolt (M8)") returns exactly "bolt m8".
    Rules: R6."""
    assert_exact(f("Bolt (M8)"), "bolt m8")


def test_inn_n_51__symbols_become_space():
    """INN-N-51 \u2014 f("A&B+C@D#E") returns exactly "a b c d e".
    Rules: R6."""
    assert_exact(f("A&B+C@D#E"), "a b c d e")


def test_inn_n_52__enclosing_mark_not_kept():
    """INN-N-52 \u2014 enclosing mark (Me) becomes a space: "a b".
    Rules: R6."""
    assert_exact(f("a" + ENCLOSING_CIRCLE + "b"), "a b")


def test_inn_n_53__zero_width_space_becomes_space():
    """INN-N-53 \u2014 ZWSP is not a deleted joiner: "a b", not "ab".
    Rules: R6, R6b."""
    assert_exact(f("a" + ZWSP + "b"), "a b")


def test_inn_n_54__bengali_letters_only_kept():
    """INN-N-54 \u2014 bug-independent part: f("\u099a\u09b2") returns exactly "\u099a\u09b2".
    Rules: R6, R6a."""
    assert_exact(f(CHOL), "\u099a\u09b2")


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_55__vowel_sign_mc_kept():
    """INN-N-55 \u2014 f("\u099a\u09be\u09b2") returns exactly "\u099a\u09be\u09b2".
    Rules: R6a [BUG-180]."""
    assert_exact(f(CHAL), "\u099a\u09be\u09b2")


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_56__vowel_sign_words_stay_distinct():
    """INN-N-56 \u2014 "\u099a\u09be\u09b2", "\u099a\u09c1\u09b2", "\u099a\u09bf\u09b2" give three different results.
    Rules: R6a [BUG-180]."""
    chal, chul, chil = f(CHAL), f(CHUL), f(CHIL)
    assert chul == "\u099a\u09c1\u09b2"
    assert chil == "\u099a\u09bf\u09b2"
    assert chal != chul
    assert chal != chil
    assert chul != chil


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_57__bengali_phrase_unchanged():
    """INN-N-57 \u2014 f(PHRASE) returns exactly PHRASE.
    Rules: R6a [BUG-180]."""
    assert_exact(f(PHRASE), PHRASE)


@pytest.mark.xfail(strict=True, reason=f"{BUG_180}; {BUG_182}")
def test_inn_n_58__short_word_followed_by_mark_not_glued():
    """INN-N-58 \u2014 f("5 kq\u0301") returns exactly "5 kq\u0301" (mark kept, not glued).
    Rules: R6a, R5 [BUG-180; BUG-182]."""
    assert_exact(f("5 k" + Q_ACUTE), "5 k" + Q_ACUTE)


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_59__mn_mark_on_ascii_letter_kept():
    """INN-N-59 \u2014 f("q\u0301") returns exactly "q\u0301".
    Rules: R6a [BUG-180]."""
    assert_exact(f(Q_ACUTE), Q_ACUTE)


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_60__zwj_inside_conjunct_deleted():
    """INN-N-60 \u2014 "\u09b0\u200d\u09cd\u09af\u09be\u09ac" (with ZWJ) gives "\u09b0\u09cd\u09af\u09be\u09ac", same as without ZWJ.
    Rules: R6b [BUG-180]."""
    assert f(RAB_ZWJ) == "\u09b0\u09cd\u09af\u09be\u09ac"
    assert f(RAB_ZWJ) == f(RAB)


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_61__soft_hyphen_deleted():
    """INN-N-61 \u2014 f("Screw<SHY>driver") returns exactly "screwdriver".
    Rules: R6b [BUG-180]."""
    assert_exact(f("Screw" + SOFT_HYPHEN + "driver"), "screwdriver")


@pytest.mark.xfail(strict=True, reason=BUG_180)
def test_inn_n_62__zwnj_deleted():
    """INN-N-62 \u2014 f("a<ZWNJ>b") returns exactly "ab".
    Rules: R6b [BUG-180]."""
    assert_exact(f("a" + ZWNJ + "b"), "ab")


@pytest.mark.xfail(strict=True, reason=BUG_183)
def test_inn_n_63__underscore_between_words_becomes_space():
    """INN-N-63 \u2014 f("Screw_Driver") returns exactly "screw driver".
    Rules: R6c [BUG-183]."""
    assert_exact(f("Screw_Driver"), "screw driver")


@pytest.mark.xfail(strict=True, reason=BUG_183)
def test_inn_n_64__only_underscores_returns_empty():
    """INN-N-64 \u2014 f("__") returns exactly "".
    Rules: R6c, R7 [BUG-183]."""
    assert_exact(f("__"), "")


def test_inn_n_65__hyphens_only_returns_empty():
    """INN-N-65 \u2014 f("--") returns exactly "".
    Rules: R7."""
    assert_exact(f("--"), "")


def test_inn_n_66__exclamations_only_returns_empty():
    """INN-N-66 \u2014 f("!!!") returns exactly "".
    Rules: R7."""
    assert_exact(f("!!!"), "")


def test_inn_n_67__spaces_around_punctuation_collapse():
    """INN-N-67 \u2014 f("a - b") returns exactly "a b".
    Rules: R7."""
    assert_exact(f("a - b"), "a b")


def test_inn_n_68__four_variants_same_key():
    """INN-N-68 \u2014 four spacing/case/punctuation variants all give "screw driver 22m".
    Rules: R8."""
    for x in (
        "Screw Driver 22m",
        "Screw Driver 22 m",
        "  screw   driver  22  M  ",
        "Screw-Driver 22m",
    ):
        assert_exact(f(x), "screw driver 22m")


@pytest.mark.parametrize(
    "x",
    [
        pytest.param(x, id=f"INN-N-69[{x!a}]")
        for x in (
            "Screw Driver 22 m",
            "  screw   driver  22  M  ",
            "2 x 3 m",
            "10 mm, 20 mm",
            "1.5 mm",
            "Size 10 and up",
            "Model X5 pro",
            "5 kg-pack",
            "5 kg2",
            "22 metres",
            "Screw-Driver",
            "a" + ZWSP + "b",
            "a" + ENCLOSING_CIRCLE + "b",
            "--",
            "",
            "bolt 10 mm",
        )
    ],
)
def test_inn_n_69__idempotent_on_bug_free_inputs(x):
    """INN-N-69 \u2014 f(f(x)) == f(x) for each bug-free input (param id names x).
    Rules: R8a."""
    assert f(f(x)) == f(x)


@pytest.mark.parametrize(
    "x",
    [
        pytest.param(CAFE_PRE, id="INN-N-70[CAFE_PRE]"),
        pytest.param(CAFE_DEC, id="INN-N-70[CAFE_DEC]"),
        pytest.param(FW_BOLT, id="INN-N-70[FW_BOLT]"),
        pytest.param(FW_10MM, id="INN-N-70[FW_10MM]"),
        pytest.param(X_SQUARED, id="INN-N-70[x_superscript_2]"),
        pytest.param(FI_LIGATURE_FILE, id="INN-N-70[fi_ligature_le]"),
        pytest.param(CHAL, id="INN-N-70[CHAL]"),
        pytest.param(RAB_ZWJ, id="INN-N-70[RAB_ZWJ]"),
        pytest.param(PHRASE, id="INN-N-70[PHRASE]"),
    ],
)
def test_inn_n_70__idempotent_on_unicode_inputs(x):
    """INN-N-70 \u2014 f(f(x)) == f(x) for Unicode inputs stable today and after every fix.
    Rules: R8a."""
    assert f(f(x)) == f(x)


@pytest.mark.xfail(strict=True, reason=BUG_182)
def test_inn_n_71__idempotent_when_gluing_follows_punctuation():
    """INN-N-71 \u2014 f(f(x)) == f(x) for "Bolt 10-mm", "Bolt 10.mm", "Size 5 (pack)"; f("Bolt 10-mm") == "bolt 10mm".
    Rules: R8a [BUG-182]."""
    for x in ("Bolt 10-mm", "Bolt 10.mm", "Size 5 (pack)"):
        assert f(f(x)) == f(x), f"not idempotent for {x!r}"
    assert f("Bolt 10-mm") == "bolt 10mm"


def test_inn_n_72__no_length_validation():
    """INN-N-72 \u2014 a 10000-char input returns exactly "a" * 10000, no exception.
    Rules: Inputs; Errors (none)."""
    assert_exact(f("A" * 10000), "a" * 10000)


# --------------------------------------------------------------------------- #
# Module constants
# --------------------------------------------------------------------------- #


def test_inn_k_01__constant_values():
    """INN-K-01 \u2014 MIN_SIMILAR_NAME_LENGTH == 3 and SIMILARITY_THRESHOLD == 0.35.
    Rules: Overview (constants)."""
    assert MIN_SIMILAR_NAME_LENGTH == 3
    assert SIMILARITY_THRESHOLD == 0.35
