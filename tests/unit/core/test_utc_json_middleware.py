"""Unit tests for app/core/utc_json_middleware.py.

Implements tests/unit/core/utc_json_middleware.cases.md (revision 2), one test
per case (parametrized cases keep one pytest.param id per case/variant).
Harness: a fresh minimal FastAPI() app per test with UtcJsonResponseMiddleware
and only the routes the case needs, called through starlette's TestClient
(default raise_server_exceptions=True). No database, no mocks.
"""
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import Response, StreamingResponse
from starlette.testclient import TestClient

from app.core.utc_json_middleware import UtcJsonResponseMiddleware

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Standard bodies"
B_COMPACT = b'{"a":"\xc3\xa9","b":1}'
B_PROCESSED = b'{"a": "\\u00e9", "b": 1}'
B_DT = b'{"a":"\xc3\xa9","t":"2026-01-05T09:30:00"}'
assert len(B_COMPACT) == 16 and len(B_PROCESSED) == 23 and len(B_DT) == 36

BUG_520 = "BUG-520: Free-text values shaped like a date-time get a \"Z\" appended"
BUG_521 = "BUG-521: Rebuilt JSON responses keep only the first of repeated headers"
BUG_522 = "BUG-522: JSON-labelled body that is not valid UTF-8 causes a 500"


# Convention "Harness": fresh minimal app with only this middleware
def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(UtcJsonResponseMiddleware)
    return app


def client_for(app: FastAPI) -> TestClient:
    return TestClient(app)


# Convention "Call counter": closure counter, reset to 0 at the start of the test
class Counter:
    def __init__(self):
        self.n = 0

    def hit(self):
        self.n += 1


# Convention "Repeated headers": append raw repeated lines
def with_repeated(resp: Response, name: str, values) -> Response:
    for v in values:
        resp.headers.append(name, v)
    return resp


def with_cookies(resp: Response) -> Response:
    return with_repeated(resp, "Set-Cookie", ["access=a", "refresh=r"])


# Convention "processed"
def assert_processed(response, expected_bytes: bytes):
    assert response.content == expected_bytes
    assert response.headers["content-length"] == str(len(response.content))


# --------------------------------------------------------------------------- #
# UtcJsonResponseMiddleware.dispatch
# --------------------------------------------------------------------------- #


def test_utcj_d_01__api_route_called_once():
    """UTCJ-D-01 — an /api/ request reaches the route once and its JSON comes back.
    Rules: dispatch R1."""
    app = make_app()
    counter = Counter()

    @app.get("/api/v1/count")
    def count():
        counter.hit()
        return JSONResponse({"a": 1})

    counter.n = 0
    r = client_for(app).get("/api/v1/count")
    assert r.status_code == 200
    assert r.json() == {"a": 1}
    assert counter.n == 1


