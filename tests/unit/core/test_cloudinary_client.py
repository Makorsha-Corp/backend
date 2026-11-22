"""Unit tests for app/core/cloudinary_client.py.

Implements tests/unit/core/cloudinary_client.cases.md (revision 2), one test
per case. No database: the module is pure or calls Cloudinary (spec Overview).
Only mocks: the four Cloudinary SDK externals listed in the spec
(`cloudinary.api.resource`, `cloudinary.api.update`,
`cloudinary.uploader.destroy`, `cloudinary.uploader.rename`), replaced with
recording fakes. `cloudinary.utils.api_sign_request` / `cloudinary_url` are real.
"""
import copy
import hashlib
import inspect
import re

import cloudinary
import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import cloudinary.utils
import pytest

from app.core import cloudinary_client as cc
from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.core.config import settings

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "MSG"
MSG = (
    "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
    "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
)

# Convention "SIGSEG"
SIGSEG = r"s--[^/]{8}--"
SPEC_URL_SIG = "s--5pmR91cm--"
URL01 = "https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg"
UPLOAD_AB = "https://res.cloudinary.com/demo/image/upload/v123/a/b.jpg"


# Convention "Recipe SHA(str)"
def SHA(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()


# Convention "SDK global config": prev values, restored after the test
PREV = {"cloud_name": "prev-cloud", "api_key": "prev-key",
        "api_secret": "prev-secret", "secure": False}


@pytest.fixture(autouse=True)
def _sdk_config():
    saved = copy.deepcopy(vars(cloudinary._config))
    cloudinary.config(**PREV)
    yield
    cloudinary._config.__dict__.clear()
    cloudinary._config.__dict__.update(saved)


def cfg() -> dict:
    c = cloudinary.config()
    return {"cloud_name": c.cloud_name, "api_key": c.api_key,
            "api_secret": c.api_secret, "secure": c.secure}


def assert_config_unchanged():
    assert cfg() == PREV


def assert_config_set(cloud="demo", key="k", secret="s"):
    c = cloudinary.config()
    assert c.cloud_name == cloud
    assert c.api_key == key
    assert c.api_secret == secret
    assert c.secure is True


# Convention "Credentials (default: demo / k / s)"
def set_creds(mp, cloud="demo", key="k", secret="s"):
    mp.setattr(settings, "CLOUDINARY_CLOUD_NAME", cloud)
    mp.setattr(settings, "CLOUDINARY_API_KEY", key)
    mp.setattr(settings, "CLOUDINARY_API_SECRET", secret)


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    set_creds(monkeypatch)


# Convention "Externals mocked in every test": recording fakes; the default
# fake raises AssertionError("unexpected Cloudinary call").
_EXTERNALS = {
    "resource": (cloudinary.api, "resource"),
    "update": (cloudinary.api, "update"),
    "destroy": (cloudinary.uploader, "destroy"),
    "rename": (cloudinary.uploader, "rename"),
}
_ORIGINALS = {name: getattr(mod, attr) for name, (mod, attr) in _EXTERNALS.items()}


class Fake:
    """Recording fake for one SDK function."""

    def __init__(self, name, returns=None, raises=None, unexpected=False):
        self.name = name
        self.returns = returns
        self.raises = raises
        self.unexpected = unexpected
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.unexpected:
            raise AssertionError("unexpected Cloudinary call")
        if self.raises is not None:
            raise self.raises
        return self.returns

    def received(self) -> dict:
        """'SDK received X': exactly one call, bound to the ORIGINAL signature."""
        assert len(self.calls) == 1
        args, kwargs = self.calls[0]
        bound = inspect.signature(_ORIGINALS[self.name]).bind(*args, **kwargs)
        return dict(bound.arguments)


class SDK:
    def __init__(self, mp):
        self._mp = mp
        self.fakes = {}
        for name in _EXTERNALS:
            self.install(name, Fake(name, unexpected=True))

    def install(self, name, fake):
        mod, attr = _EXTERNALS[name]
        self._mp.setattr(mod, attr, fake)
        self.fakes[name] = fake
        return fake

    def returning(self, name, resp):
        return self.install(name, Fake(name, returns=resp))

    def raising(self, name, exc):
        return self.install(name, Fake(name, raises=exc))

    def total_calls(self, exclude=()):
        return sum(len(f.calls) for n, f in self.fakes.items() if n not in exclude)


@pytest.fixture(autouse=True)
def sdk(monkeypatch):
    return SDK(monkeypatch)


# --------------------------------------------------------------------------- #
# _ensure_configured
# --------------------------------------------------------------------------- #

def test_cld_ens_01__configures_sdk_when_creds_ok():
    """CLD-ENS-01 — creds OK: returns None and writes the SDK global config with secure=True.
    Rules: _ensure_configured R3."""
    assert cfg() == PREV
    assert cc._ensure_configured() is None
    assert_config_set()


@pytest.mark.parametrize(
    ("cloud", "key", "secret"),
    [
        pytest.param("", "k", "s", id="CLD-ENS-02"),
        pytest.param("demo", "", "s", id="CLD-ENS-03"),
        pytest.param("demo", "k", "", id="CLD-ENS-04"),
        pytest.param("", "", "", id="CLD-ENS-05"),
        pytest.param("demo", None, "s", id="CLD-ENS-06"),
    ],
)
def test_cld_ens_02_to_06__missing_credential_raises(monkeypatch, cloud, key, secret, request):
    """CLD-ENS-02..06 — any falsy credential raises CloudinaryNotConfiguredError(MSG); config unchanged.
    Rules: _ensure_configured R1, R4; Errors row 1."""
    set_creds(monkeypatch, cloud, key, secret)
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc._ensure_configured()
    assert str(exc.value) == MSG
    if request.node.callspec.id == "CLD-ENS-02":
        assert isinstance(exc.value, RuntimeError)
    assert_config_unchanged()


def test_cld_ens_07__whitespace_counts_as_configured(monkeypatch):
    """CLD-ENS-07 — whitespace-only credentials are accepted and loaded into the SDK.
    Rules: _ensure_configured R2, R3."""
    set_creds(monkeypatch, " ", " ", " ")
    assert cc._ensure_configured() is None
    assert_config_set(" ", " ", " ")


# --------------------------------------------------------------------------- #
# generate_upload_signature
# --------------------------------------------------------------------------- #

def test_cld_sig_01__spec_example():
    """CLD-SIG-01 — spec example signature (empty asset_folder omitted, default type).
    Rules: generate_upload_signature R2, R3, R5."""
    got = cc.generate_upload_signature(
        public_id="p", asset_folder="", display_name="d", timestamp=1)
    assert got == "510bdebded8f7df0736f986c8d03a6408d67923f"


def test_cld_sig_02__recipe_and_side_effect():
    """CLD-SIG-02 — signature matches the SHA-1 recipe and api_sign_request; SDK config set.
    Rules: generate_upload_signature R2, R4 (resource_type not signed), side effect."""
    got = cc.generate_upload_signature(
        public_id="ws1/att-9", asset_folder="ws1/attachments",
        display_name="invoice.pdf", timestamp=1700000000, delivery_type="authenticated")
    assert isinstance(got, str)
    assert len(got) == 40
    assert re.fullmatch(r"^[0-9a-f]{40}$", got)
    assert got == SHA(
        "asset_folder=ws1/attachments&display_name=invoice.pdf&public_id=ws1/att-9"
        "&timestamp=1700000000&type=authenticated" + "s")
    assert got == cloudinary.utils.api_sign_request(
        {"timestamp": 1700000000, "public_id": "ws1/att-9",
         "asset_folder": "ws1/attachments", "display_name": "invoice.pdf",
         "type": "authenticated"}, "s")
    assert_config_set()


def test_cld_sig_03__ampersand_escaped():
    """CLD-SIG-03 — '&' inside a value is signed as %26.
    Rules: generate_upload_signature R2."""
    got = cc.generate_upload_signature(
        public_id="p", asset_folder="f", display_name="a&b", timestamp=1, delivery_type="upload")
    assert got == SHA("asset_folder=f&display_name=a%26b&public_id=p&timestamp=1&type=upload" + "s")
    assert got != SHA("asset_folder=f&display_name=a&b&public_id=p&timestamp=1&type=upload" + "s")


def _sig(**over):
    kw = {"public_id": "p", "asset_folder": "f", "display_name": "d",
          "timestamp": 1, "delivery_type": "upload"}
    kw.update(over)
    return cc.generate_upload_signature(**kw)


def test_cld_sig_04__empty_strings_omitted():
    """CLD-SIG-04 — an empty string parameter is left out of the signed string.
    Rules: generate_upload_signature R3."""
    a = _sig(asset_folder="")
    b = _sig(display_name="")
    c = _sig(public_id="")
    assert a == SHA("display_name=d&public_id=p&timestamp=1&type=upload" + "s")
    assert b == SHA("asset_folder=f&public_id=p&timestamp=1&type=upload" + "s")
    assert c == SHA("asset_folder=f&display_name=d&timestamp=1&type=upload" + "s")
    full = _sig()
    assert full == SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s")
    assert full != a
    assert full != b
    assert full != c


def test_cld_sig_05__timestamp_zero_omitted():
    """CLD-SIG-05 — timestamp=0 is left out of the signed string.
    Rules: generate_upload_signature R3."""
    t0 = _sig(timestamp=0)
    t1 = _sig(timestamp=1)
    assert t0 == SHA("asset_folder=f&display_name=d&public_id=p&type=upload" + "s")
    assert t1 == SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s")
    assert t0 != t1


def test_cld_sig_06__each_param_changes_signature():
    """CLD-SIG-06 — changing any one of the five parameters changes the signature.
    Rules: generate_upload_signature R4."""
    base = _sig()
    variants = [
        _sig(public_id="p2"),
        _sig(asset_folder="f2"),
        _sig(display_name="d2"),
        _sig(timestamp=2),
        _sig(delivery_type="authenticated"),
    ]
    for v in variants:
        assert v != base
    assert len({base, *variants}) == 6


def test_cld_sig_07__secret_changes_signature(monkeypatch):
    """CLD-SIG-07 — a different API secret gives a different signature.
    Rules: generate_upload_signature R4 (secret)."""
    first = _sig()
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", "s2")
    second = _sig()
    assert first != second
    assert second == SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s2")


def test_cld_sig_08__default_delivery_type_is_authenticated():
    """CLD-SIG-08 — omitted delivery_type signs type=authenticated.
    Rules: generate_upload_signature R5."""
    base = {"public_id": "p", "asset_folder": "f", "display_name": "d", "timestamp": 1}
    none = cc.generate_upload_signature(**base)
    auth = cc.generate_upload_signature(**base, delivery_type="authenticated")
    upl = cc.generate_upload_signature(**base, delivery_type="upload")
    assert none == auth
    assert none == SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=authenticated" + "s")
    assert upl != none


def test_cld_sig_09__deterministic():
    """CLD-SIG-09 — same inputs give the same signature.
    Rules: generate_upload_signature R6."""
    assert _sig() == _sig()


def test_cld_sig_10__missing_secret_raises(monkeypatch, sdk):
    """CLD-SIG-10 — incomplete creds raise before signing; config unchanged; no SDK call.
    Rules: generate_upload_signature R1; Errors; _ensure_configured R5."""
    set_creds(monkeypatch, "demo", "k", "")
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc.generate_upload_signature(
            public_id="p", asset_folder="f", display_name="d", timestamp=1)
    assert str(exc.value) == MSG
    assert_config_unchanged()
    assert sdk.total_calls() == 0


# --------------------------------------------------------------------------- #
# build_signed_delivery_url
# --------------------------------------------------------------------------- #

def _url(**over):
    kw = {"public_id": "a/b", "resource_type": "image", "delivery_type": "authenticated",
          "version": 123, "fmt": "jpg"}
    kw.update(over)
    return cc.build_signed_delivery_url(**kw)


def _sigseg(url):
    m = re.search(r"/image/authenticated/(" + SIGSEG + r")/", url)
    assert m is not None
    return m.group(1)


def test_cld_url_01__signed_spec_example():
    """CLD-URL-01 — authenticated URL equals the spec's signed example; SDK config set.
    Rules: build_signed_delivery_url R2, R4, side effect."""
    got = _url()
    assert isinstance(got, str)
    assert got == URL01
    assert_config_set()


def test_cld_url_02__upload_is_unsigned():
    """CLD-URL-02 — upload delivery type gives an unsigned URL.
    Rules: build_signed_delivery_url R3, R4 (Q1)."""
    got = _url(public_id="ws/invoice-1", delivery_type="upload", fmt="pdf")
    assert got == "https://res.cloudinary.com/demo/image/upload/v123/ws/invoice-1.pdf"
    assert "s--" not in got


def test_cld_url_03__private_is_unsigned():
    """CLD-URL-03 — private delivery type gives an unsigned URL.
    Rules: build_signed_delivery_url R3."""
    got = _url(delivery_type="private")
    assert got == "https://res.cloudinary.com/demo/image/private/v123/a/b.jpg"
    assert re.search(SIGSEG, got) is None


def test_cld_url_04__case_sensitive_match():
    """CLD-URL-04 — 'Authenticated' (different case) is not signed.
    Rules: build_signed_delivery_url R2/R3 (exact match)."""
    got = _url(delivery_type="Authenticated")
    assert got == "https://res.cloudinary.com/demo/image/Authenticated/v123/a/b.jpg"
    assert re.search(SIGSEG, got) is None


def test_cld_url_05__cloud_name_and_resource_type_in_path(monkeypatch):
    """CLD-URL-05 — URL uses the configured cloud name and resource type.
    Rules: build_signed_delivery_url R4."""
    set_creds(monkeypatch, "acme-co", "k", "s")
    a = _url(public_id="docs/x", resource_type="raw", delivery_type="upload", version=7, fmt="pdf")
    b = _url(public_id="docs/x", resource_type="raw", delivery_type="authenticated", version=7, fmt="pdf")
    assert a == "https://res.cloudinary.com/acme-co/raw/upload/v7/docs/x.pdf"
    assert re.fullmatch(
        r"^https://res\.cloudinary\.com/acme-co/raw/authenticated/s--[^/]{8}--/v7/docs/x\.pdf$", b)


def test_cld_url_06__transformation():
    """CLD-URL-06 — non-empty transformation rendered; [] and None add nothing.
    Rules: build_signed_delivery_url R5."""
    a = _url(delivery_type="upload", transformation=[{"width": 400, "crop": "limit"}])
    b = _url(delivery_type="upload", transformation=[])
    c = _url(delivery_type="upload", transformation=None)
    assert a == "https://res.cloudinary.com/demo/image/upload/c_limit,w_400/v123/a/b.jpg"
    assert b == UPLOAD_AB
    assert c == UPLOAD_AB


def test_cld_url_07__flags():
    """CLD-URL-07 — non-empty flags rendered as fl_<flags>; '' and None add nothing.
    Rules: build_signed_delivery_url R6."""
    a = _url(delivery_type="upload", flags="attachment")
    b = _url(delivery_type="upload", flags="")
    c = _url(delivery_type="upload", flags=None)
    assert a == "https://res.cloudinary.com/demo/image/upload/fl_attachment/v123/a/b.jpg"
    assert b == UPLOAD_AB
    assert c == UPLOAD_AB
    assert "fl_" not in b
    assert "fl_" not in c


def test_cld_url_08__transformation_and_flags_unsigned():
    """CLD-URL-08 — unsigned URL with transformation and flags (spec example).
    Rules: build_signed_delivery_url R5, R6."""
    got = _url(delivery_type="upload", transformation=[{"width": 400, "crop": "limit"}],
               flags="attachment")
    assert got == "https://res.cloudinary.com/demo/image/upload/c_limit,w_400/fl_attachment/v123/a/b.jpg"


def test_cld_url_09__transformation_and_flags_signed():
    """CLD-URL-09 — signed URL with transformation and flags; signature differs from the plain one.
    Rules: build_signed_delivery_url R2, R5, R6."""
    got = _url(transformation=[{"width": 400, "crop": "limit"}], flags="attachment")
    assert re.fullmatch(
        r"^https://res\.cloudinary\.com/demo/image/authenticated/s--[^/]{8}--"
        r"/c_limit,w_400/fl_attachment/v123/a/b\.jpg$", got)
    assert _sigseg(got) != SPEC_URL_SIG


def test_cld_url_10__empty_transformation_and_flags_signed():
    """CLD-URL-10 — signed path: [] transformation and '' flags add nothing.
    Rules: build_signed_delivery_url R2, R5, R6."""
    a = _url(transformation=[])
    b = _url(flags="")
    assert a == URL01
    assert b == URL01


def test_cld_url_11__signature_depends_on_secret(monkeypatch):
    """CLD-URL-11 — secret 't' gives the known signature s--IoFgbQBd-- (differs from secret 's').
    Rules: build_signed_delivery_url R2 (depends on secret)."""
    set_creds(monkeypatch, "demo", "k", "t")
    got = _url()
    assert got == "https://res.cloudinary.com/demo/image/authenticated/s--IoFgbQBd--/v123/a/b.jpg"
    assert _sigseg(got) != SPEC_URL_SIG


def test_cld_url_12__signature_depends_on_path():
    """CLD-URL-12 — changing public id, format, flags or transformation gives the known signatures.
    Rules: build_signed_delivery_url R2 (depends on signed path)."""
    b = _url(public_id="a/c")
    c = _url(fmt="png")
    d = _url(flags="attachment")
    e = _url(transformation=[{"width": 400, "crop": "limit"}])
    assert b == "https://res.cloudinary.com/demo/image/authenticated/s--5J5IkvPG--/v123/a/c.jpg"
    assert c == "https://res.cloudinary.com/demo/image/authenticated/s--KeyAQbUE--/v123/a/b.png"
    assert d == ("https://res.cloudinary.com/demo/image/authenticated/s--LQNPH1Ob--"
                 "/fl_attachment/v123/a/b.jpg")
    assert e == ("https://res.cloudinary.com/demo/image/authenticated/s--6_QbkIb2--"
                 "/c_limit,w_400/v123/a/b.jpg")
    for url in (b, c, d, e):
        assert _sigseg(url) != SPEC_URL_SIG


def test_cld_url_13__deterministic():
    """CLD-URL-13 — same inputs give the same URL.
    Rules: build_signed_delivery_url R7."""
    kw = {"transformation": [{"width": 400, "crop": "limit"}], "flags": "attachment"}
    assert _url(**kw) == _url(**kw)


def test_cld_url_14__missing_cloud_name_raises(monkeypatch, sdk):
    """CLD-URL-14 — incomplete creds raise before building; config unchanged; no SDK call.
    Rules: build_signed_delivery_url R1; Errors; _ensure_configured R5."""
    set_creds(monkeypatch, "", "k", "s")
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        _url()
    assert str(exc.value) == MSG
    assert_config_unchanged()
    assert sdk.total_calls() == 0


def test_cld_url_15__version_not_signed():
    """CLD-URL-15 — version is not signed: v123 and v124 share s--5pmR91cm--.
    Rules: build_signed_delivery_url R2a, R4."""
    a = _url(version=123)
    b = _url(version=124)
    assert a == "https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg"
    assert b == "https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v124/a/b.jpg"
    assert _sigseg(a) == _sigseg(b)
    assert a.replace("/v123/", "/v124/") == b


# --------------------------------------------------------------------------- #
# get_resource
# --------------------------------------------------------------------------- #

def test_cld_get_01__passes_args_returns_response(sdk):
    """CLD-GET-01 — resource lookup gets public_id/resource_type/type only; response returned as-is.
    Rules: get_resource R2, R4."""
    RESP = {"public_id": "ws1/att-9", "bytes": 1234}
    fake = sdk.returning("resource", RESP)
    got = cc.get_resource(public_id="ws1/att-9", resource_type="raw", delivery_type="upload")
    assert got is RESP
    assert fake.received() == {"public_id": "ws1/att-9",
                               "options": {"resource_type": "raw", "type": "upload"}}
    assert sdk.total_calls(exclude=("resource",)) == 0


def test_cld_get_02__defaults(sdk):
    """CLD-GET-02 — defaults are resource_type=image, type=authenticated.
    Rules: get_resource R3."""
    RESP = {"public_id": "x"}
    fake = sdk.returning("resource", RESP)
    got = cc.get_resource(public_id="x")
    assert got is RESP
    assert fake.received() == {"public_id": "x",
                               "options": {"resource_type": "image", "type": "authenticated"}}


def test_cld_get_03__sdk_not_found_propagates(sdk):
    """CLD-GET-03 — SDK NotFound propagates unchanged.
    Rules: get_resource R5; Errors (SDK)."""
    E = cloudinary.exceptions.NotFound("Resource not found - x")
    sdk.raising("resource", E)
    with pytest.raises(cloudinary.exceptions.NotFound) as exc:
        cc.get_resource(public_id="x")
    assert exc.value is E


def test_cld_get_04__network_error_propagates(sdk):
    """CLD-GET-04 — non-SDK exceptions propagate unchanged, not wrapped.
    Rules: get_resource R5."""
    E = ConnectionError("network down")
    sdk.raising("resource", E)
    with pytest.raises(ConnectionError) as exc:
        cc.get_resource(public_id="x")
    assert exc.value is E
    assert not isinstance(exc.value, CloudinaryNotConfiguredError)


def test_cld_get_05__missing_key_no_call(monkeypatch, sdk):
    """CLD-GET-05 — incomplete creds raise and Cloudinary is not contacted.
    Rules: get_resource R1; Errors; _ensure_configured R5."""
    set_creds(monkeypatch, "demo", "", "s")
    fake = sdk.returning("resource", {})
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc.get_resource(public_id="x")
    assert str(exc.value) == MSG
    assert len(fake.calls) == 0


# --------------------------------------------------------------------------- #
# destroy_resource
# --------------------------------------------------------------------------- #

def test_cld_del_01__passes_args_returns_response(sdk):
    """CLD-DEL-01 — destroy gets public_id/resource_type/type/invalidate=True; response returned as-is.
    Rules: destroy_resource R2, R4."""
    RESP = {"result": "ok"}
    fake = sdk.returning("destroy", RESP)
    got = cc.destroy_resource(public_id="ws1/att-9", resource_type="raw", delivery_type="upload")
    assert got is RESP
    assert fake.received() == {
        "public_id": "ws1/att-9",
        "options": {"resource_type": "raw", "type": "upload", "invalidate": True}}


def test_cld_del_02__defaults(sdk):
    """CLD-DEL-02 — defaults are resource_type=image, type=authenticated.
    Rules: destroy_resource R3."""
    RESP = {"result": "ok"}
    fake = sdk.returning("destroy", RESP)
    got = cc.destroy_resource(public_id="x")
    assert got is RESP
    assert fake.received() == {
        "public_id": "x",
        "options": {"resource_type": "image", "type": "authenticated", "invalidate": True}}


def test_cld_del_03__not_found_result_does_not_raise(sdk):
    """CLD-DEL-03 — a 'not found' result is returned, not raised.
    Rules: destroy_resource R4."""
    RESP = {"result": "not found"}
    sdk.returning("destroy", RESP)
    got = cc.destroy_resource(public_id="missing")
    assert got is RESP
    assert got == {"result": "not found"}


def test_cld_del_04__sdk_error_propagates(sdk):
    """CLD-DEL-04 — SDK Error propagates unchanged.
    Rules: destroy_resource R5; Errors (SDK)."""
    E = cloudinary.exceptions.Error("boom")
    sdk.raising("destroy", E)
    with pytest.raises(cloudinary.exceptions.Error) as exc:
        cc.destroy_resource(public_id="x")
    assert exc.value is E


def test_cld_del_05__missing_secret_no_call(monkeypatch, sdk):
    """CLD-DEL-05 — secret None raises and destroy is not called.
    Rules: destroy_resource R1; Errors."""
    set_creds(monkeypatch, "demo", "k", None)
    fake = sdk.returning("destroy", {"result": "ok"})
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc.destroy_resource(public_id="x")
    assert str(exc.value) == MSG
    assert len(fake.calls) == 0


# --------------------------------------------------------------------------- #
# rename_resource
# --------------------------------------------------------------------------- #

def test_cld_ren_01__passes_args_returns_response(sdk):
    """CLD-REN-01 — rename gets ids, resource_type, type, to_type, invalidate; no overwrite.
    Rules: rename_resource R2, R4."""
    RESP = {"public_id": "ws1/att/abc"}
    fake = sdk.returning("rename", RESP)
    got = cc.rename_resource(from_public_id="ws1/tmp/abc", to_public_id="ws1/att/abc",
                             resource_type="raw", delivery_type="upload")
    assert got is RESP
    received = fake.received()
    assert received == {
        "from_public_id": "ws1/tmp/abc", "to_public_id": "ws1/att/abc",
        "options": {"resource_type": "raw", "type": "upload", "to_type": "upload",
                    "invalidate": True}}
    assert "overwrite" not in received["options"]


def test_cld_ren_02__defaults(sdk):
    """CLD-REN-02 — defaults are resource_type=image, type/to_type=authenticated.
    Rules: rename_resource R3."""
    RESP = {"public_id": "b"}
    fake = sdk.returning("rename", RESP)
    got = cc.rename_resource(from_public_id="a", to_public_id="b")
    assert got is RESP
    assert fake.received() == {
        "from_public_id": "a", "to_public_id": "b",
        "options": {"resource_type": "image", "type": "authenticated",
                    "to_type": "authenticated", "invalidate": True}}


def test_cld_ren_03__sdk_error_propagates(sdk):
    """CLD-REN-03 — SDK BadRequest propagates unchanged.
    Rules: rename_resource R4; Errors (SDK)."""
    E = cloudinary.exceptions.BadRequest("to_public_id already exists")
    sdk.raising("rename", E)
    with pytest.raises(cloudinary.exceptions.BadRequest) as exc:
        cc.rename_resource(from_public_id="a", to_public_id="b")
    assert exc.value is E


def test_cld_ren_04__missing_cloud_no_call(monkeypatch, sdk):
    """CLD-REN-04 — incomplete creds raise and rename is not called.
    Rules: rename_resource R1; Errors."""
    set_creds(monkeypatch, "", "k", "s")
    fake = sdk.returning("rename", {})
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc.rename_resource(from_public_id="a", to_public_id="b")
    assert str(exc.value) == MSG
    assert len(fake.calls) == 0


# --------------------------------------------------------------------------- #
# update_resource_metadata
# --------------------------------------------------------------------------- #

def test_cld_upd_01__all_fields_sent(sdk):
    """CLD-UPD-01 — update gets resource_type, type, asset_folder, display_name; response as-is.
    Rules: update_resource_metadata R2, R3, R4, R6."""
    RESP = {"public_id": "ws1/att-9"}
    fake = sdk.returning("update", RESP)
    got = cc.update_resource_metadata(
        public_id="ws1/att-9", resource_type="raw", delivery_type="upload",
        asset_folder="ws1/attachments", display_name="invoice.pdf")
    assert got is RESP
    assert fake.received() == {
        "public_id": "ws1/att-9",
        "options": {"resource_type": "raw", "type": "upload",
                    "asset_folder": "ws1/attachments", "display_name": "invoice.pdf"}}


def test_cld_upd_02__defaults_still_sent(sdk):
    """CLD-UPD-02 — with both None the update is still sent with only resource_type/type.
    Rules: update_resource_metadata R2, R5, defaults."""
    RESP = {}
    fake = sdk.returning("update", RESP)
    got = cc.update_resource_metadata(public_id="x")
    assert got is RESP
    assert len(fake.calls) == 1
    received = fake.received()
    assert received == {"public_id": "x",
                        "options": {"resource_type": "image", "type": "authenticated"}}
    assert "asset_folder" not in received["options"]
    assert "display_name" not in received["options"]


def test_cld_upd_03__empty_asset_folder_sent(sdk):
    """CLD-UPD-03 — asset_folder '' is sent; display_name omitted.
    Rules: update_resource_metadata R3."""
    RESP = {}
    fake = sdk.returning("update", RESP)
    got = cc.update_resource_metadata(public_id="x", asset_folder="")
    assert got is RESP
    received = fake.received()
    assert received == {"public_id": "x",
                        "options": {"resource_type": "image", "type": "authenticated",
                                    "asset_folder": ""}}
    assert "display_name" not in received["options"]


def test_cld_upd_04__empty_display_name_sent(sdk):
    """CLD-UPD-04 — display_name '' is sent; asset_folder omitted.
    Rules: update_resource_metadata R4."""
    RESP = {}
    fake = sdk.returning("update", RESP)
    got = cc.update_resource_metadata(public_id="x", display_name="")
    assert got is RESP
    received = fake.received()
    assert received == {"public_id": "x",
                        "options": {"resource_type": "image", "type": "authenticated",
                                    "display_name": ""}}
    assert "asset_folder" not in received["options"]


def test_cld_upd_05__sdk_error_propagates(sdk):
    """CLD-UPD-05 — SDK NotFound propagates unchanged.
    Rules: update_resource_metadata R6; Errors (SDK)."""
    E = cloudinary.exceptions.NotFound("Resource not found - x")
    sdk.raising("update", E)
    with pytest.raises(cloudinary.exceptions.NotFound) as exc:
        cc.update_resource_metadata(public_id="x", display_name="n")
    assert exc.value is E


def test_cld_upd_06__missing_key_no_call(monkeypatch, sdk):
    """CLD-UPD-06 — incomplete creds raise and update is not called.
    Rules: update_resource_metadata R1; Errors."""
    set_creds(monkeypatch, "demo", "", "s")
    fake = sdk.returning("update", {})
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        cc.update_resource_metadata(public_id="x", asset_folder="f")
    assert str(exc.value) == MSG
    assert len(fake.calls) == 0
