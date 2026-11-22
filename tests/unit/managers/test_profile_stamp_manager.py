"""Unit tests for app/managers/profile_stamp_manager.py.

Implements tests/unit/managers/profile_stamp_manager.cases.md, one test per
case, in card order. No database: the manager has no persistence, so no test
requests `db`.

Externals are patched only where the spec's Overview names them:
`app.managers.profile_stamp_manager.destroy_resource` (fixture `dr`, every DS
and VS card), `app.managers.profile_stamp_manager.generate_upload_signature`
(fixture `gus`, only SG-01, SG-02, SG-06), `...uuid.uuid4` (`fixed_uuid`) and
`...time.time` (`fixed_time`). Settings are set per test with
`monkeypatch.setattr(settings, ...)` (autouse fixture `stamp_settings`).
Nothing ever reaches Cloudinary over the network: SG-03 .. SG-05 sign locally.

Normal mode: every test is written from its card and carries a
`# [claude] <ID>` comment; `# Then N` marks the checks of the card's Then line N.
"""

import copy
import logging
import re
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cloudinary.utils import api_sign_request
from pydantic import ValidationError as PydanticValidationError

from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.core.config import settings
from app.managers.profile_stamp_manager import (
    ProfileStampManager,
    profile_stamp_manager,
)
from app.schemas.saved_stamp import SavedStampImage

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = profile_stamp_manager"
M = profile_stamp_manager
assert isinstance(M, ProfileStampManager)

# Conventions "TOKEN", "OWN5"
TOKEN = "0123456789abcdef0123456789abcdef"
OWN5 = "development/profiles/5/stamp-" + TOKEN

# Convention "PRE5" (Revision 2)
PRE5 = "development/profiles/5/stamp-"

# Convention "Token variants" (Revision 2)
TOKEN31 = TOKEN[:31]
TOKEN33 = TOKEN + "0"
TOKENU = TOKEN.upper()
TOKENG = TOKEN[:31] + "g"

# Conventions "KIND_MSG", "FOREIGN_MSG"
KIND_MSG = "saved_stamp.kind must be 'vector' or 'image'."
FOREIGN_MSG = "saved_stamp.public_id is not a stamp of this user"

# Convention "VEC"
VEC = {
    "kind": "vector",
    "strokes": [{"color": "#000000", "width": 0.5, "points": []}],
    "viewBox": {"width": 100, "height": 50},
}

LOGGER_NAME = "app.managers.profile_stamp_manager"


# Convention "IMG(pid)" — a fresh dict on every call
def IMG(pid):
    return {
        "kind": "image",
        "public_id": pid,
        "url": "https://tracker.example/p.png",
        "width": 10,
        "height": 10,
    }


# Conventions "U5", "U55" — fresh objects per test (SG-07 checks U5 is not changed)
@pytest.fixture
def U5():
    return SimpleNamespace(id=5, name="Ann Lee")


# --------------------------------------------------------------------------- #
# Conventions -> settings (every test) and externals
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def stamp_settings(monkeypatch):
    """Convention "Settings (every test)"; a Given line overrides one with `setting(...)`."""
    monkeypatch.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "demo-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "123456")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", "s3cret")

    def setting(name, value):
        monkeypatch.setattr(settings, name, value)

    return setting


@pytest.fixture
def dr():
    """Convention "dr": destroy_resource patched, return_value {"result": "ok"}."""
    with patch(
        "app.managers.profile_stamp_manager.destroy_resource",
        return_value={"result": "ok"},
    ) as mock:
        yield mock


@pytest.fixture
def gus():
    """Convention "gus": generate_upload_signature patched, return_value "sig-x"."""
    with patch(
        "app.managers.profile_stamp_manager.generate_upload_signature",
        return_value="sig-x",
    ) as mock:
        yield mock


@pytest.fixture
def fixed_uuid():
    """Convention "fixed uuid"."""
    with patch(
        "app.managers.profile_stamp_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN)
    ) as mock:
        yield mock


@pytest.fixture
def fixed_time():
    """Convention "fixed time"."""
    with patch(
        "app.managers.profile_stamp_manager.time.time", return_value=1767225600.9
    ) as mock:
        yield mock


@pytest.fixture
def warnings_log(caplog):
    """Convention "warnings": set caplog before the When; call the result after it."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    def warnings():
        return [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == LOGGER_NAME
        ]

    return warnings


# --------------------------------------------------------------------------- #
# build_stamp_public_id
# --------------------------------------------------------------------------- #


# [claude] PSM-PI-01
def test_psm_pi_01__non_production_id_has_env_prefix(fixed_uuid):
    """PSM-PI-01 — outside production the id is <env>/profiles/<id>/stamp-<token>.
    Rules: build_stamp_public_id R3, R1."""
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-02
def test_psm_pi_02__production_id_has_no_prefix(stamp_settings, fixed_uuid):
    """PSM-PI-02 — in production the id has no environment prefix.
    Rules: build_stamp_public_id R2."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "production")
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-03
def test_psm_pi_03__empty_upload_env_falls_back_to_environment(
    stamp_settings, fixed_uuid
):
    """PSM-PI-03 — an empty upload environment falls back to ENVIRONMENT.
    Rules: build_stamp_public_id R1, R2."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "")
    stamp_settings("ENVIRONMENT", "production")
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-04
def test_psm_pi_04__upload_env_wins_over_environment(stamp_settings, fixed_uuid):
    """PSM-PI-04 — a non-empty upload environment wins over ENVIRONMENT.
    Rules: build_stamp_public_id R1, R3."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "staging")
    stamp_settings("ENVIRONMENT", "production")
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "staging/profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-05
def test_psm_pi_05__capital_production_is_not_production(stamp_settings, fixed_uuid):
    """PSM-PI-05 — "Production" with a capital is not production.
    Rules: build_stamp_public_id R3."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "Production")
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "Production/profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-06
def test_psm_pi_06__both_settings_empty_give_leading_slash(stamp_settings, fixed_uuid):
    """PSM-PI-06 — both settings empty give a leading slash.
    Rules: build_stamp_public_id R3."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "")
    stamp_settings("ENVIRONMENT", "")
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result == "/profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-PI-07
def test_psm_pi_07__each_call_gives_new_hex_token():
    """PSM-PI-07 — each call gives a new 32-character lowercase hex token.
    Rules: build_stamp_public_id R4, R2."""
    first = M.build_stamp_public_id(user_id=5)
    result = M.build_stamp_public_id(user_id=5)
    # Then 1
    assert result != first
    # Then 2
    assert (
        re.fullmatch(r"development/profiles/5/stamp-[0-9a-f]{32}", result) is not None
    )
    # Then 3
    assert re.fullmatch(r"development/profiles/5/stamp-[0-9a-f]{32}", first) is not None