def test_utcj_d_02__non_api_route_called_once():
    """UTCJ-D-02 — a non-/api/ request reaches the route once.
    Rules: dispatch R1."""
    app = make_app()
    counter = Counter()

    @app.get("/health")
    def health():
        counter.hit()
        return JSONResponse({"ok": True})

    counter.n = 0
    r = client_for(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert counter.n == 1


def test_utcj_d_03__downstream_exception_propagates():
    """UTCJ-D-03 — an unhandled route exception propagates unchanged.
    Rules: dispatch R1; Errors row 1."""
    app = make_app()
    counter = Counter()

    @app.get("/api/v1/boom")
    def boom():
        counter.hit()
        raise RuntimeError("boom")

    counter.n = 0
    with pytest.raises(RuntimeError) as exc:
        client_for(app).get("/api/v1/boom")
    assert type(exc.value) is RuntimeError
    assert str(exc.value) == "boom"
    assert counter.n == 1


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api", id="UTCJ-D-04-api-no-slash"),
        pytest.param("/apiv1/x", id="UTCJ-D-04-apiv1"),
        pytest.param("/", id="UTCJ-D-04-root"),
        pytest.param("/health", id="UTCJ-D-04-health"),
        pytest.param("/API/v1/x", id="UTCJ-D-04-uppercase"),
    ],
)
def test_utcj_d_04__non_api_paths_passed_through(path):
    """UTCJ-D-04 — paths not starting with /api/ are passed through byte-for-byte.
    Rules: dispatch R2."""
    app = make_app()

    @app.get(path)
    def route():
        return Response(content=B_DT, media_type="application/json")

    r = client_for(app).get(path)
    assert r.status_code == 200
    assert r.content == B_DT
    assert r.headers["content-length"] == "36"
    assert r.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/", id="UTCJ-D-05-api-slash"),
        pytest.param("/api/v1/anything", id="UTCJ-D-05-api-v1"),
    ],
)
def test_utcj_d_05__api_prefix_paths_processed(path):
    """UTCJ-D-05 — paths starting with /api/ are processed.
    Rules: dispatch R2."""
    app = make_app()

    @app.get(path)
    def route():
        return Response(content=B_COMPACT, media_type="application/json")

    r = client_for(app).get(path)
    assert r.status_code == 200
    assert r.content == B_PROCESSED
    assert r.headers["content-length"] == "23"
    assert r.json() == {"a": "é", "b": 1}


def test_utcj_d_06__non_api_keeps_repeated_headers():
    """UTCJ-D-06 — a passed-through non-/api/ response keeps repeated Set-Cookie lines.
    Rules: dispatch R2, R12."""
    app = make_app()

    @app.get("/health")
    def health():
        return with_cookies(Response(content=B_COMPACT, media_type="application/json"))

    r = client_for(app).get("/health")
    assert r.status_code == 200
    assert r.content == B_COMPACT
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]


@pytest.mark.parametrize(
    "mt",
    [
        pytest.param("text/plain", id="UTCJ-D-07-text-plain"),
        pytest.param("text/html", id="UTCJ-D-07-text-html"),
        pytest.param("application/pdf", id="UTCJ-D-07-pdf"),
        pytest.param("application/problem+json", id="UTCJ-D-07-problem-json"),
        pytest.param(None, id="UTCJ-D-07-no-content-type"),
    ],
)
def test_utcj_d_07__non_json_content_types_passed_through(mt):
    """UTCJ-D-07 — /api/ responses without application/json are passed through.
    Rules: dispatch R3."""
    app = make_app()

    @app.get("/api/v1/doc")
    def doc():
        return Response(content=B_DT, media_type=mt)

    r = client_for(app).get("/api/v1/doc")
    assert r.status_code == 200
    assert r.content == B_DT
    assert r.headers["content-length"] == "36"
    if mt is not None:
        assert r.headers["content-type"].startswith(mt)
    else:
        assert "content-type" not in r.headers


@pytest.mark.parametrize(
    "ct",
    [
        pytest.param("application/json", id="UTCJ-D-08-json"),
        pytest.param("application/json; charset=utf-8", id="UTCJ-D-08-json-charset"),
        pytest.param("application/json-patch+json", id="UTCJ-D-08-json-patch"),
    ],
)
def test_utcj_d_08__json_content_types_processed(ct):
    """UTCJ-D-08 — content types containing application/json are processed.
    Rules: dispatch R3."""
    app = make_app()

    @app.get("/api/v1/doc")
    def doc():
        return Response(content=B_COMPACT, headers={"content-type": ct})

    r = client_for(app).get("/api/v1/doc")
    assert r.status_code == 200
    assert r.content == B_PROCESSED
    assert r.headers["content-length"] == "23"
    assert r.headers["content-type"] == ct


def test_utcj_d_09__non_json_keeps_repeated_headers():
    """UTCJ-D-09 — a passed-through non-JSON /api/ response keeps repeated Set-Cookie lines.
    Rules: dispatch R3, R12."""
    app = make_app()

    @app.get("/api/v1/doc")
    def doc():
        return with_cookies(Response(content=b"plain text", media_type="text/plain"))

    r = client_for(app).get("/api/v1/doc")
    assert r.status_code == 200
    assert r.content == b"plain text"
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]


