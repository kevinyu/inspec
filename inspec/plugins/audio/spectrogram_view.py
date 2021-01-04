import curses
import os
from collections import namedtuple
from collections import defaultdict
import time

import cv2
import numpy as np

from inspec import const, var
from inspec.plugins.colormap import curses_cmap, load_cmap
from inspec.plugins.audio.spectrogram import spectrogram

from .base import BaseAudioPlugin, SoundFileMixin


CharBin = namedtuple("CharBin", [
    "char",
    "fg",
    "bg",
])


class BaseAsciiSpectrogramPlugin(BaseAudioPlugin, SoundFileMixin):

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
            int(var.PRINT_SPEC_TERMINAL_Y_FRAC * size.lines * 2),
            int(var.PRINT_SPEC_TERMINAL_X_FRAC * size.columns)
        )

    def convert_audio(self, data, sampling_rate):
        spec_height, spec_width = self.size_available()
        t, f, spec = spectrogram(
            data,
            sampling_rate,
            var.SPECTROGRAM_SAMPLE_RATE,
            var.SPECTROGRAM_FREQ_SPACING,
            min_freq=var.SPECTROGRAM_MIN_FREQ,
            max_freq=var.SPECTROGRAM_MAX_FREQ
        )
        resized_spec = cv2.resize(
            spec,
            dsize=(spec_width, spec_height),
            interpolation=cv2.INTER_CUBIC
        )
        resized_t = np.linspace(t[0], t[-1], spec_width)
        resized_f = np.linspace(f[0], f[-1], spec_height)

        return resized_t, resized_f, resized_spec

    def ascii_background(self):
        return ColorBin(char=const.FULL_1, fg=self.cmap.colors[0], bg=self.cmap.colors[-1])

    def to_ascii_char(self, frac0, frac1):
        """Returns a character and foreground and background terminal colors (0-255)
        """
        bin0, bin1 = self.cmap.scale(frac0), self.cmap.scale(frac1)
        if bin0 == bin1 == 0:
            return CharBin(
                char=const.FULL_1,
                fg=self.cmap.colors[0],
                bg=self.cmap.colors[-1]
            )
        elif bin0 == bin1:
            return CharBin(
                char=const.FULL_0,
                fg=self.cmap.colors[0],
                bg=self.cmap.colors[bin1]
            )
        elif bin0 < bin1:
            return CharBin(
                char=const.HALF_01,
                fg=self.cmap.colors[bin0],
                bg=self.cmap.colors[bin1],
            )
        elif bin1 < bin0:
            return CharBin(
                char=const.HALF_10,
                fg=self.cmap.colors[bin1],
                bg=self.cmap.colors[bin0]
            )

    def to_ascii_array(self, spec):
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
        floor = np.quantile(spec, var.SPECTROGRAM_LOWER_QUANTILE)
        ceil = np.quantile(spec, var.SPECTROGRAM_UPPER_QUANTILE)

        rows = spec.shape[0] // 2  # Each char represents 2 freq bins
        cols = spec.shape[1]

        output_characters = np.empty((rows, cols), dtype=object)
        for output_row in range(rows):
            for output_col in range(cols):
                patch = spec[slice(output_row * 2, (output_row+1) * 2), output_col]

                if ceil == floor:
                    char, fg_color, bg_color = self.ascii_background()
                else:
                    patch0_frac, patch1_frac = (patch - floor) / (ceil - floor)
                    char, fg_color, bg_color = self.to_ascii_char(patch0_frac, patch1_frac)

                output_characters[output_row, output_col] = (char, fg_color, bg_color)

        return output_characters

    def ansi(self, fg_color=0, bg_color=0, reset=False):
        if reset:
            return "\u001b[0m"
        return "\u001b[38;5;{fg_color}m\u001b[48;5;{bg_color}m".format(fg_color=fg_color, bg_color=bg_color)

    def render(self):
        t, f, spec = self.convert_audio(self.data, self.sampling_rate)
        chars = self.to_ascii_array(spec)

        print()
        for row in chars[::-1]:
            row_output = ""
            for char, fg_color, bg_color in row:
                row_output += self.ansi(fg_color, bg_color) + char
            row_output += self.ansi(reset=True)
            print(row_output)

        self._last_render_data = {
            "t": t,
            "f": f,
            "spec": spec,
        }


