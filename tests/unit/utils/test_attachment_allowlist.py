"""Unit tests for app/utils/attachment_allowlist.py — implements tests/unit/utils/attachment_allowlist.cases.md (revision 4)."""
import dataclasses

import pydantic
import pytest

from app.models.enums import AttachmentEntityTypeEnum
from app.schemas.attachment import AttachmentSignRequest
from app.utils.attachment_allowlist import (
    ALLOWED_MIME_TYPES,
    EXTENSION_TO_SPEC,
    MAX_FILE_SIZE_BYTES,
    AttachmentConfirmError,
    AttachmentTypeSpec,
    AttachmentValidationError,
    extract_extension,
    normalize_upload_request,
    sanitize_file_name,
    validate_cloudinary_resource,
)

# Convention "Database": not used — pure module, no `db` fixture, no mocks, no race simulations.

# Convention "MIME constants".
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Convention "first / last member of AttachmentEntityTypeEnum".
_FIRST_ENTITY_TYPE = list(AttachmentEntityTypeEnum)[0]
_LAST_ENTITY_TYPE = list(AttachmentEntityTypeEnum)[-1]


def P(name, mime, size=1024, *, entity_type=None, entity_id=1, note=None):
    """Convention "Payload P(name, mime, size=1024)": model_construct, no schema validation."""
    return AttachmentSignRequest.model_construct(
        entity_type=entity_type if entity_type is not None else _FIRST_ENTITY_TYPE,
        entity_id=entity_id,
        file_name=name,
        mime_type=mime,
        file_size=size,
        note=note,
    )


def T(rt="image"):
    """Convention "Local type entry T(rt)": AttachmentTypeSpec built positionally (pdf-like values)."""
    return AttachmentTypeSpec(frozenset({"pdf"}), frozenset({"application/pdf"}), rt, frozenset({"pdf"}))


def TK(rt="image"):
    """Convention "TK(rt)": the same values as T(rt), passed as keywords."""
    return AttachmentTypeSpec(
        extensions=frozenset({"pdf"}),
        mime_types=frozenset({"application/pdf"}),
        resource_type=rt,
        confirm_formats=frozenset({"pdf"}),
    )


def S(name, mime):
    """Convention "Schema build S(name, mime)": real Pydantic validation, `note` omitted."""
    return AttachmentSignRequest(
        entity_type=_FIRST_ENTITY_TYPE,
        entity_id=1,
        file_name=name,
        mime_type=mime,
        file_size=1024,
    )


# Bug markers (titles from the bugs staging file for this module).
BUG_120 = pytest.mark.xfail(strict=True, reason="BUG-120: Attachment file name can keep a leading/trailing space")
BUG_121 = pytest.mark.xfail(strict=True, reason="BUG-121: Long file names lose their extension when cut to 255 characters")
BUG_122 = pytest.mark.xfail(
    strict=True,
    reason="BUG-122: Invisible Unicode control/format characters (bidi override, zero-width, C1) kept in file names",
)
BUG_123 = pytest.mark.xfail(strict=True, reason="BUG-123: MIME type check is case-sensitive and rejects parameters")
BUG_124 = pytest.mark.xfail(
    strict=True,
    reason="BUG-124: Confirm with a no-longer-allowed extension returns 500 and leaves the attachment pending",
)
BUG_125 = pytest.mark.xfail(
    strict=True, reason="BUG-125: Whitespace-only attachment file name passes the sign-request schema"
)

_NOT_ALLOWED = ["zip", "bin", "doc", "xls", "docm", "xlsm", "svg", "html", "js", "exe", "gif"]
_ALLOWED = ["jpg", "jpeg", "png", "webp", "heic", "heif", "pdf", "docx", "xlsx", "txt", "csv"]


# ---------------------------------------------------------------------------
# Module data
# ---------------------------------------------------------------------------


def test_aal_data_01__extension_keys():
    """AAL-DATA-01 — EXTENSION_TO_SPEC has exactly the 11 lowercase allowed extensions.
    Rules: Overview table."""
    keys = set(EXTENSION_TO_SPEC.keys())
    assert keys == {"jpg", "jpeg", "png", "webp", "heic", "heif", "pdf", "docx", "xlsx", "txt", "csv"}
    assert len(EXTENSION_TO_SPEC) == 11
    assert all(k == k.lower() for k in EXTENSION_TO_SPEC)


def test_aal_data_02__jpg_jpeg_share_one_entry():
    """AAL-DATA-02 — jpg and jpeg map to the same spec object with the table values.
    Rules: Overview (jpg/jpeg share)."""
    spec = EXTENSION_TO_SPEC["jpg"]
    assert EXTENSION_TO_SPEC["jpg"] is EXTENSION_TO_SPEC["jpeg"]
    assert set(spec.extensions) == {"jpg", "jpeg"}
    assert set(spec.mime_types) == {"image/jpeg"}
    assert spec.resource_type == "image"
    assert set(spec.confirm_formats) == {"jpg", "jpeg"}


@pytest.mark.parametrize(
    "ext, mimes, resource_type, formats",
    [
        pytest.param("png", {"image/png"}, "image", {"png"}, id="AAL-DATA-03-png"),
        pytest.param("webp", {"image/webp"}, "image", {"webp"}, id="AAL-DATA-03-webp"),
        pytest.param("heic", {"image/heic"}, "image", {"heic"}, id="AAL-DATA-03-heic"),
        pytest.param("heif", {"image/heif"}, "image", {"heif"}, id="AAL-DATA-03-heif"),
        pytest.param("pdf", {"application/pdf"}, "image", {"pdf"}, id="AAL-DATA-03-pdf"),
        pytest.param("docx", {DOCX}, "raw", {"docx"}, id="AAL-DATA-03-docx"),
        pytest.param("xlsx", {XLSX}, "raw", {"xlsx"}, id="AAL-DATA-03-xlsx"),
        pytest.param("txt", {"text/plain"}, "raw", {"txt"}, id="AAL-DATA-03-txt"),
        pytest.param("csv", {"text/csv", "text/plain"}, "raw", {"csv", "txt"}, id="AAL-DATA-03-csv"),
    ],
)
def test_aal_data_03__table_rows(ext, mimes, resource_type, formats):
    """AAL-DATA-03 — each non-jpeg table row has the table's MIME types, resource_type and formats.
    Rules: Overview table."""
    spec = EXTENSION_TO_SPEC[ext]
    assert set(spec.mime_types) == mimes
    assert spec.resource_type == resource_type
    assert set(spec.confirm_formats) == formats
    assert ext in spec.extensions


