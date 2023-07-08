from collections import namedtuple

import numpy as np

from inspec.chars import Char


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
            string += Char.FULL_0
        elif i < char_to_start and i + 1 > char_to_start:
            string += Char.QTR_0010
        elif i == char_to_start and char_width < 1:
            string += Char.QTR_1000
        elif i == char_to_start:
            string += Char.HALF_10
        elif i < char_to_start < i + 1:
            string += Char.QTR_0010
        elif i < char_to_end and i + 1 <= char_to_end:
            string += Char.HALF_10
        elif i < char_to_end and i + 1 > char_to_end:
            string += Char.QTR_1000
        else:
            string += Char.FULL_0

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


def db_scale(x, dB=None):
    """Scale the channels of a signal (in dB) independently"""
    return np.power(10.0, dB / 20.0) * x