def test_utcj_d_10__streamed_chunks_joined_and_processed():
    """UTCJ-D-10 — a multi-chunk streamed JSON body is joined and processed.
    Rules: dispatch R4."""
    app = make_app()

    @app.get("/api/v1/stream")
    def stream():
        return StreamingResponse(
            iter([b'{"a":', b'"\xc3\xa9",', b'"b":1}']), media_type="application/json"
        )

    r = client_for(app).get("/api/v1/stream")
    assert r.status_code == 200
    assert_processed(r, B_PROCESSED)
    assert r.json() == {"a": "é", "b": 1}


def test_utcj_d_11__chunk_split_inside_utf8_char():
    """UTCJ-D-11 — a chunk boundary inside a 2-byte UTF-8 char still decodes correctly.
    Rules: dispatch R4."""
    app = make_app()

    @app.get("/api/v1/stream")
    def stream():
        return StreamingResponse(iter([b'{"a":"\xc3', b'\xa9"}']), media_type="application/json")

    r = client_for(app).get("/api/v1/stream")
    assert r.status_code == 200
    assert r.json() == {"a": "é"}
    assert r.content == b'{"a": "\\u00e9"}'
    assert r.headers["content-length"] == "15"


def test_utcj_d_12__empty_body_returned_as_is():
    """UTCJ-D-12 — an empty JSON body is returned unchanged with its headers.
    Rules: dispatch R5."""
    app = make_app()

    @app.get("/api/v1/empty")
    def empty():
        return Response(
            content=b"",
            status_code=200,
            media_type="application/json",
            headers={"X-Request-ID": "req-7"},
        )

    r = client_for(app).get("/api/v1/empty")
    assert r.status_code == 200
    assert r.content == b""
    assert r.headers["X-Request-ID"] == "req-7"
    assert r.headers["content-type"] == "application/json"


def test_utcj_d_13__204_no_content():
    """UTCJ-D-13 — a 204 JSON response with no body passes without error.
    Rules: dispatch R5."""
    app = make_app()

    @app.delete("/api/v1/items/1")
    def delete_item():
        return Response(status_code=204, media_type="application/json")

    r = client_for(app).delete("/api/v1/items/1")
    assert r.status_code == 204
    assert r.content == b""


def test_utcj_d_14__head_request():
    """UTCJ-D-14 — a HEAD request on a JSON route returns an empty body without error.
    Rules: dispatch R5."""
    app = make_app()

    @app.api_route("/api/v1/head", methods=["GET", "HEAD"])
    def head():
        return JSONResponse({"a": 1})

    r = client_for(app).head("/api/v1/head")
    assert r.status_code == 200
    assert r.content == b""
    assert r.headers["content-type"] == "application/json"


def test_utcj_d_15__zero_chunk_stream():
    """UTCJ-D-15 — a streamed JSON response with zero chunks passes without error.
    Rules: dispatch R4, R5."""
    app = make_app()

    @app.get("/api/v1/stream")
    def stream():
        return StreamingResponse(iter([]), media_type="application/json")

    r = client_for(app).get("/api/v1/stream")
    assert r.status_code == 200
    assert r.content == b""