def test_aal_data_04__allowed_mime_union():
    """AAL-DATA-04 — ALLOWED_MIME_TYPES is the union of the table's MIME types (10, text/plain once).
    Rules: Overview (MIME union)."""
    assert set(ALLOWED_MIME_TYPES) == {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "application/pdf",
        DOCX,
        XLSX,
        "text/plain",
        "text/csv",
    }
    assert len(ALLOWED_MIME_TYPES) == 10


def test_aal_data_05__max_file_size():
    """AAL-DATA-05 — MAX_FILE_SIZE_BYTES is 10 MiB.
    Rules: Overview (max size)."""
    assert MAX_FILE_SIZE_BYTES == 10485760


def test_aal_data_06__other_extensions_not_allowed():
    """AAL-DATA-06 — extensions outside the table are not keys.
    Rules: Overview (anything else not allowed)."""
    for ext in _NOT_ALLOWED:
        assert ext not in EXTENSION_TO_SPEC


# ---------------------------------------------------------------------------
# AttachmentTypeSpec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, new_value, original",
    [
        pytest.param("extensions", frozenset({"exe"}), {"pdf"}, id="AAL-TSP-01-extensions"),
        pytest.param("mime_types", frozenset({"text/html"}), {"application/pdf"}, id="AAL-TSP-01-mime_types"),
        pytest.param("resource_type", "raw", "image", id="AAL-TSP-01-resource_type"),
        pytest.param("confirm_formats", frozenset({"exe"}), {"pdf"}, id="AAL-TSP-01-confirm_formats"),
    ],
)
def test_aal_tsp_01__fields_cannot_be_assigned(field, new_value, original):
    """AAL-TSP-01 — assigning any field of an AttachmentTypeSpec raises FrozenInstanceError; value unchanged.
    Rules: AttachmentTypeSpec R1; Errors row "Assigning"."""
    t = T()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(t, field, new_value)
    value = getattr(t, field)
    if isinstance(original, set):
        assert set(value) == original
    else:
        assert value == original


def test_aal_tsp_02__no_new_attribute_no_delete():
    """AAL-TSP-02 — adding a new attribute or deleting a field raises FrozenInstanceError.
    Rules: AttachmentTypeSpec R1; Errors row "Assigning / deleting"."""
    t = T()
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.extra = 1
    assert hasattr(t, "extra") is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        del t.resource_type
    assert t.resource_type == "image"


def test_aal_tsp_03__shared_entry_cannot_be_assigned():
    """AAL-TSP-03 — assigning to the shared EXTENSION_TO_SPEC["pdf"] entry raises; the table is unchanged.
    Rules: AttachmentTypeSpec R1 (shared entry)."""
    entry = EXTENSION_TO_SPEC["pdf"]
    old = entry.resource_type
    try:
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.resource_type = "raw"
        assert EXTENSION_TO_SPEC["pdf"].resource_type == "image"
        assert EXTENSION_TO_SPEC["jpg"].resource_type == "image"
    finally:
        # Regression guard: if the assignment ever succeeds, put the shared entry back.
        if entry.resource_type != old:
            object.__setattr__(entry, "resource_type", old)


def test_aal_tsp_04__table_entries_hashable():
    """AAL-TSP-04 — table entries are hashable: hash, set of values (10) and dict key all work.
    Rules: AttachmentTypeSpec R2 (hashable)."""
    h = hash(EXTENSION_TO_SPEC["pdf"])
    s = set(EXTENSION_TO_SPEC.values())
    d = {EXTENSION_TO_SPEC["png"]: "x"}
    assert isinstance(h, int)
    assert len(s) == 10
    assert d[EXTENSION_TO_SPEC["png"]] == "x"


def test_aal_tsp_05__value_equality():
    """AAL-TSP-05 — equal field values compare and hash equal; a different field makes them differ.
    Rules: AttachmentTypeSpec R2 (value equality — both sides)."""
    a = T()
    b = TK()
    c = T("raw")
    assert a == b
    assert a is not b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert a == EXTENSION_TO_SPEC["pdf"]
    assert a != c
    assert len({a, c}) == 2


