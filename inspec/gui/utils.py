from collections import namedtuple

import numpy as np

from inspec import const


PositionSlider = namedtuple("PositionSlider", [
    "start",
    "end",
    "total"
])


def slider_to_character_positions(
        position_slider,
        n_chars):
    # Get the starting character to 1/2 character resolution
    char_to_start = np.round(2 * n_chars * position_slider.start / position_slider.total) / 2
    # Get the ending character to 1/2 character resolution
    char_to_end = np.round(2 * n_chars * position_slider.end / position_slider.total) / 2
    return char_to_start, char_to_end


def generate_position_slider(position_slider, n_chars):
    """Subdivide the characters into 8ths and draw progress"""
    n_chars -= 2
    char_to_start, char_to_end = slider_to_character_positions(
        position_slider,
        n_chars
    )

    char_width = char_to_end - char_to_start

    string = ""
    for i in range(n_chars):
        if i < char_to_start and i + 1 <= char_to_start:
            string += const.FULL_0
        elif i < char_to_start and i + 1 > char_to_start:
            string += const.QTR_0010
        elif i == char_to_start and char_width < 1:
            string += const.QTR_1000
        elif i == char_to_start:
            string += const.HALF_10
        elif i < char_to_start < i + 1:
            string += const.QTR_0010
        elif i < char_to_end and i + 1 <= char_to_end:
            string += const.HALF_10
        elif i < char_to_end and i + 1 > char_to_end:
            string += const.QTR_1000
        else:
            string += const.FULL_0

    return " {} ".format(string)


def pad_string(string, side="right", max_len=3, fill_char=" "):
    if side not in ("right", "left"):
        raise ValueError("side must be left or right")

    if side == "left":
        if len(string) < max_len:
            return string + fill_char * (max_len - len(string))
        else:
            return string[:max_len]
    elif side == "right":
        if len(string) < max_len:
            return fill_char * (max_len - len(string)) + string
        else:
            return string[-max_len:]
