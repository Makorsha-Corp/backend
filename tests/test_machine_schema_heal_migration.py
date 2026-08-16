"""113_heal_machine_tables is the single alembic head after the 112 merge."""
import os

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_heal_machine_tables_is_head() -> None:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "113_heal_machine_tables"
    rev = script.get_revision("113_heal_machine_tables")
    assert rev.down_revision == "112_merge_heads"