# ---------------------------------------------------------------------------
# NormalizedUploadRequest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, new_value",
    [
        pytest.param("file_name", "x.exe", id="AAL-NRQ-01-file_name"),
        pytest.param("mime_type", "text/html", id="AAL-NRQ-01-mime_type"),
        pytest.param("resource_type", "raw", id="AAL-NRQ-01-resource_type"),
        pytest.param("extension", "exe", id="AAL-NRQ-01-extension"),
        pytest.param("spec", EXTENSION_TO_SPEC["pdf"], id="AAL-NRQ-01-spec"),
    ],
)
def test_aal_nrq_01__fields_cannot_be_assigned(field, new_value):
    """AAL-NRQ-01 — assigning any field of a normalize_upload_request result raises; value unchanged.
    Rules: NormalizedUploadRequest R1; Errors row "Assigning"."""
    r = normalize_upload_request(P("photo.png", "image/png"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(r, field, new_value)
    if field == "spec":
        assert r.spec is EXTENSION_TO_SPEC["png"]
    else:
        expected = {"file_name": "photo.png", "mime_type": "image/png", "resource_type": "image", "extension": "png"}
        assert getattr(r, field) == expected[field]


def test_aal_nrq_02__no_new_attribute_no_delete():
    """AAL-NRQ-02 — adding a new attribute or deleting a field of the result raises FrozenInstanceError.
    Rules: NormalizedUploadRequest R1; Errors row "Assigning / deleting"."""
    r = normalize_upload_request(P("photo.png", "image/png"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.extra = 1
    assert hasattr(r, "extra") is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        del r.file_name
    assert r.file_name == "photo.png"


def test_aal_nrq_03__hashable_value_equality():
    """AAL-NRQ-03 — equal results compare and hash equal; a different file name makes them differ.
    Rules: NormalizedUploadRequest R2 (hashable, value equality — both sides)."""
    r1 = normalize_upload_request(P("photo.png", "image/png"))
    r2 = normalize_upload_request(P("photo.png", "image/png"))
    r3 = normalize_upload_request(P("other.png", "image/png"))
    assert r1 == r2
    assert r1 is not r2
    assert hash(r1) == hash(r2)
    assert len({r1, r2}) == 1
    assert r1 != r3
    assert len({r1, r3}) == 2


# ---------------------------------------------------------------------------
# sanitize_file_name
# ---------------------------------------------------------------------------


def test_aal_san_01__slashes_become_dashes():
    """AAL-SAN-01 — forward slash and backslash are replaced with '-'.
    Rules: sanitize_file_name R1."""
    assert sanitize_file_name("a/b\\c.pdf") == "a-b-c.pdf"


def test_aal_san_02__path_traversal_then_leading_dots_trimmed():
    """AAL-SAN-02 — '../x.pdf' becomes '-x.pdf'.
    Rules: sanitize_file_name R1, R3."""
    assert sanitize_file_name("../x.pdf") == "-x.pdf"


def test_aal_san_03__only_slashes_not_empty():
    """AAL-SAN-03 — '///' becomes '---' with no error.
    Rules: sanitize_file_name R1, R4."""
    assert sanitize_file_name("///") == "---"


def test_aal_san_04__ascii_controls_removed():
    """AAL-SAN-04 — NUL, 0x1f and DEL are removed.
    Rules: sanitize_file_name R2."""
    assert sanitize_file_name("re\x00po\x1frt\x7f.pdf") == "report.pdf"


def test_aal_san_05__windows_reserved_chars_removed():
    """AAL-SAN-05 — < > : " | ? * are removed.
    Rules: sanitize_file_name R2."""
    assert sanitize_file_name('a<b>c:d"e|f?g*h.pdf') == "abcdefgh.pdf"


def test_aal_san_06__unicode_and_punctuation_kept():
    """AAL-SAN-06 — Unicode letters and ordinary punctuation are kept unchanged.
    Rules: sanitize_file_name R2, R6."""
    name = "Ünïcödé 报告 O'Brien #1 50% A&B (v2)-final_x.pdf"
    assert sanitize_file_name(name) == name


def test_aal_san_07__inner_nbsp_kept():
    """AAL-SAN-07 — an inner non-breaking space is kept.
    Rules: sanitize_file_name R2."""
    assert sanitize_file_name("My\u00a0Report.pdf") == "My\u00a0Report.pdf"


def test_aal_san_08__control_range_edges():
    """AAL-SAN-08 — code 31 removed / 32 kept; code 127 removed / 126 kept.
    Rules: sanitize_file_name R2."""
    assert sanitize_file_name("a\x1fb c.pdf") == "ab c.pdf"
    assert sanitize_file_name("a\x7fb~c.pdf") == "ab~c.pdf"


@BUG_122
def test_aal_san_09__bidi_override_removed():
    """AAL-SAN-09 — U+202E (right-to-left override) is removed.
    Rules: sanitize_file_name R2a [BUG-122]."""
    assert sanitize_file_name("invoice\u202efdp.txt") == "invoicefdp.txt"


@BUG_122
def test_aal_san_10__zero_width_space_removed():
    """AAL-SAN-10 — leading U+200B is removed.
    Rules: sanitize_file_name R2a [BUG-122]."""
    assert sanitize_file_name("\u200breport.pdf") == "report.pdf"


@BUG_122
def test_aal_san_11__c1_controls_removed():
    """AAL-SAN-11 — C1 controls (U+0085 mid-name; U+0080 and U+009F) are removed.
    Rules: sanitize_file_name R2a [BUG-122]."""
    assert sanitize_file_name("rep\x85ort.pdf") == "report.pdf"
    assert sanitize_file_name("a\x80b\x9fc.pdf") == "abc.pdf"


@BUG_122
def test_aal_san_12__format_chars_removed():
    """AAL-SAN-12 — ZWJ, BOM and soft hyphen are removed.
    Rules: sanitize_file_name R2a [BUG-122]."""
    assert sanitize_file_name("re\u200dp\ufeffo\u00adrt.pdf") == "report.pdf"


@BUG_122
def test_aal_san_13__only_format_chars_is_invalid():
    """AAL-SAN-13 — a name of only Cf characters raises 'Invalid file name.'.
    Rules: sanitize_file_name R2a, R4 [BUG-122]."""
    with pytest.raises(AttachmentValidationError) as exc:
        sanitize_file_name("\u202e\u200b")
    assert str(exc.value) == "Invalid file name."


@BUG_122
def test_aal_san_14__format_chars_removed_before_trim():
    """AAL-SAN-14 — Cf removed before trimming, so the surrounding spaces are trimmed too.
    Rules: sanitize_file_name R2a, R3 (order) [BUG-122]."""
    assert sanitize_file_name(" \u200b report.pdf") == "report.pdf"


def test_aal_san_15__surrounding_whitespace_trimmed():
    """AAL-SAN-15 — leading/trailing spaces are trimmed.
    Rules: sanitize_file_name R3."""
    assert sanitize_file_name("  report.pdf  ") == "report.pdf"


def test_aal_san_16__surrounding_dots_trimmed():
    """AAL-SAN-16 — leading/trailing dots are trimmed.
    Rules: sanitize_file_name R3."""
    assert sanitize_file_name("..hidden.txt.") == "hidden.txt"


@BUG_120
def test_aal_san_17__dot_then_space_trimmed():
    """AAL-SAN-17 — '. report.pdf' is trimmed to 'report.pdf'.
    Rules: sanitize_file_name R3 [BUG-120]."""
    assert sanitize_file_name(". report.pdf") == "report.pdf"


@BUG_120
def test_aal_san_18__space_then_dot_trimmed():
    """AAL-SAN-18 — 'report.pdf .' is trimmed to 'report.pdf'.
    Rules: sanitize_file_name R3 [BUG-120]."""
    assert sanitize_file_name("report.pdf .") == "report.pdf"


@BUG_120
def test_aal_san_19__mixed_dots_spaces_trimmed_until_stable():
    """AAL-SAN-19 — ' . .report.pdf. . ' is trimmed to 'report.pdf'.
    Rules: sanitize_file_name R3 [BUG-120]."""
    assert sanitize_file_name(" . .report.pdf. . ") == "report.pdf"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="AAL-SAN-20-empty"),
        pytest.param("   ", id="AAL-SAN-20-spaces"),
        pytest.param("...", id="AAL-SAN-20-dots"),
        pytest.param(" . ", id="AAL-SAN-20-space-dot-space"),
        pytest.param("???", id="AAL-SAN-20-question-marks"),
        pytest.param("\x00\x01", id="AAL-SAN-20-controls"),
        pytest.param("<>", id="AAL-SAN-20-angle-brackets"),
    ],
)
def test_aal_san_20__nothing_left_is_invalid(name):
    """AAL-SAN-20 — a name that cleans to empty raises 'Invalid file name.' (a ValueError).
    Rules: sanitize_file_name R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        sanitize_file_name(name)
    assert isinstance(exc.value, ValueError)
    assert str(exc.value) == "Invalid file name."


def test_aal_san_21__single_char_ok():
    """AAL-SAN-21 — 'a' is returned unchanged.
    Rules: sanitize_file_name R4."""
    assert sanitize_file_name("a") == "a"


def test_aal_san_22__exactly_255_unchanged():
    """AAL-SAN-22 — a 255-character name is unchanged.
    Rules: sanitize_file_name R5."""
    name = "a" * 251 + ".pdf"
    result = sanitize_file_name(name)
    assert result == name
    assert len(result) == 255


def test_aal_san_23__no_dot_plain_cut():
    """AAL-SAN-23 — 300 chars with no '.' are cut to the first 255.
    Rules: sanitize_file_name R5."""
    assert sanitize_file_name("a" * 300) == "a" * 255


def test_aal_san_24__cut_counts_code_points():
    """AAL-SAN-24 — 'é' * 300 is cut to 255 characters (510 UTF-8 bytes).
    Rules: sanitize_file_name R5 (code points)."""
    result = sanitize_file_name("é" * 300)
    assert result == "é" * 255
    assert len(result) == 255
    assert len(result.encode("utf-8")) == 510


def test_aal_san_25__255_chars_over_255_bytes_unchanged():
    """AAL-SAN-25 — 255 CJK characters (more than 255 bytes) are unchanged.
    Rules: sanitize_file_name R5 (code points)."""
    name = "报" * 251 + ".pdf"
    assert sanitize_file_name(name) == name


@BUG_121
def test_aal_san_26__256_keeps_extension():
    """AAL-SAN-26 — a 256-character name keeps '.pdf' and is 255 long.
    Rules: sanitize_file_name R5a [BUG-121]."""
    result = sanitize_file_name("t" * 252 + ".pdf")
    assert result == "t" * 251 + ".pdf"
    assert len(result) == 255


@BUG_121
def test_aal_san_27__extension_case_kept_on_cut():
    """AAL-SAN-27 — an over-long name keeps '.PDF' in its original case.
    Rules: sanitize_file_name R5a [BUG-121]."""
    assert sanitize_file_name("x" * 300 + ".PDF") == "x" * 251 + ".PDF"


@BUG_121
def test_aal_san_28__only_last_extension_kept():
    """AAL-SAN-28 — '.tar.csv' keeps only '.csv' after the cut.
    Rules: sanitize_file_name R5a [BUG-121]."""
    assert sanitize_file_name("a" * 300 + ".tar.csv") == "a" * 251 + ".csv"


@BUG_121
def test_aal_san_29__largest_keepable_extension():
    """AAL-SAN-29 — a 253-character extension is kept with a 1-character stem.
    Rules: sanitize_file_name R5, R5a [BUG-121]."""
    result = sanitize_file_name("b" * 10 + "." + "e" * 253)
    assert result == "b" + "." + "e" * 253
    assert len(result) == 255


def test_aal_san_30__extension_too_long_plain_cut():
    """AAL-SAN-30 — a 254-character extension leaves no room, so a plain cut to 255.
    Rules: sanitize_file_name R5."""
    assert sanitize_file_name("b" * 10 + "." + "e" * 254) == "b" * 10 + "." + "e" * 244


@BUG_121
def test_aal_san_31__spaces_at_cut_removed():
    """AAL-SAN-31 — spaces before the extension at the cut are removed.
    Rules: sanitize_file_name R5b [BUG-121]."""
    result = sanitize_file_name("a" * 250 + " " * 10 + ".pdf")
    assert result == "a" * 250 + ".pdf"
    assert len(result) == 254


@BUG_121
def test_aal_san_32__trailing_space_at_plain_cut_removed():
    """AAL-SAN-32 — a trailing space left by a plain cut is removed.
    Rules: sanitize_file_name R5b [BUG-121]."""
    assert sanitize_file_name("a" * 254 + " b" + "c" * 50) == "a" * 254


@BUG_121
def test_aal_san_33__dots_at_cut_removed():
    """AAL-SAN-33 — dots before the extension at the cut are removed.
    Rules: sanitize_file_name R5b [BUG-121]."""
    result = sanitize_file_name("a" * 250 + "." * 10 + ".pdf")
    assert result == "a" * 250 + ".pdf"
    assert len(result) == 254


def test_aal_san_34__case_and_inner_space_kept():
    """AAL-SAN-34 — 'My Report.PDF' is unchanged.
    Rules: sanitize_file_name R6."""
    assert sanitize_file_name("My Report.PDF") == "My Report.PDF"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("t" * 252 + ".pdf", id="AAL-SAN-35-san26-input"),
        pytest.param("x" * 300 + ".PDF", id="AAL-SAN-35-san27-input"),
        pytest.param("a" * 300 + ".tar.csv", id="AAL-SAN-35-san28-input"),
    ],
)
def test_aal_san_35__cut_regression_length_and_prefix(name):
    """AAL-SAN-35 — over-long names come back at most 255 long and start with the input's first 251 chars.
    Rules: sanitize_file_name R5, R5a (regression part)."""
    result = sanitize_file_name(name)
    assert len(result) <= 255
    assert result.startswith(name[:251])


# ---------------------------------------------------------------------------
# extract_extension
# ---------------------------------------------------------------------------


def test_aal_ext_01__last_extension_used():
    """AAL-EXT-01 — 'evil.exe.pdf' gives 'pdf'.
    Rules: extract_extension R1."""
    assert extract_extension("evil.exe.pdf") == "pdf"


def test_aal_ext_02__last_extension_not_allowed():
    """AAL-EXT-02 — 'report.pdf.exe' raises 'Unsupported file extension: .exe'.
    Rules: extract_extension R1, R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("report.pdf.exe")
    assert str(exc.value) == "Unsupported file extension: .exe"


def test_aal_ext_03__no_dot():
    """AAL-EXT-03 — 'README' raises the missing-extension error.
    Rules: extract_extension R2."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("README")
    assert str(exc.value) == "File name must include a supported extension."


def test_aal_ext_04__trailing_dot():
    """AAL-EXT-04 — 'report.' raises the missing-extension error.
    Rules: extract_extension R2."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("report.")
    assert str(exc.value) == "File name must include a supported extension."


def test_aal_ext_05__lowercased():
    """AAL-EXT-05 — upper/mixed case extensions are returned lowercase.
    Rules: extract_extension R3."""
    assert extract_extension("PHOTO.JPG") == "jpg"
    assert extract_extension("a.JpEg") == "jpeg"


def test_aal_ext_06__lowercased_in_error():
    """AAL-EXT-06 — 'archive.ZIP' raises with the lowercased extension.
    Rules: extract_extension R3, R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("archive.ZIP")
    assert str(exc.value) == "Unsupported file extension: .zip"


def test_aal_ext_07__space_in_extension_not_allowed():
    """AAL-EXT-07 — 'a. pdf' raises 'Unsupported file extension: . pdf'.
    Rules: extract_extension R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("a. pdf")
    assert str(exc.value) == "Unsupported file extension: . pdf"


def test_aal_ext_08__trailing_space_not_cleaned():
    """AAL-EXT-08 — 'photo.png ' raises with the space kept in the message.
    Rules: extract_extension R4 (not cleaned)."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("photo.png ")
    assert str(exc.value) == "Unsupported file extension: .png "


def test_aal_ext_09__dot_only_stem():
    """AAL-EXT-09 — '.pdf' gives 'pdf'.
    Rules: extract_extension R5."""
    assert extract_extension(".pdf") == "pdf"


@pytest.mark.parametrize("ext", [pytest.param(e, id=f"AAL-EXT-10-{e}") for e in _ALLOWED])
def test_aal_ext_10__every_allowed_extension(ext):
    """AAL-EXT-10 — each allowed extension, lower or upper case, returns the lowercase extension.
    Rules: extract_extension R1, R3."""
    assert extract_extension("file." + ext) == ext
    assert extract_extension("file." + ext.upper()) == ext


@pytest.mark.parametrize("ext", [pytest.param(e, id=f"AAL-EXT-11-{e}") for e in _NOT_ALLOWED])
def test_aal_ext_11__not_allowed_extensions(ext):
    """AAL-EXT-11 — each not-allowed extension raises 'Unsupported file extension: .<ext>'.
    Rules: extract_extension R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        extract_extension("file." + ext)
    assert str(exc.value) == "Unsupported file extension: ." + ext


# ---------------------------------------------------------------------------
# normalize_upload_request
# ---------------------------------------------------------------------------


def test_aal_nur_01__png_happy():
    """AAL-NUR-01 — photo.png / image/png is normalised field by field.
    Rules: normalize_upload_request R5."""
    r = normalize_upload_request(P("photo.png", "image/png"))
    assert r.file_name == "photo.png"
    assert r.mime_type == "image/png"
    assert r.resource_type == "image"
    assert r.extension == "png"
    assert r.spec is EXTENSION_TO_SPEC["png"]


def test_aal_nur_02__docx_happy():
    """AAL-NUR-02 — report.docx / DOCX is normalised with resource_type raw.
    Rules: normalize_upload_request R5."""
    r = normalize_upload_request(P("report.docx", DOCX))
    assert r.file_name == "report.docx"
    assert r.mime_type == DOCX
    assert r.resource_type == "raw"
    assert r.extension == "docx"
    assert r.spec is EXTENSION_TO_SPEC["docx"]


@pytest.mark.parametrize(
    "ext, mime, resource_type",
    [
        pytest.param("jpg", "image/jpeg", "image", id="AAL-NUR-03-jpg"),
        pytest.param("jpeg", "image/jpeg", "image", id="AAL-NUR-03-jpeg"),
        pytest.param("png", "image/png", "image", id="AAL-NUR-03-png"),
        pytest.param("webp", "image/webp", "image", id="AAL-NUR-03-webp"),
        pytest.param("heic", "image/heic", "image", id="AAL-NUR-03-heic"),
        pytest.param("heif", "image/heif", "image", id="AAL-NUR-03-heif"),
        pytest.param("pdf", "application/pdf", "image", id="AAL-NUR-03-pdf"),
        pytest.param("docx", DOCX, "raw", id="AAL-NUR-03-docx"),
        pytest.param("xlsx", XLSX, "raw", id="AAL-NUR-03-xlsx"),
        pytest.param("txt", "text/plain", "raw", id="AAL-NUR-03-txt"),
        pytest.param("csv", "text/csv", "raw", id="AAL-NUR-03-csv-text/csv"),
        pytest.param("csv", "text/plain", "raw", id="AAL-NUR-03-csv-text/plain"),
    ],
)
def test_aal_nur_03__every_allowed_pair(ext, mime, resource_type):
    """AAL-NUR-03 — every allowed (extension, MIME) pair normalises per the table.
    Rules: normalize_upload_request R5."""
    r = normalize_upload_request(P("file." + ext, mime))
    assert r.file_name == "file." + ext
    assert r.extension == ext
    assert r.mime_type == mime
    assert r.resource_type == resource_type
    assert r.spec is EXTENSION_TO_SPEC[ext]


def test_aal_nur_04__jpeg_uses_shared_spec():
    """AAL-NUR-04 — a.jpeg keeps extension 'jpeg' and uses the shared jpg spec object.
    Rules: normalize_upload_request R5."""
    r = normalize_upload_request(P("a.jpeg", "image/jpeg"))
    assert r.extension == "jpeg"
    assert r.spec is EXTENSION_TO_SPEC["jpg"]


def test_aal_nur_05__size_at_limit_ok():
    """AAL-NUR-05 — exactly MAX_FILE_SIZE_BYTES is accepted.
    Rules: normalize_upload_request R1."""
    r = normalize_upload_request(P("photo.png", "image/png", size=10485760))
    assert r.file_name == "photo.png"


def test_aal_nur_06__size_over_limit():
    """AAL-NUR-06 — one byte over the limit raises the size error.
    Rules: normalize_upload_request R1."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("photo.png", "image/png", size=10485761))
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."


def test_aal_nur_07__size_checked_first():
    """AAL-NUR-07 — the size error wins over bad name and bad MIME.
    Rules: normalize_upload_request R1 (order)."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("???", "application/zip", size=20000000))
    assert str(exc.value) == "File too large (20000000 bytes). Maximum is 10485760 bytes."


def test_aal_nur_08__name_sanitized():
    """AAL-NUR-08 — ' ../My Report.PDF ' is sanitised to '-My Report.PDF'.
    Rules: normalize_upload_request R2."""
    r = normalize_upload_request(P(" ../My Report.PDF ", "application/pdf"))
    assert r.file_name == "-My Report.PDF"
    assert r.extension == "pdf"
    assert r.mime_type == "application/pdf"


def test_aal_nur_09__name_cleans_to_empty():
    """AAL-NUR-09 — '???' raises 'Invalid file name.'.
    Rules: normalize_upload_request R2."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("???", "image/png"))
    assert str(exc.value) == "Invalid file name."


def test_aal_nur_10__extension_from_sanitized_name():
    """AAL-NUR-10 — the extension is taken from the cleaned name and lowercased.
    Rules: normalize_upload_request R3."""
    r = normalize_upload_request(P("  photo.PNG. ", "image/png"))
    assert r.file_name == "photo.PNG"
    assert r.extension == "png"
    assert r.resource_type == "image"


@pytest.mark.parametrize(
    "name, mime, message",
    [
        pytest.param("README", "text/plain", "File name must include a supported extension.", id="AAL-NUR-11-a"),
        pytest.param(".pdf", "application/pdf", "File name must include a supported extension.", id="AAL-NUR-11-b"),
        pytest.param("archive.zip", "text/plain", "Unsupported file extension: .zip", id="AAL-NUR-11-c"),
    ],
)
def test_aal_nur_11__extension_errors(name, mime, message):
    """AAL-NUR-11 — missing / unsupported extension raise before the MIME check.
    Rules: normalize_upload_request R3."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P(name, mime))
    assert str(exc.value) == message


def test_aal_nur_12__mime_mismatch():
    """AAL-NUR-12 — image/jpeg for .png raises the MIME error.
    Rules: normalize_upload_request R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("photo.png", "image/jpeg"))
    assert str(exc.value) == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."


def test_aal_nur_13__mime_mismatch_sorted_list():
    """AAL-NUR-13 — application/pdf for .csv lists both csv MIME types sorted.
    Rules: normalize_upload_request R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("data.csv", "application/pdf"))
    assert str(exc.value) == (
        "MIME type 'application/pdf' does not match .csv (expected one of: text/csv, text/plain)."
    )


