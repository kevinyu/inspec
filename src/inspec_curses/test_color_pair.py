from unittest import mock

import pytest
from inspec_curses import context
from inspec_curses.color_pair import ColorToSlot
from render import chars
from render.types import XTermColor


@pytest.fixture()
def mock_curses_colors():
    mock_curses_colors = {}

    def mock_init_pair(slot, fg, bg):
        mock_curses_colors[slot] = (fg, bg)

    with mock.patch("curses.init_pair", mock_init_pair):
        yield mock_curses_colors


def test_set_active(mock_curses_colors):
    # Test this by setting the slots (but mocking curses)
    color_to_slot = ColorToSlot(
        colors=[
            XTermColor(0),
            XTermColor(1),
            XTermColor(100),
            XTermColor(255),
        ]
    )
    context.set_active(color_to_slot.colors)

    assert set(mock_curses_colors.keys()) == {0, 1, 2, 3, 4, 5}
    assert mock_curses_colors[0] == (1, 0)
    assert mock_curses_colors[1] == (100, 0)
    assert mock_curses_colors[2] == (100, 1)
    assert mock_curses_colors[3] == (255, 0)
    assert mock_curses_colors[4] == (255, 1)
    assert mock_curses_colors[5] == (255, 100)


def test_color_to_slot(mock_curses_colors):
    # Test this by setting the slots (but mocking curses)
    color_to_slot = ColorToSlot(
        colors=[
            XTermColor(0),
            XTermColor(1),
            XTermColor(100),
            XTermColor(255),
        ]
    )
    context.set_active(color_to_slot.colors)

    slot, char = color_to_slot.convert(
        chars.QTR_0001,
        fg=XTermColor(0),
        bg=XTermColor(100),
    )

    # These are testing the implementation a bit (testing the character inversions)
    # but is necessary.
    assert char == str(chars.QTR_1110)
    assert mock_curses_colors[slot.value] == (100, 0)

    slot, char = color_to_slot.convert(
        chars.QTR_0001,
        fg=XTermColor(1),
        bg=XTermColor(1),
    )

    assert char == str(chars.FULL_1)
    assert mock_curses_colors[slot.value][0] == 1

    slot, char = color_to_slot.convert(
        chars.QTR_0001,
        fg=XTermColor(100),
        bg=XTermColor(1),
    )

    assert char == str(chars.QTR_0001)
    assert mock_curses_colors[slot.value] == (100, 1)

    slot, char = color_to_slot.convert(
        chars.QTR_0001,
        fg=XTermColor(0),
        bg=XTermColor(0),
    )

    assert char == str(chars.FULL_0)
    assert mock_curses_colors[slot.value][1] == 0
