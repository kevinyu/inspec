import os

import numpy as np

from inspec import const, var
from inspec.plugins.colormap import curses_cmap, load_cmap

from .base import BaseAudioPlugin, SoundFileMixin


class BaseAsciiAmplitudePlugin(BaseAudioPlugin, SoundFileMixin):

    def __init__(self):
        super().__init__()
        self.cmap = load_cmap(var.DEFAULT_CMAP)

    def set_cmap(self, cmap):
        self.cmap = load_cmap(cmap)

    def receive(self, data):
        raise NotImplementedError

    def size_available(self):
        """Return half the screen vertically
        """
        size = os.get_terminal_size()
        return (
            int(var.PRINT_AMP_TERMINAL_Y_FRAC * size.lines * 2),
            int(var.PRINT_AMP_TERMINAL_X_FRAC * size.columns * 2)
        )

    def convert_audio(self, data, sampling_rate):
        # Resample to desired size, rescale
        height, width = self.size_available()

        resized_t = np.linspace(0, len(data) / sampling_rate, width)
        resized_data = np.interp(
            resized_t,
            np.linspace(0, len(data) / sampling_rate, len(data)),
            data
        )

        return resized_t, np.abs(resized_data)

    def to_ascii_array(self, signal):
        """Converts a spectrogram array into ascii characters color indices

        Params
        ======
        spec : np.ndarray
            2D spectrogram array (freq_bins, time_bins)

        Returns a 2D array where each element is a Char namedtuple of
        (character, foreground_intensity, background_intensity). This function
        is dependent on an available colormap being set and initiated.

        The colormap must implement a method to convert fractional values
        for the foreground and background intensities to a color index
        """
        height, width = self.size_available()
        floor = np.min(signal)
        ceil = np.max(signal)

        rows = height // 2  # Each char represents 2 amplitude ticks
        cols = width // 2   # Each char represents 2 time points

        output_characters = np.empty((rows, cols), dtype=object)
        one_row_frac = 1 / (rows - 1)

        for output_col in range(cols):
            for output_row in range(rows):
                patch = signal[slice(output_col * 2, (output_col + 1) * 2)]
                frac0 = (patch[0] - floor) / (ceil - floor)
                frac1 = (patch[1] - floor) / (ceil - floor)

                output_row_frac = output_row / (rows - 1)
                if frac0 - output_row_frac < 0.25 * one_row_frac:
                    bits0 = "00"
                elif 0.25 * one_row_frac <= frac0 - output_row_frac < 0.75 * one_row_frac:
                    bits0 = "10"
                else:
                    bits0 = "11"

                if frac1 - output_row_frac < 0.25 * one_row_frac:
                    bits1 = "00"
                elif 0.25 * one_row_frac <= frac1 - output_row_frac < 0.75 * one_row_frac:
                    bits1 = "10"
                else:
                    bits1 = "11"

                char = getattr(const, "QTR_{}{}".format(bits0, bits1))
                output_characters[output_row, output_col] = (
                    char,
                    self.cmap.colors[-1],
                    self.cmap.colors[0]
                )

        return output_characters

    def ansi(self, fg_color=0, bg_color=0, reset=False):
        if reset:
            return "\u001b[0m"
        return "\u001b[38;5;{fg_color}m\u001b[48;5;{bg_color}m".format(fg_color=fg_color, bg_color=bg_color)

    def render(self):
        t, signal = self.convert_audio(self.data, self.sampling_rate)
        chars = self.to_ascii_array(signal)

        print()
        for row in chars[::-1]:
            row_output = ""
            for char, fg_color, bg_color in row:
                row_output += self.ansi(fg_color, bg_color) + char
            row_output += self.ansi(reset=True)
            print(row_output)

        self._last_render_data = {
            "t": t,
            "signal": signal,
        }


class AsciiAmplitudeTwoSidedPlugin(BaseAsciiAmplitudePlugin):

    def to_ascii_array(self, signal):
        """Converts a spectrogram array into ascii characters color indices

        Params
        ======
        spec : np.ndarray
            2D spectrogram array (freq_bins, time_bins)

        Returns a 2D array where each element is a Char namedtuple of
        (character, foreground_intensity, background_intensity). This function
        is dependent on an available colormap being set and initiated.

        The colormap must implement a method to convert fractional values
        for the foreground and background intensities to a color index
        """
        height, width = self.size_available()
        floor = np.min(signal)
        ceil = np.max(signal)

        rows = height // 2  # Each char represents 2 amplitude ticks
        cols = width // 2   # Each char represents 2 time points

        output_characters = np.empty((rows, cols), dtype=object)

        row0 = rows / 2   # The center "row" value

        row0_idx = int(np.ceil(row0))
        row0_char = "_" if rows % 2 else "╌"

        one_row_frac = 1 / (rows - 1)

        for output_col in range(cols):
            for output_row in range(rows):

                patch = signal[slice(output_col * 2, (output_col + 1) * 2)]
                frac0 = (patch[0] - floor) / (ceil - floor)
                frac1 = (patch[1] - floor) / (ceil - floor)

                output_row_frac = 2 * (output_row - row0) / (rows - 1)

                if np.abs(frac0) - np.abs(output_row_frac) < 0.25 * one_row_frac:
                    bits0 = "00"
                elif 0.25 * one_row_frac <= np.abs(frac0) - np.abs(output_row_frac) < 0.75 * one_row_frac:
                    if output_row_frac > 0:
                        bits0 = "10"
                    else:
                        bits0 = "01"
                else:
                    bits0 = "11"

                if np.abs(frac1) - np.abs(output_row_frac) < 0.25 * one_row_frac:
                    bits1 = "00"
                elif 0.25 * one_row_frac <= np.abs(frac1) - np.abs(output_row_frac) < 0.75 * one_row_frac:
                    if output_row_frac > 0:
                        bits1 = "10"
                    else:
                        bits1 = "01"
                else:
                    bits1 = "11"

                if output_row == row0_idx and bits0 == "00" and bits1 == "00":
                    char = row0_char
                else:
                    char = getattr(const, "QTR_{}{}".format(bits0, bits1))
                output_characters[output_row, output_col] = (
                    char,
                    self.cmap.colors[-1],
                    self.cmap.colors[0]
                )

        return output_characters


__all__ = [
    "BaseAsciiAmplitudePlugin",
    "AsciiAmplitudeTwoSidedPlugin",
]