# --------------------------------------------------------------------------- #
# build_stamp_asset_folder
# --------------------------------------------------------------------------- #


# [claude] PSM-AF-01
def test_psm_af_01__slash_becomes_dash():
    """PSM-AF-01 — a slash becomes a dash.
    Rules: build_stamp_asset_folder R1, R3."""
    result = M.build_stamp_asset_folder(user_name="Ann / Lee", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/Ann - Lee"


# [claude] PSM-AF-02
def test_psm_af_02__backslash_becomes_dash():
    """PSM-AF-02 — a backslash becomes a dash.
    Rules: build_stamp_asset_folder R1."""
    result = M.build_stamp_asset_folder(user_name="Ann\\Lee", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/Ann-Lee"


# [claude] PSM-AF-03
def test_psm_af_03__outer_spaces_removed():
    """PSM-AF-03 — outer spaces are removed.
    Rules: build_stamp_asset_folder R1."""
    result = M.build_stamp_asset_folder(user_name=" Ann ", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/Ann"


# [claude] PSM-AF-04
def test_psm_af_04__case_inner_spaces_and_characters_kept():
    """PSM-AF-04 — case, inner spaces and other characters are kept.
    Rules: build_stamp_asset_folder R1."""
    result = M.build_stamp_asset_folder(user_name="  Mary  O'NEIL_é ", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/Mary  O'NEIL_é"


# [claude] PSM-AF-05
def test_psm_af_05__empty_name_becomes_user_id():
    """PSM-AF-05 — an empty name becomes user-<id>.
    Rules: build_stamp_asset_folder R2."""
    result = M.build_stamp_asset_folder(user_name="", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/user-5"


# [claude] PSM-AF-06
def test_psm_af_06__whitespace_name_becomes_user_id():
    """PSM-AF-06 — a whitespace-only name becomes user-<id>.
    Rules: build_stamp_asset_folder R2."""
    result = M.build_stamp_asset_folder(user_name="   ", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/user-5"


# [claude] PSM-AF-07
def test_psm_af_07__only_slashes_is_not_empty():
    """PSM-AF-07 — a name of only slashes is not empty.
    Rules: build_stamp_asset_folder R2."""
    result = M.build_stamp_asset_folder(user_name="//", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/--"


# [claude] PSM-AF-08
def test_psm_af_08__production_has_no_dev_prefix(stamp_settings):
    """PSM-AF-08 — production has no Dev prefix.
    Rules: build_stamp_asset_folder R3."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "production")
    result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)
    # Then 1
    assert result == "Profile stamps/Ann Lee"


# [claude] PSM-AF-09
def test_psm_af_09__other_environment_gets_dev_prefix(stamp_settings):
    """PSM-AF-09 — any other environment gets the Dev prefix, whatever its name.
    Rules: build_stamp_asset_folder R3."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "staging")
    result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)
    # Then 1
    assert result == "Dev/Profile stamps/Ann Lee"


# [claude] PSM-AF-10
def test_psm_af_10__production_read_from_environment(stamp_settings):
    """PSM-AF-10 — production is read from ENVIRONMENT when the upload environment is empty.
    Rules: build_stamp_asset_folder R3 (via build_stamp_public_id R1)."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "")
    stamp_settings("ENVIRONMENT", "production")
    result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)
    # Then 1
    assert result == "Profile stamps/Ann Lee"


# [claude] PSM-AF-11
def test_psm_af_11__none_name_raises_attribute_error():
    """PSM-AF-11 — a None name raises AttributeError.
    Rules: build_stamp_asset_folder Errors."""
    # Then 1
    with pytest.raises(AttributeError):
        M.build_stamp_asset_folder(user_name=None, user_id=5)


# --------------------------------------------------------------------------- #
# sign_stamp_image_upload
# --------------------------------------------------------------------------- #


# [claude] PSM-SG-01
def test_psm_sg_01__empty_cloud_name_raises_before_signing(stamp_settings, gus, U5):
    """PSM-SG-01 — an empty cloud name raises before anything is signed.
    Rules: sign_stamp_image_upload R1, Errors row 1."""
    stamp_settings("CLOUDINARY_CLOUD_NAME", "")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.sign_stamp_image_upload(U5)
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert gus.call_count == 0


# [claude] PSM-SG-02
def test_psm_sg_02__empty_api_key_raises_before_signing(stamp_settings, gus, U5):
    """PSM-SG-02 — an empty API key raises before anything is signed.
    Rules: sign_stamp_image_upload R1, Errors row 1."""
    stamp_settings("CLOUDINARY_API_KEY", "")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.sign_stamp_image_upload(U5)
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert gus.call_count == 0


# [claude] PSM-SG-03
def test_psm_sg_03__empty_api_secret_raises_client_error(stamp_settings, U5):
    """PSM-SG-03 — an empty API secret raises the client's error.
    Rules: sign_stamp_image_upload R2, Errors row 2."""
    stamp_settings("CLOUDINARY_API_SECRET", "")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.sign_stamp_image_upload(U5)
    # Then 2
    assert (
        str(exc.value)
        == "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
    )


# [claude] PSM-SG-04
def test_psm_sg_04__response_holds_every_field(fixed_uuid, fixed_time, U5):
    """PSM-SG-04 — the response holds every field as stated.
    Rules: sign_stamp_image_upload R3."""
    result = M.sign_stamp_image_upload(U5)
    # Then 1
    assert result.cloud_name == "demo-cloud"
    assert result.api_key == "123456"
    # Then 2
    assert result.timestamp == 1767225600
    # Then 3
    assert (
        result.public_id
        == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"
    )
    # Then 4
    assert result.asset_folder == "Dev/Profile stamps/Ann Lee"
    # Then 5
    assert result.display_name == "saved-stamp"
    assert result.type == "authenticated"
    assert result.resource_type == "image"
    # Then 6
    assert (
        result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"
    )


# [claude] PSM-SG-05
def test_psm_sg_05__signature_signs_response_fields(fixed_uuid, fixed_time, U5):
    """PSM-SG-05 — the signature is the signature of the response's own fields.
    Rules: sign_stamp_image_upload R4."""
    result = M.sign_stamp_image_upload(U5)
    # Then 1
    assert result.signature == api_sign_request(
        {
            "timestamp": result.timestamp,
            "public_id": result.public_id,
            "asset_folder": result.asset_folder,
            "display_name": result.display_name,
            "type": "authenticated",
        },
        "s3cret",
    )
    # Then 2
    assert re.fullmatch(r"[0-9a-f]{40}", result.signature) is not None


# [claude] PSM-SG-06
def test_psm_sg_06__signer_receives_response_values(fixed_uuid, fixed_time, gus, U5):
    """PSM-SG-06 — the signer receives exactly the response's values.
    Rules: sign_stamp_image_upload R4."""
    result = M.sign_stamp_image_upload(U5)
    # Then 1
    assert result.signature == "sig-x"
    # Then 2
    assert gus.call_count == 1
    # Then 3
    assert (
        gus.call_args.kwargs["public_id"]
        == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"
    )
    # Then 4
    assert gus.call_args.kwargs["asset_folder"] == "Dev/Profile stamps/Ann Lee"
    # Then 5
    assert gus.call_args.kwargs["display_name"] == "saved-stamp"
    assert gus.call_args.kwargs["timestamp"] == 1767225600
    # Then 6
    assert gus.call_args.kwargs.get("delivery_type", "authenticated") == "authenticated"


# [claude] PSM-SG-07
def test_psm_sg_07__two_calls_differ_user_unchanged(U5):
    """PSM-SG-07 — two calls give different public ids; the user is not changed.
    Rules: sign_stamp_image_upload R5."""
    first = M.sign_stamp_image_upload(U5)
    result = M.sign_stamp_image_upload(U5)
    # Then 1
    assert result.public_id != first.public_id
    # Then 2
    assert vars(U5) == {"id": 5, "name": "Ann Lee"}


# --------------------------------------------------------------------------- #
# destroy_saved_stamp_image
# --------------------------------------------------------------------------- #


# [claude] PSM-DS-01
def test_psm_ds_01__none_deletes_nothing(dr):
    """PSM-DS-01 — None deletes nothing.
    Rules: destroy_saved_stamp_image R1."""
    result = M.destroy_saved_stamp_image(None)
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-02
def test_psm_ds_02__empty_dict_deletes_nothing(dr):
    """PSM-DS-02 — an empty dict deletes nothing.
    Rules: destroy_saved_stamp_image R1."""
    result = M.destroy_saved_stamp_image({})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-03
def test_psm_ds_03__vector_stamp_deletes_nothing(dr):
    """PSM-DS-03 — a vector stamp deletes nothing.
    Rules: destroy_saved_stamp_image R2."""
    result = M.destroy_saved_stamp_image({"kind": "vector", "public_id": OWN5})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-04
def test_psm_ds_04__stamp_without_kind_deletes_nothing(dr):
    """PSM-DS-04 — a stamp without kind deletes nothing.
    Rules: destroy_saved_stamp_image R2."""
    result = M.destroy_saved_stamp_image({"public_id": OWN5})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-05
def test_psm_ds_05__capital_image_kind_deletes_nothing(dr):
    """PSM-DS-05 — kind "IMAGE" in capitals deletes nothing.
    Rules: destroy_saved_stamp_image R2."""
    result = M.destroy_saved_stamp_image({"kind": "IMAGE", "public_id": OWN5})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-06
def test_psm_ds_06__image_without_public_id_deletes_nothing(dr):
    """PSM-DS-06 — an image stamp without public_id deletes nothing.
    Rules: destroy_saved_stamp_image R3."""
    result = M.destroy_saved_stamp_image({"kind": "image"})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-07
def test_psm_ds_07__public_id_none_deletes_nothing(dr):
    """PSM-DS-07 — public_id None deletes nothing.
    Rules: destroy_saved_stamp_image R3."""
    result = M.destroy_saved_stamp_image({"kind": "image", "public_id": None})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-08
def test_psm_ds_08__empty_public_id_deletes_nothing(dr):
    """PSM-DS-08 — public_id "" deletes nothing.
    Rules: destroy_saved_stamp_image R3."""
    result = M.destroy_saved_stamp_image({"kind": "image", "public_id": ""})
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-DS-09
def test_psm_ds_09__own_file_deleted_as_authenticated_image(dr):
    """PSM-DS-09 — the user's own stamp file is deleted as an authenticated image.
    Rules: destroy_saved_stamp_image R4."""
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    kw = dr.call_args.kwargs
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 1
    # Then 3
    assert kw["public_id"] == OWN5
    # Then 4
    assert kw.get("resource_type", "image") == "image"
    # Then 5
    assert kw.get("delivery_type", "authenticated") == "authenticated"


# [claude] PSM-DS-10
def test_psm_ds_10__not_configured_is_swallowed(dr):
    """PSM-DS-10 — "not configured" from Cloudinary is swallowed.
    Rules: destroy_saved_stamp_image R5."""
    dr.side_effect = CloudinaryNotConfiguredError("x")
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 1


# [claude] PSM-DS-11
def test_psm_ds_11__network_error_is_swallowed(dr):
    """PSM-DS-11 — a network error is swallowed.
    Rules: destroy_saved_stamp_image R5."""
    dr.side_effect = RuntimeError("network down")
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 1


# [claude] PSM-DS-12
def test_psm_ds_12__not_found_is_not_an_error_no_warning(dr, warnings_log):
    """PSM-DS-12 — a "not found" answer is not an error and logs no warning.
    Rules: destroy_saved_stamp_image R5, R5a."""
    dr.return_value = {"result": "not found"}
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    warnings = warnings_log()
    # Then 1
    assert result is None
    # Then 2
    assert dr.call_count == 1
    # Then 3
    assert warnings == []


# [claude] PSM-DS-13
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1713: a failed delete of the old stamp picture is silently ignored (no warning log)",
)
def test_psm_ds_13__failed_delete_logs_one_warning(dr, warnings_log):
    """PSM-DS-13 — a failed delete logs one warning naming the public_id and the error.
    Rules: destroy_saved_stamp_image R5a [BUG-1713]."""
    dr.side_effect = RuntimeError("network down")
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    warnings = warnings_log()
    # Then 1
    assert result is None
    # Then 2
    assert len(warnings) == 1
    # Then 3
    assert OWN5 in warnings[0].getMessage()
    # Then 4
    assert "network down" in warnings[0].getMessage()


# [claude] PSM-DS-14
def test_psm_ds_14__successful_delete_logs_no_warning(dr, warnings_log):
    """PSM-DS-14 — a successful delete logs no warning.
    Rules: destroy_saved_stamp_image R5a."""
    result = M.destroy_saved_stamp_image(IMG(OWN5))
    warnings = warnings_log()
    # Then 1
    assert result is None
    # Then 2
    assert warnings == []


# [claude] PSM-DS-15
def test_psm_ds_15__non_dict_raises_attribute_error(dr):
    """PSM-DS-15 — a non-dict value raises AttributeError.
    Rules: destroy_saved_stamp_image R6."""
    # Then 1
    with pytest.raises(AttributeError):
        M.destroy_saved_stamp_image("image")
    # Then 2
    assert dr.call_count == 0


BUG_1865 = "BUG-1865: destroy_saved_stamp_image deletes any public_id, also another user's or an attachment's file"


# [claude] PSM-DS-16
@pytest.mark.xfail(strict=True, reason=BUG_1865)
def test_psm_ds_16__own_file_still_deleted_with_user_id(dr):
    """PSM-DS-16 — with the user's id, the user's own file is still deleted.
    Rules: destroy_saved_stamp_image R4 [BUG-1865]."""
    # Then 1
    result = M.destroy_saved_stamp_image(IMG(OWN5), user_id=5)
    assert result is None
    # Then 2
    assert dr.call_count == 1
    # Then 3
    assert dr.call_args.kwargs["public_id"] == OWN5


@pytest.mark.xfail(strict=True, reason=BUG_1865)
@pytest.mark.parametrize(
    ("pid", "user_id"),
    [
        # [claude] PSM-DS-17 — another user's (higher id) stamp file is never deleted
        pytest.param("development/profiles/55/stamp-" + TOKEN, 5, id="PSM-DS-17"),
        # [claude] PSM-DS-18 — a caller with a higher id cannot delete the lower user's stamp file
        pytest.param(OWN5, 55, id="PSM-DS-18"),
        # [claude] PSM-DS-19 — an attachment's file is never deleted
        pytest.param("ws-12/9f2c" + TOKEN, 5, id="PSM-DS-19"),
        # [claude] PSM-DS-20 — the production form is foreign in development
        pytest.param("profiles/5/stamp-" + TOKEN, 5, id="PSM-DS-20"),
        # [claude] PSM-DS-21 — the prefix compare is case-sensitive
        pytest.param("Development/profiles/5/stamp-" + TOKEN, 5, id="PSM-DS-21"),
        # [claude] PSM-DS-22 — a leading space makes the id foreign
        pytest.param(" " + OWN5, 5, id="PSM-DS-22"),
        # [claude] PSM-DS-23 — the own prefix in the middle of the id is foreign
        pytest.param("ws-12/" + OWN5, 5, id="PSM-DS-23"),
        # [claude] PSM-DS-24 — the user's own folder but not a stamp file is foreign
        pytest.param("development/profiles/5/avatar-" + TOKEN, 5, id="PSM-DS-24"),
    ],
)
def test_psm_ds_17_to_24__foreign_file_never_deleted(dr, pid, user_id):
    """PSM-DS-17 .. PSM-DS-24 — a public_id outside the user's own stamp prefix is never deleted.
    Rules: destroy_saved_stamp_image R4a [BUG-1865]."""
    # Then 1
    result = M.destroy_saved_stamp_image(IMG(pid), user_id=user_id)
    assert result is None
    # Then 2
    assert dr.call_count == 0


@pytest.mark.xfail(strict=True, reason=BUG_1865)
@pytest.mark.parametrize(
    "pid",
    [
        # [claude] PSM-DS-25 — `stamp` without the dash is foreign
        pytest.param("development/profiles/5/stamp" + TOKEN, id="PSM-DS-25"),
        # [claude] PSM-DS-26 — the bare prefix (empty token) is foreign
        pytest.param(PRE5, id="PSM-DS-26"),
        # [claude] PSM-DS-27 — a token of 31 hex characters is foreign
        pytest.param(PRE5 + TOKEN31, id="PSM-DS-27"),
        # [claude] PSM-DS-28 — a token of 33 hex characters is foreign
        pytest.param(PRE5 + TOKEN33, id="PSM-DS-28"),
        # [claude] PSM-DS-29 — an upper-case hex token is foreign
        pytest.param(PRE5 + TOKENU, id="PSM-DS-29"),
        # [claude] PSM-DS-30 — a 32-character token with a non-hex letter is foreign
        pytest.param(PRE5 + TOKENG, id="PSM-DS-30"),
        # [claude] PSM-DS-31 — a suffix `.png` after a valid token is foreign
        pytest.param(OWN5 + ".png", id="PSM-DS-31"),
        # [claude] PSM-DS-32 — a suffix `/x` after a valid token is foreign
        pytest.param(OWN5 + "/x", id="PSM-DS-32"),
        # [claude] PSM-DS-33 — a trailing newline after a valid token is foreign (Revision 3)
        pytest.param(OWN5 + "\n", id="PSM-DS-33"),
    ],
)
def test_psm_ds_25_to_32__not_minted_form_never_deleted(dr, pid):
    """PSM-DS-25 .. PSM-DS-33 — an id that is not the user's prefix plus exactly 32 lowercase hex is never deleted.
    Rules: destroy_saved_stamp_image R4a [BUG-1865] (Revision 2; DS-33 Revision 3)."""
    # Then 1
    result = M.destroy_saved_stamp_image(IMG(pid), user_id=5)
    assert result is None
    # Then 2
    assert dr.call_count == 0


# --------------------------------------------------------------------------- #
# validate_saved_stamp_payload
# --------------------------------------------------------------------------- #


# [claude] PSM-VS-01
def test_psm_vs_01__none_gives_none(dr):
    """PSM-VS-01 — None gives None.
    Rules: validate_saved_stamp_payload R1."""
    result = M.validate_saved_stamp_payload(None)
    # Then 1
    assert result is None


# [claude] PSM-VS-02
def test_psm_vs_02__vector_dumped_unknown_keys_dropped(dr):
    """PSM-VS-02 — a vector stamp is returned as its dump, unknown keys dropped.
    Rules: validate_saved_stamp_payload R2."""
    payload = {
        "kind": "vector",
        "extra": 1,
        "strokes": [{"color": "#000000", "width": 0.5, "points": [], "junk": "x"}],
        "viewBox": {"width": 100, "height": 50},
    }
    result = M.validate_saved_stamp_payload(payload)
    # Then 1
    assert result == VEC
    # Then 2
    assert dr.call_count == 0


# [claude] PSM-VS-03
def test_psm_vs_03__strokes_default_to_empty_list(dr):
    """PSM-VS-03 — strokes default to an empty list.
    Rules: validate_saved_stamp_payload R2."""
    result = M.validate_saved_stamp_payload(
        {"kind": "vector", "viewBox": {"width": 100, "height": 50}}
    )
    # Then 1
    assert result == {
        "kind": "vector",
        "strokes": [],
        "viewBox": {"width": 100, "height": 50},
    }


# [claude] PSM-VS-04
def test_psm_vs_04__stroke_width_one_accepted(dr):
    """PSM-VS-04 — a stroke width of exactly 1 is accepted.
    Rules: validate_saved_stamp_payload R5 (boundary)."""
    result = M.validate_saved_stamp_payload(
        {
            "kind": "vector",
            "strokes": [{"color": "#000000", "width": 1, "points": []}],
            "viewBox": {"width": 100, "height": 50},
        }
    )
    # Then 1
    assert result["strokes"][0]["width"] == 1


# [claude] PSM-VS-05
def test_psm_vs_05__own_image_stamp_has_five_keys(dr):
    """PSM-VS-05 — an image stamp under the user's own prefix is returned with five keys, unknown keys dropped.
    Rules: validate_saved_stamp_payload R3, R4."""
    payload = IMG(OWN5)
    payload["extra"] = 1
    result = M.validate_saved_stamp_payload(payload)
    # Then 1
    assert set(result) == {"kind", "public_id", "url", "width", "height"}
    # Then 2
    assert result["kind"] == "image"
    assert result["public_id"] == OWN5
    # Then 3
    assert result["width"] == 10
    assert result["height"] == 10
    # Then 4
    assert dr.call_count == 0


# [claude] PSM-VS-06 (Revision 2: target schema)
def test_psm_vs_06__schema_accepts_public_id_512_chars(dr):
    """PSM-VS-06 — the image schema accepts a public_id of 512 characters.
    Rules: validate_saved_stamp_payload R4 (schema limit)."""
    result = SavedStampImage(
        kind="image", public_id="a" * 512, url="https://x/a", width=10, height=10
    )
    # Then 1
    assert result.public_id == "a" * 512


# [claude] PSM-VS-07 (Revision 2: target schema)
def test_psm_vs_07__schema_refuses_public_id_513_chars(dr):
    """PSM-VS-07 — the image schema refuses a public_id of 513 characters.
    Rules: validate_saved_stamp_payload R4, R5 (schema limit)."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        SavedStampImage(
            kind="image", public_id="a" * 513, url="https://x/a", width=10, height=10
        )


# [claude] PSM-VS-08
def test_psm_vs_08__empty_public_id_refused(dr):
    """PSM-VS-08 — an empty public_id is refused by the schema.
    Rules: validate_saved_stamp_payload R5, Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(IMG(""))


# [claude] PSM-VS-09
def test_psm_vs_09__width_zero_refused(dr):
    """PSM-VS-09 — width 0 is refused by the schema.
    Rules: validate_saved_stamp_payload R4, R5."""
    payload = IMG(OWN5)
    payload["width"] = 0
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(payload)


# [claude] PSM-VS-10
def test_psm_vs_10__url_2048_chars_accepted(dr):
    """PSM-VS-10 — a url of 2048 characters is accepted.
    Rules: validate_saved_stamp_payload R4."""
    payload = IMG(OWN5)
    payload["url"] = "https://x/" + "a" * 2038
    assert len(payload["url"]) == 2048
    result = M.validate_saved_stamp_payload(payload)
    # Then 1
    assert result["public_id"] == OWN5


# [claude] PSM-VS-11
def test_psm_vs_11__url_2049_chars_refused(dr):
    """PSM-VS-11 — a url of 2049 characters is refused by the schema.
    Rules: validate_saved_stamp_payload R4."""
    payload = IMG(OWN5)
    payload["url"] = "https://x/" + "a" * 2039
    assert len(payload["url"]) == 2049
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(payload)


# [claude] PSM-VS-12
def test_psm_vs_12__empty_url_refused(dr):
    """PSM-VS-12 — an empty url is refused by the schema.
    Rules: validate_saved_stamp_payload R4."""
    payload = IMG(OWN5)
    payload["url"] = ""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(payload)


# [claude] PSM-VS-13
def test_psm_vs_13__height_zero_refused_one_accepted(dr):
    """PSM-VS-13 — height 0 is refused; width and height 1 are accepted.
    Rules: validate_saved_stamp_payload R4."""
    ok = IMG(OWN5)
    ok["width"] = 1
    ok["height"] = 1
    bad = IMG(OWN5)
    bad["height"] = 0
    accepted = M.validate_saved_stamp_payload(ok)
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(bad)
    # Then 2
    assert accepted["width"] == 1
    assert accepted["height"] == 1


# [claude] PSM-VS-14
def test_psm_vs_14__vector_without_viewbox_refused(dr):
    """PSM-VS-14 — a vector without viewBox is refused by the schema.
    Rules: validate_saved_stamp_payload R5."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload({"kind": "vector", "strokes": []})


# [claude] PSM-VS-15
def test_psm_vs_15__viewbox_width_zero_refused(dr):
    """PSM-VS-15 — a viewBox width of 0 is refused by the schema.
    Rules: validate_saved_stamp_payload R5."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(
            {"kind": "vector", "viewBox": {"width": 0, "height": 50}}
        )


# [claude] PSM-VS-16
def test_psm_vs_16__stroke_width_above_one_refused(dr):
    """PSM-VS-16 — a stroke width above 1 is refused by the schema.
    Rules: validate_saved_stamp_payload R5."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(
            {
                "kind": "vector",
                "strokes": [{"color": "#000000", "width": 1.5, "points": []}],
                "viewBox": {"width": 100, "height": 50},
            }
        )


# [claude] PSM-VS-17
def test_psm_vs_17__stroke_width_zero_refused(dr):
    """PSM-VS-17 — a stroke width of 0 is refused by the schema.
    Rules: validate_saved_stamp_payload R5."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        M.validate_saved_stamp_payload(
            {
                "kind": "vector",
                "strokes": [{"color": "#000000", "width": 0, "points": []}],
                "viewBox": {"width": 100, "height": 50},
            }
        )


# [claude] PSM-VS-18
def test_psm_vs_18__empty_dict_raises_kind_error(dr):
    """PSM-VS-18 — an empty dict raises the kind error.
    Rules: validate_saved_stamp_payload R6, Errors row 1."""
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_saved_stamp_payload({})
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert str(exc.value) == KIND_MSG


# [claude] PSM-VS-19
def test_psm_vs_19__none_empty_text_kind_raise_kind_error(dr):
    """PSM-VS-19 — kind None, "" and "text" raise the kind error.
    Rules: validate_saved_stamp_payload R6."""
    errors = []
    for k in [None, "", "text"]:
        with pytest.raises(ValueError) as exc:
            M.validate_saved_stamp_payload(
                {"kind": k, "viewBox": {"width": 100, "height": 50}}
            )
        errors.append(exc.value)
    # Then 1
    for err in errors:
        assert type(err) is ValueError
    # Then 2
    for err in errors:
        assert str(err) == KIND_MSG


# [claude] PSM-VS-20
def test_psm_vs_20__kind_compared_exactly(dr):
    """PSM-VS-20 — kind is compared exactly: "Vector", "IMAGE" and " vector" raise the kind error.
    Rules: validate_saved_stamp_payload R6."""
    errors = []
    for k in ["Vector", "IMAGE", " vector"]:
        with pytest.raises(ValueError) as exc:
            M.validate_saved_stamp_payload(
                {
                    "kind": k,
                    "public_id": OWN5,
                    "url": "https://x/a",
                    "width": 10,
                    "height": 10,
                    "viewBox": {"width": 100, "height": 50},
                }
            )
        errors.append(exc.value)
    # Then 1
    for err in errors:
        assert type(err) is ValueError
    # Then 2
    for err in errors:
        assert str(err) == KIND_MSG


BUG_1864 = "BUG-1864: validate_saved_stamp_payload accepts any public_id, also another user's or an attachment's file"
BUG_1866 = "BUG-1866: the stamp url is taken from the client instead of being built from the public_id"


# [claude] PSM-VS-21
@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_psm_vs_21__own_stamp_accepted_with_user_id(dr):
    """PSM-VS-21 — with the user's id, the user's own stamp is accepted.
    Rules: validate_saved_stamp_payload R4, R4a [BUG-1864]."""
    # Then 1
    result = M.validate_saved_stamp_payload(IMG(OWN5), user_id=5)
    assert result["public_id"] == OWN5
    # Then 2
    assert result["kind"] == "image"


# [claude] PSM-VS-22
@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_psm_vs_22__higher_id_users_stamp_refused(dr):
    """PSM-VS-22 — another user's (higher id) stamp is refused.
    Rules: validate_saved_stamp_payload R4a [BUG-1864], Errors row 2."""
    payload = IMG("development/profiles/55/stamp-" + TOKEN)
    before = copy.deepcopy(payload)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_saved_stamp_payload(payload, user_id=5)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert str(exc.value) == FOREIGN_MSG
    # Then 4
    assert payload == before
    # Then 5
    assert dr.call_count == 0


@pytest.mark.xfail(strict=True, reason=BUG_1864)
@pytest.mark.parametrize(
    ("pid", "user_id", "upload_env"),
    [
        # [claude] PSM-VS-23 — a caller with a higher id cannot save the lower user's stamp
        pytest.param(OWN5, 55, None, id="PSM-VS-23"),
        # [claude] PSM-VS-24 — the user's own folder but an avatar file is refused
        pytest.param("development/profiles/5/avatar-" + TOKEN, 5, None, id="PSM-VS-24"),
        # [claude] PSM-VS-25 — the production form is refused in development
        pytest.param("profiles/5/stamp-" + TOKEN, 5, None, id="PSM-VS-25"),
        # [claude] PSM-VS-26 — another environment's prefix is refused
        pytest.param("production/profiles/5/stamp-" + TOKEN, 5, None, id="PSM-VS-26"),
        # [claude] PSM-VS-28 — the prefix compare is case-sensitive
        pytest.param("Development/profiles/5/stamp-" + TOKEN, 5, None, id="PSM-VS-28"),
        # [claude] PSM-VS-29 — a leading space makes the id foreign
        pytest.param(" " + OWN5, 5, None, id="PSM-VS-29"),
        # [claude] PSM-VS-30 — the own prefix in the middle of the id is refused
        pytest.param("ws-12/" + OWN5, 5, None, id="PSM-VS-30"),
        # [claude] PSM-VS-31 — `stamp` without the dash is refused
        pytest.param("development/profiles/5/stamp" + TOKEN, 5, None, id="PSM-VS-31"),
        # [claude] PSM-VS-33 — in production the development form is refused
        pytest.param(OWN5, 5, "production", id="PSM-VS-33"),
    ],
)
def test_psm_vs_foreign_public_id_refused(dr, stamp_settings, pid, user_id, upload_env):
    """PSM-VS-23 .. 26, 28 .. 31, 33 — a public_id outside the user's own stamp prefix is refused.
    Rules: validate_saved_stamp_payload R4a [BUG-1864]."""
    if upload_env is not None:
        stamp_settings("CLOUDINARY_UPLOAD_ENV", upload_env)
    payload = IMG(pid)
    before = copy.deepcopy(payload)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_saved_stamp_payload(payload, user_id=user_id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert str(exc.value) == FOREIGN_MSG
    # Then 4
    assert payload == before


# [claude] PSM-VS-27
@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_psm_vs_27__attachment_id_refused(dr):
    """PSM-VS-27 — an attachment's id is refused.
    Rules: validate_saved_stamp_payload R4a [BUG-1864]."""
    payload = IMG("ws-12/9f2c" + TOKEN)
    before = copy.deepcopy(payload)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_saved_stamp_payload(payload, user_id=5)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert str(exc.value) == FOREIGN_MSG
    # Then 4
    assert payload == before
    # Then 5
    assert dr.call_count == 0


# [claude] PSM-VS-32
@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_psm_vs_32__production_bare_own_id_accepted(dr, stamp_settings):
    """PSM-VS-32 — in production the bare form of the user's own id is accepted.
    Rules: validate_saved_stamp_payload R4a [BUG-1864]."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "production")
    # Then 1
    result = M.validate_saved_stamp_payload(IMG("profiles/5/stamp-" + TOKEN), user_id=5)
    assert result["public_id"] == "profiles/5/stamp-0123456789abcdef0123456789abcdef"


# [claude] PSM-VS-34
@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_psm_vs_34__prefix_follows_environment(dr, stamp_settings):
    """PSM-VS-34 — the prefix follows ENVIRONMENT when the upload environment is empty.
    Rules: validate_saved_stamp_payload R4a [BUG-1864]."""
    stamp_settings("CLOUDINARY_UPLOAD_ENV", "")
    stamp_settings("ENVIRONMENT", "staging")
    # Then 1
    result = M.validate_saved_stamp_payload(
        IMG("staging/profiles/5/stamp-" + TOKEN), user_id=5
    )
    assert (
        result["public_id"]
        == "staging/profiles/5/stamp-0123456789abcdef0123456789abcdef"
    )


# [claude] PSM-VS-35
@pytest.mark.xfail(strict=True, reason=BUG_1866)
def test_psm_vs_35__server_builds_url(dr):
    """PSM-VS-35 — the server builds the url; the client's url is ignored.
    Rules: validate_saved_stamp_payload R4b [BUG-1866]."""
    # Then 1
    result = M.validate_saved_stamp_payload(IMG(OWN5), user_id=5)
    assert result["url"].startswith(
        "https://res.cloudinary.com/demo-cloud/image/authenticated/"
    )
    # Then 2
    assert OWN5 in result["url"]
    # Then 3
    assert "tracker.example" not in result["url"]
    # Then 4
    assert result["public_id"] == OWN5


# [claude] PSM-VS-36
@pytest.mark.xfail(strict=True, reason=BUG_1866)
def test_psm_vs_36__client_url_on_other_cloud_ignored(dr):
    """PSM-VS-36 — the client's url on another Cloudinary account is ignored.
    Rules: validate_saved_stamp_payload R4b [BUG-1866]."""
    payload = IMG(OWN5)
    payload["url"] = "https://res.cloudinary.com/other-cloud/image/upload/x.png"
    # Then 1
    result = M.validate_saved_stamp_payload(payload, user_id=5)
    assert result["url"].startswith(
        "https://res.cloudinary.com/demo-cloud/image/authenticated/"
    )
    # Then 2
    assert OWN5 in result["url"]
    # Then 3
    assert "other-cloud" not in result["url"]
    # Then 4
    assert result["url"] != "https://res.cloudinary.com/other-cloud/image/upload/x.png"


# [claude] PSM-VS-37
@pytest.mark.xfail(strict=True, reason=BUG_1866)
def test_psm_vs_37__client_url_on_our_cloud_other_file_ignored(dr):
    """PSM-VS-37 — the client's url on our cloud but another file is ignored.
    Rules: validate_saved_stamp_payload R4b [BUG-1866]."""
    payload = IMG(OWN5)
    payload["url"] = "https://res.cloudinary.com/demo-cloud/image/upload/ws-12/9f2c.png"
    # Then 1
    result = M.validate_saved_stamp_payload(payload, user_id=5)
    assert result["url"].startswith(
        "https://res.cloudinary.com/demo-cloud/image/authenticated/"
    )
    # Then 2
    assert OWN5 in result["url"]
    # Then 3
    assert "ws-12" not in result["url"]
    # Then 4
    assert (
        result["url"]
        != "https://res.cloudinary.com/demo-cloud/image/upload/ws-12/9f2c.png"
    )


@pytest.mark.xfail(strict=True, reason=BUG_1864)
@pytest.mark.parametrize(
    "pid",
    [
        # [claude] PSM-VS-38 — the bare prefix (empty token) is refused
        pytest.param(PRE5, id="PSM-VS-38"),
        # [claude] PSM-VS-39 — a token of 31 hex characters is refused
        pytest.param(PRE5 + TOKEN31, id="PSM-VS-39"),
        # [claude] PSM-VS-40 — a token of 33 hex characters is refused
        pytest.param(PRE5 + TOKEN33, id="PSM-VS-40"),
        # [claude] PSM-VS-41 — an upper-case hex token is refused
        pytest.param(PRE5 + TOKENU, id="PSM-VS-41"),
        # [claude] PSM-VS-42 — a 32-character token with a non-hex letter is refused
        pytest.param(PRE5 + TOKENG, id="PSM-VS-42"),
        # [claude] PSM-VS-43 — a suffix `.png` after a valid token is refused
        pytest.param(OWN5 + ".png", id="PSM-VS-43"),
        # [claude] PSM-VS-44 — a suffix `/x` after a valid token is refused
        pytest.param(OWN5 + "/x", id="PSM-VS-44"),
        # [claude] PSM-VS-45 — a trailing newline after a valid token is refused (Revision 3)
        pytest.param(OWN5 + "\n", id="PSM-VS-45"),
    ],
)
def test_psm_vs_38_to_44__not_minted_form_refused(dr, pid):
    """PSM-VS-38 .. PSM-VS-45 — an id that is not the user's prefix plus exactly 32 lowercase hex is refused.
    Rules: validate_saved_stamp_payload R4a [BUG-1864], Errors row 2 (Revision 2; VS-45 Revision 3)."""
    payload = IMG(pid)
    before = copy.deepcopy(payload)
    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_saved_stamp_payload(payload, user_id=5)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert str(exc.value) == FOREIGN_MSG
    # Then 4
    assert payload == before