def test_utcj_d_16__empty_body_keeps_repeated_headers():
    """UTCJ-D-16 — an empty-body JSON response keeps repeated Set-Cookie lines.
    Rules: dispatch R5, R12."""
    app = make_app()

    @app.get("/api/v1/empty")
    def empty():
        return with_cookies(Response(content=b"", status_code=200, media_type="application/json"))

    r = client_for(app).get("/api/v1/empty")
    assert r.status_code == 200
    assert r.content == b""
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(201, id="UTCJ-D-17-201"),
        pytest.param(400, id="UTCJ-D-17-400"),
        pytest.param(404, id="UTCJ-D-17-404"),
        pytest.param(422, id="UTCJ-D-17-422"),
        pytest.param(500, id="UTCJ-D-17-500"),
    ],
)
def test_utcj_d_17__any_status_processed(code):
    """UTCJ-D-17 — JSON bodies are processed whatever the status code, status kept.
    Rules: dispatch R6."""
    app = make_app()

    @app.get("/api/v1/s/{code}")
    def s(code: int):
        return Response(content=B_COMPACT, status_code=code, media_type="application/json")

    r = client_for(app).get(f"/api/v1/s/{code}")
    assert r.status_code == code
    assert r.content == B_PROCESSED
    assert r.headers["content-length"] == "23"


def test_utcj_d_18__http_exception_body_processed():
    """UTCJ-D-18 — FastAPI's HTTPException error body is processed.
    Rules: dispatch R6."""
    app = make_app()

    @app.get("/api/v1/missing")
    def missing():
        raise HTTPException(status_code=404, detail="café")

    r = client_for(app).get("/api/v1/missing")
    assert r.status_code == 404
    assert r.content == b'{"detail": "caf\\u00e9"}'
    assert r.json() == {"detail": "café"}
    assert r.headers["content-length"] == str(len(r.content))


def test_utcj_d_19__validation_error_body_processed():
    """UTCJ-D-19 — FastAPI's 422 validation body is processed.
    Rules: dispatch R6."""
    app = make_app()

    @app.get("/api/v1/q")
    def q(n: int):
        return {"n": n}

    r = client_for(app).get("/api/v1/q?n=abc")
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "n"]
    assert r.content == json.dumps(r.json()).encode()
    assert r.headers["content-length"] == str(len(r.content))


def test_utcj_d_20__malformed_json_passed_through():
    """UTCJ-D-20 — a JSON-labelled body that is not JSON is passed through with status/headers.
    Rules: dispatch R7, R10."""
    app = make_app()

    @app.get("/api/v1/bad")
    def bad():
        return Response(
            content=b"not json",
            status_code=202,
            media_type="application/json",
            headers={"X-Request-ID": "req-1"},
        )

    r = client_for(app).get("/api/v1/bad")
    assert r.status_code == 202
    assert r.content == b"not json"
    assert r.headers["content-length"] == "8"
    assert r.headers["content-type"] == "application/json"
    assert r.headers["X-Request-ID"] == "req-1"


def test_utcj_d_21__truncated_json_passed_through():
    """UTCJ-D-21 — a truncated JSON body is passed through with its status.
    Rules: dispatch R7."""
    app = make_app()

    @app.get("/api/v1/bad")
    def bad():
        return Response(content=b'{"a":', status_code=400, media_type="application/json")

    r = client_for(app).get("/api/v1/bad")
    assert r.status_code == 400
    assert r.content == b'{"a":'
    assert r.headers["content-length"] == "5"


@pytest.mark.xfail(strict=True, reason=BUG_522)
def test_utcj_d_22__undecodable_body_passed_through():
    """UTCJ-D-22 — a JSON-labelled non-UTF-8 body is passed through unchanged.
    Rules: dispatch R7a [BUG-522], R10."""
    app = make_app()

    @app.get("/api/v1/raw")
    def raw():
        return Response(
            content=b'"\xc3\x28"',
            status_code=200,
            media_type="application/json",
            headers={"X-Request-ID": "req-2"},
        )

    r = client_for(app).get("/api/v1/raw")  # fails today: UnicodeDecodeError raised
    assert r.status_code == 200
    assert r.content == b'"\xc3\x28"'
    assert r.headers["content-length"] == "4"
    assert r.headers["content-type"] == "application/json"
    assert r.headers["X-Request-ID"] == "req-2"


