import curses

import numpy as np

from inspec import const
from inspec.colormap import curses_cmap
from inspec.maps import Char


class CursesRenderError(Exception):
    pass


class BaseRenderer(object):

    @staticmethod
    def apply_cmap_to_char_array(cmap, char_array):
        """Applies a colormap to trasnslate float values in char_array to Color256s"""
        output_array = np.empty(char_array.shape, dtype=object)
        for i in range(output_array.shape[0]):
            for j in range(output_array.shape[1]):
                char = char_array[i, j]
                output_array[i, j] = Char(
                    char=char.char,
                    fg=cmap.scale_to_color(char.fg),
                    bg=cmap.scale_to_color(char.bg)
                )

        return output_array

    @staticmethod
    def render(char_array):
        raise NotImplementedError


class StdoutRenderer(BaseRenderer):

    @staticmethod
    def _ansi(fg_color=0, bg_color=0, reset=False):
        if reset:
            return "\u001b[0m"
        return "\u001b[38;5;{fg_color}m\u001b[48;5;{bg_color}m".format(fg_color=fg_color, bg_color=bg_color)

    @staticmethod
    def render(char_array):
        print()
        for row in char_array[::-1]:
            row_output = ""
            for char, fg_color, bg_color in row:
                row_output += StdoutRenderer._ansi(fg_color, bg_color) + char
            row_output += StdoutRenderer._ansi(reset=True)
            print(row_output)


class StdoutRGBRenderer(StdoutRenderer):

    @staticmethod
    def _ansi(fg_color=0, bg_color=0, reset=False):
        if reset:
            return "\u001b[0m"
        return ("\u001b[38;2;{fg_color[0]};{fg_color[1]};{fg_color[2]}m"
            "\u001b[48;2;{bg_color[0]};{bg_color[1]};{bg_color[2]}m".format(fg_color=fg_color, bg_color=bg_color))

    @staticmethod
    def render(char_array):
        print()
        for row in char_array[::-1]:
            row_output = ""
            for char, fg_color, bg_color in row:
                row_output += StdoutRGBRenderer._ansi(fg_color, bg_color) + char
            row_output += StdoutRenderer._ansi(reset=True)
            print(row_output)


class CursesRenderer(BaseRenderer):

    @staticmethod
    def apply_cmap_to_char_array(cmap, char_array):
        """Applies a colormap to trasnslate float values in char_array to ColorSlots"""
        curses_cmap.init_colormap(cmap)
        char_array = BaseRenderer.apply_cmap_to_char_array(cmap, char_array)

        output_array = np.empty(char_array.shape, dtype=object)
        for i in range(output_array.shape[0]):
            for j in range(output_array.shape[1]):
                char = char_array[i, j]
                slot, invert = curses_cmap.get_slot(char.fg, char.bg)
                if invert:
                    char_ = const.INVERT[char.char]
                elif char.fg.idx == char.bg.idx == 0:
                    char_ = const.FULL_0
                elif char.fg.idx == char.bg.idx != 0:
                    char_ = const.FULL_1
                else:
                    char_ = char.char

                output_array[i, j] = (char_, slot)

        return output_array

    @staticmethod
    def render(window, char_array, start_row=0, start_col=0):
        """Render a array of unicode characters with color slots to window
        """
        errored_on = 0
        for row in range(char_array.shape[0]):
            for col in range(char_array.shape[1]):
                char, slot = char_array[row, col]
                color = curses.color_pair(slot)
                try:
                    window.addstr(
                        start_row + char_array.shape[0] - row - 1,
                        start_col + col,
                        char,
                        color
                    )
                except curses.error:
                    errored_on += 1

        if errored_on > 1:
            raise CursesRenderError("Could not write to more than just the last character in window")
