"""Production line machine membership helpers."""
from app.utils.production_line_response import mirror_machine_id_column


def test_mirror_machine_id_single():
    assert mirror_machine_id_column([42]) == 42


def test_mirror_machine_id_multiple_or_empty():
    assert mirror_machine_id_column([1, 2]) is None
    assert mirror_machine_id_column([]) is None