def test_aal_nur_14__csv_as_text_plain():
    """AAL-NUR-14 — data.csv with text/plain is accepted.
    Rules: normalize_upload_request R4, R5."""
    r = normalize_upload_request(P("data.csv", "text/plain"))
    assert r.mime_type == "text/plain"
    assert r.extension == "csv"
    assert r.resource_type == "raw"


def test_aal_nur_15__txt_as_text_csv_rejected():
    """AAL-NUR-15 — notes.txt with text/csv is rejected.
    Rules: normalize_upload_request R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("notes.txt", "text/csv"))
    assert str(exc.value) == "MIME type 'text/csv' does not match .txt (expected one of: text/plain)."


def test_aal_nur_16__octet_stream_rejected():
    """AAL-NUR-16 — application/octet-stream for .png is rejected.
    Rules: normalize_upload_request R4."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("photo.png", "application/octet-stream"))
    assert str(exc.value) == (
        "MIME type 'application/octet-stream' does not match .png (expected one of: image/png)."
    )


def test_aal_nur_17__error_quotes_mime_as_sent():
    """AAL-NUR-17 — 'IMAGE/JPEG' is quoted as sent in the error.
    Rules: normalize_upload_request R4, R4a (quote as sent)."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("photo.png", "IMAGE/JPEG"))
    assert str(exc.value) == "MIME type 'IMAGE/JPEG' does not match .png (expected one of: image/png)."


def test_aal_nur_18__inner_spaces_rejected():
    """AAL-NUR-18 — 'image / png' (inner spaces) is rejected.
    Rules: normalize_upload_request R4a (inner spaces)."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("photo.png", "image / png"))
    assert str(exc.value) == "MIME type 'image / png' does not match .png (expected one of: image/png)."


