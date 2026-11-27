"""Unit tests for app/managers/base_manager.py.

Implements tests/unit/managers/base_manager.cases.md (revision 3), one test per
card, in card order. The constructor takes no session, so no database row is
built and the `db` fixture is not used. Nothing is patched (no externals).
`# Then N` marks the checks of the card's Then line N.
"""
import pytest

from app.managers.base_manager import BaseManager
from app.managers.department_manager import DepartmentManager
from app.models.department import Department


def test_bmg_i_01__model_stored_as_only_attribute():
    """BMG-I-01 — the model passed is stored as the only attribute.
    Rules: __init__ R1."""
    result = BaseManager(Department)
    # Then 1
    assert result.model is Department
    # Then 2
    assert vars(result) == {"model": Department}


def test_bmg_i_02__none_stored_without_error():
    """BMG-I-02 — None is stored without an error.
    Rules: __init__ R2."""
    result = BaseManager(None)
    # Then 1
    assert result.model is None
    # Then 2
    assert vars(result) == {"model": None}


def test_bmg_i_03__string_or_any_object_stored_as_given():
    """BMG-I-03 — a string or any object is stored as given.
    Rules: __init__ R2."""
    S = object()
    result = BaseManager("x")
    # Then 1
    assert result.model == "x"
    # Then 2
    assert vars(result) == {"model": "x"}
    # Then 3
    assert BaseManager(S).model is S


def test_bmg_i_04__no_model_raises_type_error():
    """BMG-I-04 — no model raises TypeError.
    Rules: __init__ R3; Errors row "no model given"."""
    # Then 1
    with pytest.raises(TypeError) as exc:
        BaseManager()
    assert "missing 1 required positional argument: 'model'" in str(exc.value)


def test_bmg_i_05__subscripted_class_stores_model():
    """BMG-I-05 — the subscripted class stores the model the same way.
    Rules: __init__ R4."""
    result = BaseManager[Department](Department)
    # Then 1
    assert result.model is Department
    # Then 2
    assert vars(result)["model"] is Department
    # Then 3
    assert set(vars(result)) - {"__orig_class__"} == {"model"}


def test_bmg_i_06__subclass_gets_model_next_to_own_attributes():
    """BMG-I-06 — a subclass gets model next to its own attributes.
    Rules: __init__ R5."""
    result = DepartmentManager()
    # Then 1
    assert result.model is Department
    # Then 2
    assert set(vars(result)) == {"department_dao", "model"}
    # Then 3
    assert isinstance(result, BaseManager) is True
