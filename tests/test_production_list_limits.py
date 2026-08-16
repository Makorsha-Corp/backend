"""Production list routes must accept the factories-overview page size."""


def test_production_lines_list_allows_limit_1000() -> None:
    from app.main import app

    params = app.openapi()["paths"]["/api/v1/production-lines/"]["get"]["parameters"]
    limit = next(p for p in params if p["name"] == "limit")
    assert limit["schema"]["maximum"] == 1000


def test_production_batches_list_allows_limit_1000() -> None:
    from app.main import app

    params = app.openapi()["paths"]["/api/v1/production-batches/"]["get"]["parameters"]
    limit = next(p for p in params if p["name"] == "limit")
    assert limit["schema"]["maximum"] == 1000