def test_aal_nur_19__wrong_type_with_params_rejected():
    """AAL-NUR-19 — 'text/html; charset=utf-8' for .txt is rejected, quoted as sent.
    Rules: normalize_upload_request R4, R4a (params, quote as sent)."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("notes.txt", "text/html; charset=utf-8"))
    assert str(exc.value) == (
        "MIME type 'text/html; charset=utf-8' does not match .txt (expected one of: text/plain)."
    )


@BUG_123
def test_aal_nur_20__mixed_case_mime_normalised():
    """AAL-NUR-20 — 'Image/PNG' is accepted and returned as 'image/png'.
    Rules: normalize_upload_request R4a, R5a [BUG-123]."""
    r = normalize_upload_request(P("photo.png", "Image/PNG"))
    assert r.mime_type == "image/png"
    assert r.extension == "png"


@BUG_123
def test_aal_nur_21__padded_mime_normalised():
    """AAL-NUR-21 — ' image/png ' is accepted and returned as 'image/png'.
    Rules: normalize_upload_request R4a, R5a [BUG-123]."""
    r = normalize_upload_request(P("photo.png", " image/png "))
    assert r.mime_type == "image/png"


@BUG_123
def test_aal_nur_22__empty_params_normalised():
    """AAL-NUR-22 — 'image/png;' is accepted and returned as 'image/png'.
    Rules: normalize_upload_request R4a, R5a [BUG-123]."""
    r = normalize_upload_request(P("photo.png", "image/png;"))
    assert r.mime_type == "image/png"


@BUG_123
def test_aal_nur_23__charset_param_normalised():
    """AAL-NUR-23 — 'text/csv; charset=utf-8' is accepted and returned as 'text/csv'.
    Rules: normalize_upload_request R4a, R5a [BUG-123]."""
    r = normalize_upload_request(P("data.csv", "text/csv; charset=utf-8"))
    assert r.mime_type == "text/csv"
    assert r.extension == "csv"
    assert r.resource_type == "raw"


@BUG_121
def test_aal_nur_24__long_name_keeps_extension():
    """AAL-NUR-24 — a 256-character name keeps '.pdf' after sanitising.
    Rules: normalize_upload_request R2 [BUG-121]."""
    r = normalize_upload_request(P("t" * 252 + ".pdf", "application/pdf"))
    assert r.file_name == "t" * 251 + ".pdf"
    assert r.extension == "pdf"


@BUG_122
def test_aal_nur_25__bidi_override_removed_from_name():
    """AAL-NUR-25 — U+202E is removed from the normalised file name.
    Rules: normalize_upload_request R2 [BUG-122]."""
    r = normalize_upload_request(P("invoice\u202efdp.txt", "text/plain"))
    assert r.file_name == "invoicefdp.txt"
    assert r.extension == "txt"


def test_aal_nur_26__ignored_fields():
    """AAL-NUR-26 — entity_type, entity_id and note do not affect the result.
    Rules: normalize_upload_request Inputs (ignored fields)."""
    r1 = normalize_upload_request(P("photo.png", "image/png"))
    r2 = normalize_upload_request(
        P("photo.png", "image/png", entity_type=_LAST_ENTITY_TYPE, entity_id=999, note="hello")
    )
    assert r1.file_name == r2.file_name
    assert r1.mime_type == r2.mime_type
    assert r1.resource_type == r2.resource_type
    assert r1.extension == r2.extension
    assert r1.spec is r2.spec


@BUG_125
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("   ", id="AAL-NUR-27-a-spaces"),
        pytest.param("\t \n", id="AAL-NUR-27-b-tab-space-newline"),
    ],
)
def test_aal_nur_27__schema_rejects_blank_name(name):
    """AAL-NUR-27 — AttachmentSignRequest rejects a whitespace-only file_name (target: schema).
    Rules: normalize_upload_request R2a [BUG-125]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        S(name, "text/plain")
    assert any(tuple(e["loc"]) == ("file_name",) for e in exc.value.errors())