class AsciiSpectrogram2x2Plugin(BaseAsciiSpectrogramPlugin):
    """Renders a spectrogram with twice the time resolution using 2x2 patches

    Increases resolution in time axis by using unicode quarter patches, at the
    cost of a slightly slower rendering (the mean is subtracted off each
    patch to determine the best character to use and the fg, bg values.
    """

    def size_available(self):
        """Return half the screen vertically
        """
        size = os.get_terminal_size()
        return (
            int(var.PRINT_SPEC_TERMINAL_Y_FRAC * size.lines * 2),
            int(var.PRINT_SPEC_TERMINAL_X_FRAC * size.columns * 2)
        )

    def convert_audio(self, data, sampling_rate):
        spec_height, spec_width = self.size_available()
        t, f, spec = spectrogram(
            data,
            sampling_rate,
            var.SPECTROGRAM_SAMPLE_RATE,
            var.SPECTROGRAM_FREQ_SPACING,
            min_freq=var.SPECTROGRAM_MIN_FREQ,
            max_freq=var.SPECTROGRAM_MAX_FREQ,
        )
        resized_spec = cv2.resize(
            spec,
            dsize=(spec_width, spec_height),
            interpolation=cv2.INTER_CUBIC
        )
        resized_t = np.linspace(t[0], t[-1], spec_width)
        resized_f = np.linspace(f[0], f[-1], spec_height)

        return resized_t, resized_f, resized_spec

    def to_ascii_char(self, patch):
        """Returns a character and foreground and background terminal colors (0-255)
        """
        mask = (patch > np.mean(patch)).astype(bool)
        char = getattr(const, "QTR_{2}{0}{3}{1}".format(*mask.astype(int).flatten()))
        # raise Exception(~mask)
        # frac0 = np.mean(patch[~mask])
        # frac1 = np.mean(patch[mask])
        frac0 = np.mean(np.ma.masked_array(patch, mask=mask))
        frac1 = np.mean(np.ma.masked_array(patch, mask=~mask))

        bin0, bin1 = self.cmap.scale(frac0), self.cmap.scale(frac1)
        if bin0 == bin1 == 0:
            return CharBin(
                char=const.FULL_1,
                fg=self.cmap.colors[0],
                bg=self.cmap.colors[-1]
            )
        elif bin0 == bin1:
            return CharBin(
                char=const.FULL_0,
                fg=self.cmap.colors[0],
                bg=self.cmap.colors[bin1]
            )
        elif bin0 < bin1:
            return CharBin(
                char=char,
                fg=self.cmap.colors[bin0],
                bg=self.cmap.colors[bin1],
            )
        else:
            raise ValueError("bin0 should not be able to be larger than bin1 (from {}, {}  {}, {})".format(
                patch,
                mask,
                np.ma.masked_array(patch, mask=mask),
                np.ma.masked_array(patch, mask=~mask)))

    def to_ascii_array(self, spec):
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
        floor = np.quantile(spec, var.SPECTROGRAM_LOWER_QUANTILE)
        ceil = np.quantile(spec, var.SPECTROGRAM_UPPER_QUANTILE)

        rows = spec.shape[0] // 2  # Each char represents 2 freq bins
        cols = spec.shape[1] // 2

        output_characters = np.empty((rows, cols), dtype=object)
        for output_row in range(rows):
            for output_col in range(cols):
                patch = spec[
                    slice(output_row * 2, (output_row+1) * 2),
                    slice(output_col * 2, (output_col+1) * 2)
                ]

                if ceil == floor:
                    char, fg_color, bg_color = self.ascii_background()
                else:
                    patch_frac = (patch - floor) / (ceil - floor)
                    char, fg_color, bg_color = self.to_ascii_char(patch_frac)

                output_characters[output_row, output_col] = (char, fg_color, bg_color)

        return output_characters


class CursesSpectrogramPlugin(AsciiSpectrogram2x2Plugin, SoundFileMixin):

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.cmap = curses_cmap

    def set_cmap(self, cmap):
        self.cmap.init_colormap(cmap)

    def size_available(self):
        lines, cols = self.window.getmaxyx()
        lines -= 1  # Or else I get out of bounds errors in render()....
        return (2 * lines, 2 * cols)

    def render(self):
        t, f, spec = self.convert_audio(self.data, self.sampling_rate)
        chars = self.to_ascii_array(spec)

        for row in range(chars.shape[0]):
            for col in range(chars.shape[1]):
                char, fg_color, bg_color = chars[row, col]
                color = curses.color_pair(self.cmap.colors_to_color_slot(fg_color, bg_color))
                self.window.addstr(
                    chars.shape[0] - row - 1,
                    col,
                    char,
                    color
                )

        self.window.refresh()

        self._last_render_data = {
            "t": t,
            "f": f,
            "spec": spec,
        }


__all__ = [
    "BaseAsciiSpectrogramPlugin",
    "AsciiSpectrogram2x2Plugin",
    "CursesSpectrogramPlugin",
]
