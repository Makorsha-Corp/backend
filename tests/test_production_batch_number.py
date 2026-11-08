"""Production batch number generation (B-YYYY-NNN)."""

from app.dao.production_batch import production_batch_dao


def test_sequence_from_batch_number_accepts_standard_and_legacy():
    assert production_batch_dao.sequence_from_batch_number("B-2026-085", 2026) == 85
    assert production_batch_dao.sequence_from_batch_number("BATCH-2026-085", 2026) == 85
    assert production_batch_dao.sequence_from_batch_number("2026-085", 2026) == 85
    assert production_batch_dao.sequence_from_batch_number("B-2026-085", 2025) is None
    assert production_batch_dao.sequence_from_batch_number("B-1", 2026) is None