def test_aal_nur_28__schema_accepts_padded_name():
    """AAL-NUR-28 — S(' a.pdf ') builds, and normalising it gives 'a.pdf' (target: schema).
    Rules: normalize_upload_request R2a (non-blank accepted)."""
    payload = S(" a.pdf ", "application/pdf")
    r = normalize_upload_request(payload)
    assert r.file_name == "a.pdf"
    assert r.extension == "pdf"
    assert r.mime_type == "application/pdf"
    assert r.resource_type == "image"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("<>", id="AAL-NUR-29-a-angle-brackets"),
        pytest.param("...", id="AAL-NUR-29-b-dots"),
    ],
)
def test_aal_nur_29__schema_accepts_but_module_rejects(name):
    """AAL-NUR-29 — non-blank names that clean to empty pass the schema, then get 'Invalid file name.'.
    Rules: normalize_upload_request R2a (not covered: cleans to empty), R2."""
    payload = S(name, "text/plain")
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(payload)
    assert str(exc.value) == "Invalid file name."


def test_aal_nur_30__module_defence_for_blank_name():
    """AAL-NUR-30 — a blank name that bypasses the schema still gets 'Invalid file name.'.
    Rules: normalize_upload_request R2a (module defence stays), R2."""
    with pytest.raises(AttachmentValidationError) as exc:
        normalize_upload_request(P("   ", "text/plain"))
    assert str(exc.value) == "Invalid file name."