def test_utcj_d_23__non_naive_strings_and_scalars_unchanged():
    """UTCJ-D-23 — non-naive-date-time strings and non-string scalars are unchanged.
    Rules: dispatch R8."""
    app = make_app()
    value = {
        "z": "2026-01-05T09:30:00Z",
        "off": "2026-01-05T09:30:00+00:00",
        "d": "2026-01-05",
        "sp": "2026-01-05 09:30:00",
        "pre": "x2026-01-05T09:30:00",
        "h": "hello",
        "n": 42,
        "f": 1.5,
        "t": True,
        "fa": False,
        "nu": None,
    }

    @app.get("/api/v1/vals")
    def vals():
        return JSONResponse(value)

    r = client_for(app).get("/api/v1/vals")
    assert r.status_code == 200
    body = r.json()
    assert body == value
    assert type(body["n"]) is int and type(body["f"]) is float
    assert body["t"] is True and body["fa"] is False and body["nu"] is None


def test_utcj_d_24__keys_never_changed():
    """UTCJ-D-24 — dictionary keys shaped like date-times are not changed; key order kept.
    Rules: dispatch R8."""
    app = make_app()

    @app.get("/api/v1/keys")
    def keys():
        return JSONResponse({"2026-01-05T09:30:00": 1, "k": "hello"})

    r = client_for(app).get("/api/v1/keys")
    assert r.status_code == 200
    assert r.json() == {"2026-01-05T09:30:00": 1, "k": "hello"}
    assert list(r.json().keys()) == ["2026-01-05T09:30:00", "k"]


def test_utcj_d_25__nested_structure_unchanged():
    """UTCJ-D-25 — a nested dict/list structure comes back equal.
    Rules: dispatch R8."""
    app = make_app()
    value = {"a": {"b": [{"c": "2026-01-05T09:30:00Z"}, ["hello", 1, None, True]]}}

    @app.get("/api/v1/nest")
    def nest():
        return JSONResponse(value)

    r = client_for(app).get("/api/v1/nest")
    assert r.status_code == 200
    assert r.json() == value


def test_utcj_d_26__top_level_list_unchanged():
    """UTCJ-D-26 — a top-level list body comes back equal.
    Rules: dispatch R8."""
    app = make_app()
    value = ["2026-01-05", "hello", 1, True, None, {"x": "2026-01-05T09:30:00+00:00"}]

    @app.get("/api/v1/list")
    def lst():
        return JSONResponse(value)

    r = client_for(app).get("/api/v1/list")
    assert r.status_code == 200
    assert r.json() == value


def test_utcj_d_27__top_level_string_unchanged():
    """UTCJ-D-27 — a top-level plain string body comes back unchanged.
    Rules: dispatch R8."""
    app = make_app()

    @app.get("/api/v1/str")
    def s():
        return Response(content=b'"hello"', media_type="application/json")

    r = client_for(app).get("/api/v1/str")
    assert r.status_code == 200
    assert r.json() == "hello"
    assert r.content == b'"hello"'


def test_utcj_d_28__near_miss_shapes_unchanged():
    """UTCJ-D-28 — strings not wholly in the naive date-time shape are unchanged.
    Rules: dispatch R8."""
    app = make_app()
    value = {"suffix": "2026-01-05T09:30:00x", "nosec": "2026-01-05T09:30"}

    @app.get("/api/v1/near")
    def near():
        return JSONResponse(value)

    r = client_for(app).get("/api/v1/near")
    assert r.status_code == 200
    assert r.json() == value


@pytest.mark.xfail(strict=True, reason=BUG_520)
def test_utcj_d_29__free_text_datetime_shape_unchanged():
    """UTCJ-D-29 — a free-text value shaped like a naive date-time is not given a Z.
    Rules: dispatch R8a [BUG-520]."""
    app = make_app()

    @app.get("/api/v1/note")
    def note():
        return JSONResponse({"note": "2026-01-05T09:30:00"})

    r = client_for(app).get("/api/v1/note")
    assert r.status_code == 200
    assert r.json() == {"note": "2026-01-05T09:30:00"}


