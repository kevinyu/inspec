import curses

import numpy as np
from numpy.typing import NDArray

from inspec.chars import Char
from inspec.colormap import PairedColormap, get_slot, set_curses_cmap
from inspec.maps import CharWithColor, CharWithColor256


class CursesRenderError(Exception):
    pass


class BaseRenderer:
    @staticmethod
    def apply_cmap_to_char_array(
        cmap: PairedColormap, char_array: NDArray[CharWithColor]  # type: ignore
    ) -> NDArray[CharWithColor256]:  # type: ignore
        """Applies a colormap to trasnslate float values in char_array to Color256s"""
        output_array = np.empty(char_array.shape, dtype=object)
        for i in range(output_array.shape[0]):
            for j in range(output_array.shape[1]):
                char: CharWithColor = char_array[i, j]

                output_array[i, j] = CharWithColor256(
                    char=char.char,
                    fg=cmap.scale_to_color(char.fg),
                    bg=cmap.scale_to_color(char.bg),
                )

        return output_array

    @staticmethod
    def render(char_array):
        raise NotImplementedError


class StdoutRenderer(BaseRenderer):
    @staticmethod
    def _ansi(fg_color: int = 0, bg_color: int = 0, reset=False):
        if reset:
            return "\u001b[0m"
        return "\u001b[38;5;{fg_color}m\u001b[48;5;{bg_color}m".format(
            fg_color=fg_color, bg_color=bg_color
        )

    @staticmethod
    def render(char_array: NDArray[CharWithColor256]):  # type: ignore
        print()
        for row in char_array[::-1]:
            row_output = ""
            for char_with_color in row:
                char_with_color: CharWithColor256
                row_output += (
                    StdoutRenderer._ansi(
                        char_with_color.fg,
                        char_with_color.bg,
                    )
                    + char_with_color.char
                )
            row_output += StdoutRenderer._ansi(reset=True)
            print(row_output)


class CursesRenderer(BaseRenderer):
    @staticmethod
    def apply_cmap_to_char_array(
        cmap: PairedColormap, char_array: NDArray[CharWithColor]  # type: ignore
    ) -> NDArray[CharWithColor256]:  # type: ignore
        """Applies a colormap to trasnslate float values in char_array to ColorSlots"""
        set_curses_cmap(cmap)
        char_array = BaseRenderer.apply_cmap_to_char_array(cmap, char_array)

        output_array = np.empty(char_array.shape, dtype=object)
        for i in range(output_array.shape[0]):
            for j in range(output_array.shape[1]):
                char: CharWithColor256 = char_array[i, j]
                slot, invert = get_slot(char.fg, char.bg)
                if invert:
                    char_ = char.char.invert()
                elif char.fg.idx == char.bg.idx == 0:
                    char_ = Char.FULL_0
                elif char.fg.idx == char.bg.idx != 0:
                    char_ = Char.FULL_1
                else:
                    char_ = char.char

                output_array[i, j] = (char_, slot)

        return output_array

    @staticmethod
    def render(
        window: curses.window,
        char_array: NDArray[CharWithColor256],  # type: ignore
        start_row=0,
        start_col=0,
    ):
        """Render a array of unicode characters with color slots to window"""
        errored_on = 0
        for row in range(char_array.shape[0]):
            for col in range(char_array.shape[1]):
                char, slot = char_array[row, col]
                char: CharWithColor256
                color = curses.color_pair(slot)
                try:
                    window.addstr(
                        start_row + char_array.shape[0] - row - 1,
                        start_col + col,
                        str(char),
                        color,
                    )
                except curses.error:
                    errored_on += 1

        if errored_on > 1:
            raise CursesRenderError(
                "Could not write to more than just the last character in window"
            )