# ---------------------------------------------------------------------------
# validate_cloudinary_resource
# ---------------------------------------------------------------------------


def test_aal_vcr_01__uppercase_name_matches():
    """AAL-VCR-01 — 'SCAN.PDF' with image/pdf returns None.
    Rules: validate_cloudinary_resource R1, R5."""
    assert validate_cloudinary_resource(
        file_name="SCAN.PDF", resource={"resource_type": "image", "format": "pdf"}
    ) is None


def test_aal_vcr_02__last_extension_used():
    """AAL-VCR-02 — the last extension decides: evil.exe.pdf ok, report.pdf.docx mismatches.
    Rules: validate_cloudinary_resource R1 (last extension)."""
    resource = {"resource_type": "image", "format": "pdf"}
    assert validate_cloudinary_resource(file_name="evil.exe.pdf", resource=resource) is None
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf.docx", resource=resource)
    assert str(exc.value) == "Cloudinary resource_type 'image' does not match .docx (expected 'raw')."


@pytest.mark.parametrize(
    "ext, resource_type, fmt",
    [
        pytest.param("jpg", "image", "jpg", id="AAL-VCR-03-jpg-jpg"),
        pytest.param("jpg", "image", "jpeg", id="AAL-VCR-03-jpg-jpeg"),
        pytest.param("jpeg", "image", "jpg", id="AAL-VCR-03-jpeg-jpg"),
        pytest.param("jpeg", "image", "jpeg", id="AAL-VCR-03-jpeg-jpeg"),
        pytest.param("png", "image", "png", id="AAL-VCR-03-png-png"),
        pytest.param("webp", "image", "webp", id="AAL-VCR-03-webp-webp"),
        pytest.param("heic", "image", "heic", id="AAL-VCR-03-heic-heic"),
        pytest.param("heif", "image", "heif", id="AAL-VCR-03-heif-heif"),
        pytest.param("pdf", "image", "pdf", id="AAL-VCR-03-pdf-pdf"),
        pytest.param("docx", "raw", "docx", id="AAL-VCR-03-docx-docx"),
        pytest.param("xlsx", "raw", "xlsx", id="AAL-VCR-03-xlsx-xlsx"),
        pytest.param("txt", "raw", "txt", id="AAL-VCR-03-txt-txt"),
        pytest.param("csv", "raw", "csv", id="AAL-VCR-03-csv-csv"),
        pytest.param("csv", "raw", "txt", id="AAL-VCR-03-csv-txt"),
    ],
)
def test_aal_vcr_03__every_allowed_pair(ext, resource_type, fmt):
    """AAL-VCR-03 — every (extension, allowed format) pair with the table's resource_type returns None.
    Rules: validate_cloudinary_resource R1, R5."""
    assert validate_cloudinary_resource(
        file_name="file." + ext, resource={"resource_type": resource_type, "format": fmt}
    ) is None


def test_aal_vcr_04__format_case_insensitive():
    """AAL-VCR-04 — format 'PDF' and 'Jpg' are accepted.
    Rules: validate_cloudinary_resource R4 (format case)."""
    assert validate_cloudinary_resource(
        file_name="report.pdf", resource={"resource_type": "image", "format": "PDF"}
    ) is None
    assert validate_cloudinary_resource(
        file_name="a.jpeg", resource={"resource_type": "image", "format": "Jpg"}
    ) is None


def test_aal_vcr_05__cross_pairing():
    """AAL-VCR-05 — jpeg/jpg and csv/txt cross pairings are accepted.
    Rules: validate_cloudinary_resource R4 (cross pairing)."""
    assert validate_cloudinary_resource(
        file_name="a.jpeg", resource={"resource_type": "image", "format": "jpg"}
    ) is None
    assert validate_cloudinary_resource(
        file_name="a.jpg", resource={"resource_type": "image", "format": "jpeg"}
    ) is None
    assert validate_cloudinary_resource(
        file_name="data.csv", resource={"resource_type": "raw", "format": "txt"}
    ) is None