@pytest.mark.xfail(strict=True, reason=BUG_520)
def test_utcj_d_30__fractional_seconds_unchanged():
    """UTCJ-D-30 — a naive date-time with fractional seconds in a list is not given a Z.
    Rules: dispatch R8a [BUG-520]."""
    app = make_app()

    @app.get("/api/v1/frac")
    def frac():
        return JSONResponse(["2026-01-05T09:30:00.123456"])

    r = client_for(app).get("/api/v1/frac")
    assert r.status_code == 200
    assert r.json() == ["2026-01-05T09:30:00.123456"]


@pytest.mark.xfail(strict=True, reason=BUG_520)
def test_utcj_d_31__top_level_datetime_string_unchanged():
    """UTCJ-D-31 — a top-level naive date-time string body is not given a Z.
    Rules: dispatch R8a [BUG-520]."""
    app = make_app()

    @app.get("/api/v1/str")
    def s():
        return Response(content=b'"2026-01-05T09:30:00"', media_type="application/json")

    r = client_for(app).get("/api/v1/str")
    assert r.status_code == 200
    assert r.json() == "2026-01-05T09:30:00"


@pytest.mark.xfail(strict=True, reason=BUG_520)
def test_utcj_d_32__deeply_nested_datetime_unchanged():
    """UTCJ-D-32 — a deeply nested naive date-time string is not given a Z.
    Rules: dispatch R8a [BUG-520]."""
    app = make_app()
    value = {"a": {"b": [{"c": "2026-01-05T09:30:00"}]}, "h": "hello"}

    @app.get("/api/v1/deep")
    def deep():
        return JSONResponse(value)

    r = client_for(app).get("/api/v1/deep")
    assert r.status_code == 200
    assert r.json() == value


def test_utcj_d_33__reserialized_with_json_dumps_defaults_order_kept():
    """UTCJ-D-33 — the body is re-serialized with json.dumps defaults; key order kept.
    Rules: dispatch R9."""
    app = make_app()

    @app.get("/api/v1/order")
    def order():
        return Response(
            content=b'{"b":1,"a":{"y":[1,2],"x":"\xc3\xa9"}}', media_type="application/json"
        )

    r = client_for(app).get("/api/v1/order")
    assert r.status_code == 200
    assert r.content == b'{"b": 1, "a": {"y": [1, 2], "x": "\\u00e9"}}'
    assert list(r.json().keys()) == ["b", "a"]
    assert list(r.json()["a"].keys()) == ["y", "x"]


def test_utcj_d_34__status_and_headers_kept_length_recomputed():
    """UTCJ-D-34 — a rebuilt response keeps status, content-type and custom headers; length recomputed.
    Rules: dispatch R10."""
    app = make_app()

    @app.post("/api/v1/items")
    def items():
        return Response(
            content=B_COMPACT,
            status_code=201,
            headers={"content-type": "application/json; charset=utf-8", "X-Request-ID": "req-42"},
        )

    r = client_for(app).post("/api/v1/items")
    assert r.status_code == 201
    assert r.content == B_PROCESSED
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    assert r.headers["X-Request-ID"] == "req-42"
    assert r.headers["content-length"] == "23"


def test_utcj_d_35__growing_body_not_truncated():
    """UTCJ-D-35 — a body that grows on re-encoding is not truncated.
    Rules: dispatch R11."""
    app = make_app()

    @app.get("/api/v1/grow")
    def grow():
        return Response(content=b'{"a":"\xc3\xa9"}', media_type="application/json")

    r = client_for(app).get("/api/v1/grow")
    assert r.status_code == 200
    assert r.content == b'{"a": "\\u00e9"}'
    assert r.headers["content-length"] == "15"
    assert r.json() == {"a": "é"}


