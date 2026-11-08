"""Production launch routes are registered."""


def test_production_launch_paths_exist() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/production-routes/" in paths
    assert "/api/v1/production-routes/{route_id}/steps/" in paths
    assert "/api/v1/production-batches/schedule/" in paths
    assert "/api/v1/production-batches/{batch_id}/linked-orders/" in paths
    assert "/api/v1/production-batches/stage-logs/{log_id}/start/" in paths
    assert "/api/v1/production-batches/stage-logs/{log_id}/finish/" in paths
    assert "/api/v1/production-batches/stage-logs/{log_id}/log-as-planned/" in paths