def test_aal_vcr_06__other_keys_ignored():
    """AAL-VCR-06 — extra resource keys (bytes, public_id) are ignored.
    Rules: validate_cloudinary_resource Inputs (other keys ignored)."""
    assert validate_cloudinary_resource(
        file_name="photo.png",
        resource={"resource_type": "image", "format": "png", "bytes": 999999999, "public_id": "x"},
    ) is None


def test_aal_vcr_07__resource_type_mismatch():
    """AAL-VCR-07 — raw for .pdf raises the resource_type error.
    Rules: validate_cloudinary_resource R2."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource={"resource_type": "raw", "format": "pdf"})
    assert str(exc.value) == "Cloudinary resource_type 'raw' does not match .pdf (expected 'image')."


@pytest.mark.parametrize(
    "resource",
    [
        pytest.param({"format": "pdf"}, id="AAL-VCR-08-a-missing"),
        pytest.param({"resource_type": None, "format": "pdf"}, id="AAL-VCR-08-b-none"),
        pytest.param({"resource_type": "", "format": "pdf"}, id="AAL-VCR-08-c-empty"),
    ],
)
def test_aal_vcr_08__resource_type_missing(resource):
    """AAL-VCR-08 — missing / None / empty resource_type is reported as ''.
    Rules: validate_cloudinary_resource R2 (missing/None/empty)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource=resource)
    assert str(exc.value) == "Cloudinary resource_type '' does not match .pdf (expected 'image')."


def test_aal_vcr_09__resource_type_case_sensitive():
    """AAL-VCR-09 — 'IMAGE' does not match 'image'.
    Rules: validate_cloudinary_resource R2 (case-sensitive)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource={"resource_type": "IMAGE", "format": "pdf"})
    assert str(exc.value) == "Cloudinary resource_type 'IMAGE' does not match .pdf (expected 'image')."


def test_aal_vcr_10__txt_as_image_rejected():
    """AAL-VCR-10 — image for .txt raises the resource_type error.
    Rules: validate_cloudinary_resource R2."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="notes.txt", resource={"resource_type": "image", "format": "txt"})
    assert str(exc.value) == "Cloudinary resource_type 'image' does not match .txt (expected 'raw')."


def test_aal_vcr_11__resource_type_checked_before_format():
    """AAL-VCR-11 — with both wrong, the resource_type error is raised.
    Rules: validate_cloudinary_resource R2 (checked before format)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource={"resource_type": "raw", "format": "docx"})
    assert str(exc.value) == "Cloudinary resource_type 'raw' does not match .pdf (expected 'image')."


def test_aal_vcr_12__format_not_allowed():
    """AAL-VCR-12 — png for .jpg raises the format error with the sorted list.
    Rules: validate_cloudinary_resource R3."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="photo.jpg", resource={"resource_type": "image", "format": "png"})
    assert str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."


@pytest.mark.parametrize(
    "resource",
    [
        pytest.param({"resource_type": "image"}, id="AAL-VCR-13-a-missing"),
        pytest.param({"resource_type": "image", "format": None}, id="AAL-VCR-13-b-none"),
        pytest.param({"resource_type": "image", "format": ""}, id="AAL-VCR-13-c-empty"),
    ],
)
def test_aal_vcr_13__format_missing(resource):
    """AAL-VCR-13 — missing / None / empty format is reported as ''.
    Rules: validate_cloudinary_resource R3 (missing/None/empty)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource=resource)
    assert str(exc.value) == "Cloudinary format '' is not allowed for .pdf (expected one of: pdf)."


def test_aal_vcr_14__format_lowercased_in_message():
    """AAL-VCR-14 — 'PNG' is reported lowercased.
    Rules: validate_cloudinary_resource R3 (lowercased in message)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="photo.jpg", resource={"resource_type": "image", "format": "PNG"})
    assert str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."


def test_aal_vcr_15__sorted_format_list():
    """AAL-VCR-15 — xlsx for .csv lists 'csv, txt'.
    Rules: validate_cloudinary_resource R3 (sorted list)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="data.csv", resource={"resource_type": "raw", "format": "xlsx"})
    assert str(exc.value) == "Cloudinary format 'xlsx' is not allowed for .csv (expected one of: csv, txt)."


def test_aal_vcr_16__non_string_format():
    """AAL-VCR-16 — an integer format is converted to a string in the message.
    Rules: validate_cloudinary_resource R3 (converted to string)."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.pdf", resource={"resource_type": "image", "format": 123})
    assert str(exc.value) == "Cloudinary format '123' is not allowed for .pdf (expected one of: pdf)."


@BUG_124
def test_aal_vcr_17__no_extension_is_confirm_error():
    """AAL-VCR-17 — 'README' raises AttachmentConfirmError, not AttachmentValidationError.
    Rules: validate_cloudinary_resource R1a [BUG-124]."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="README", resource={})
    assert str(exc.value) == "File name must include a supported extension."
    assert not isinstance(exc.value, AttachmentValidationError)


@BUG_124
def test_aal_vcr_18__unsupported_extension_is_confirm_error():
    """AAL-VCR-18 — 'archive.zip' raises AttachmentConfirmError, not AttachmentValidationError.
    Rules: validate_cloudinary_resource R1a [BUG-124]."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="archive.zip", resource={"resource_type": "raw", "format": "zip"})
    assert str(exc.value) == "Unsupported file extension: .zip"
    assert not isinstance(exc.value, AttachmentValidationError)


@BUG_124
def test_aal_vcr_19__trailing_dot_is_confirm_error():
    """AAL-VCR-19 — 'report.' raises AttachmentConfirmError.
    Rules: validate_cloudinary_resource R1a [BUG-124]."""
    with pytest.raises(AttachmentConfirmError) as exc:
        validate_cloudinary_resource(file_name="report.", resource={})
    assert str(exc.value) == "File name must include a supported extension."


@pytest.mark.parametrize(
    "file_name, message",
    [
        pytest.param("README", "File name must include a supported extension.", id="AAL-VCR-20-a"),
        pytest.param("archive.zip", "Unsupported file extension: .zip", id="AAL-VCR-20-b"),
        pytest.param("report.", "File name must include a supported extension.", id="AAL-VCR-20-c"),
    ],
)
def test_aal_vcr_20__extension_checked_before_resource(file_name, message):
    """AAL-VCR-20 — with an empty resource, the extension error (a ValueError) is raised first.
    Rules: validate_cloudinary_resource R1, R1a (regression part)."""
    with pytest.raises(ValueError) as exc:
        validate_cloudinary_resource(file_name=file_name, resource={})
    assert str(exc.value) == message