def test_utcj_d_36__shrinking_body_length_recomputed():
    """UTCJ-D-36 — a body that shrinks on re-encoding gets the new length.
    Rules: dispatch R11."""
    app = make_app()

    @app.get("/api/v1/shrink")
    def shrink():
        return Response(content=b'{ "a" :   1 ,\n  "b" : 2 }', media_type="application/json")

    r = client_for(app).get("/api/v1/shrink")
    assert r.status_code == 200
    assert r.content == b'{"a": 1, "b": 2}'
    assert r.headers["content-length"] == "16"
    assert r.json() == {"a": 1, "b": 2}


def test_utcj_d_37__stream_without_length_gets_length():
    """UTCJ-D-37 — a processed stream with no downstream content-length gets one.
    Rules: dispatch R11, R10."""
    app = make_app()

    @app.get("/api/v1/stream")
    def stream():
        return StreamingResponse(iter([b'{"a":', b"1}"]), media_type="application/json")

    r = client_for(app).get("/api/v1/stream")
    assert r.status_code == 200
    assert r.content == b'{"a": 1}'
    assert r.headers["content-length"] == "8"


@pytest.mark.xfail(strict=True, reason=BUG_521)
def test_utcj_d_38__rebuilt_keeps_repeated_set_cookie():
    """UTCJ-D-38 — a rewritten JSON response keeps both Set-Cookie lines.
    Rules: dispatch R10a [BUG-521], R10."""
    app = make_app()

    @app.get("/api/v1/login")
    def login():
        return with_cookies(
            Response(
                content=B_COMPACT,
                media_type="application/json",
                headers={"X-Request-ID": "req-3"},
            )
        )

    r = client_for(app).get("/api/v1/login")
    assert r.status_code == 200
    assert r.content == B_PROCESSED
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]  # fails today
    assert r.headers["X-Request-ID"] == "req-3"


@pytest.mark.xfail(strict=True, reason=BUG_521)
def test_utcj_d_39__rebuilt_keeps_repeated_vary():
    """UTCJ-D-39 — a rewritten JSON response keeps both Vary lines.
    Rules: dispatch R10a [BUG-521]."""
    app = make_app()

    @app.get("/api/v1/vary")
    def vary():
        return with_repeated(
            Response(content=B_COMPACT, media_type="application/json"),
            "Vary",
            ["Accept", "Origin"],
        )

    r = client_for(app).get("/api/v1/vary")
    assert r.status_code == 200
    assert r.content == B_PROCESSED
    assert r.headers.get_list("vary") == ["Accept", "Origin"]  # fails today


@pytest.mark.xfail(strict=True, reason=BUG_521)
def test_utcj_d_40__malformed_passthrough_keeps_repeated_set_cookie():
    """UTCJ-D-40 — a malformed-JSON pass-through keeps both Set-Cookie lines.
    Rules: dispatch R10a [BUG-521], R7."""
    app = make_app()

    @app.get("/api/v1/bad")
    def bad():
        return with_cookies(
            Response(content=b"not json", status_code=202, media_type="application/json")
        )

    r = client_for(app).get("/api/v1/bad")
    assert r.status_code == 202
    assert r.content == b"not json"
    assert r.headers["content-length"] == "8"
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]  # fails today


@pytest.mark.xfail(strict=True, reason=f"{BUG_522}; {BUG_521}")
def test_utcj_d_41__undecodable_passthrough_keeps_repeated_set_cookie():
    """UTCJ-D-41 — an undecodable pass-through keeps both Set-Cookie lines.
    Rules: dispatch R10a [BUG-521], R7a [BUG-522]."""
    app = make_app()

    @app.get("/api/v1/raw")
    def raw():
        return with_cookies(
            Response(content=b'"\xc3\x28"', status_code=200, media_type="application/json")
        )

    r = client_for(app).get("/api/v1/raw")  # fails today: UnicodeDecodeError raised
    assert r.status_code == 200
    assert r.content == b'"\xc3\x28"'
    assert r.headers.get_list("set-cookie") == ["access=a", "refresh=r"]
