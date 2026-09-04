"""113_heal_machine_tables sits directly on the 112 merge, and the alembic
chain has exactly one head (guards against a repeat of the fork this repo
has hit before, where two branches independently added revisions on top of
the same down_revision)."""
import os

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_heal_machine_tables_is_head() -> None:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1
    rev = script.get_revision("113_heal_machine_tables")
    assert rev.down_revision == "112_merge_heads"
