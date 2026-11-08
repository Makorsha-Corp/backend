"""Production role → catalog tag mapping and seed tags."""
from app.db.seed_default_tags import DEFAULT_SYSTEM_TAGS, get_default_tag_codes
from app.utils.item_catalog_tags import catalog_tag_code_for_production_role


def test_default_tags_include_waste_and_byproduct() -> None:
    codes = get_default_tag_codes()
    assert "waste" in codes
    assert "byproduct" in codes
    assert len(DEFAULT_SYSTEM_TAGS) == 8


def test_catalog_tag_code_for_production_role() -> None:
    assert catalog_tag_code_for_production_role("input") == "raw_material"
    assert catalog_tag_code_for_production_role("output") == "finished_good"
    assert catalog_tag_code_for_production_role("waste") == "waste"
    assert catalog_tag_code_for_production_role("byproduct") == "byproduct"
    assert catalog_tag_code_for_production_role("unknown") is None
