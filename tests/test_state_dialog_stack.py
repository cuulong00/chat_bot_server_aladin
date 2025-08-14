import pytest

from src.graphs.state.state import update_dialog_stack


def test_ignore_empty_list_update():
    left = ["assistant"]
    right = []  # empty list should be ignored
    assert update_dialog_stack(left, right) == left


def test_accept_non_empty_list_as_absolute_set():
    left = ["assistant"]
    right = ["book_hotel"]
    assert update_dialog_stack(left, right) == ["book_hotel"]


def test_reject_non_string_in_list_update():
    left = ["assistant"]
    right = ["flight_assistant", 123]
    assert update_dialog_stack(left, right) == left


def test_pop_behavior():
    left = ["assistant", "book_hotel"]
    right = "pop"
    assert update_dialog_stack(left, right) == ["assistant"]


def test_depth_limit_on_append():
    # When at max depth (5), appending should drop the oldest
    left = ["a", "b", "c", "d", "e"]
    right = "f"
    assert update_dialog_stack(left, right) == ["b", "c", "d", "e", "f"]
