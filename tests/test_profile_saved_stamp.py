"""Profile saved stamp tests."""
from unittest.mock import MagicMock

import pytest

from app.managers.profile_stamp_manager import ProfileStampManager
from app.schemas.saved_stamp import SavedStampVector


def test_validate_saved_stamp_vector() -> None:
    manager = ProfileStampManager()
    payload = {
        "kind": "vector",
        "strokes": [
            {
                "color": "#000000",
                "width": 0.02,
                "points": [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}],
            }
        ],
        "viewBox": {"width": 400, "height": 120},
    }
    result = manager.validate_saved_stamp_payload(payload)
    assert result is not None
    assert result["kind"] == "vector"
    SavedStampVector.model_validate(result)


def test_validate_saved_stamp_rejects_unknown_kind() -> None:
    manager = ProfileStampManager()
    with pytest.raises(ValueError, match="kind"):
        manager.validate_saved_stamp_payload({"kind": "pdf"})


def test_destroy_saved_stamp_image_skips_vector() -> None:
    manager = ProfileStampManager()
    manager.destroy_saved_stamp_image({"kind": "vector", "strokes": [], "viewBox": {"width": 1, "height": 1}})
