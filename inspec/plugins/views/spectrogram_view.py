import os
from collections import namedtuple

import cv2
import numpy as np
import soundfile
from soundsig.sound import spectrogram

from inspec import const, var
from inspec.colormap import curses_cmap, get_colormap


CharBin = namedtuple("CharBin", [
    "char",
    "fg",
    "bg",
])


class BaseSpectrogramPlugin(object):

    def __init__(self):
        self.data = None
        self.sampling_rate = None
        self._last_render_metadata = {}

    def set_data(self, data, sampling_rate):
        self.data = data
        self.sampling_rate = sampling_rate

    @property
    def last_render_data(self):
        return self._last_render_data

    def render(self):
        raise NotImplementedError


class SoundFileMixin(object):

    def read_file(self, filename):
        data, sampling_rate = soundfile.read(filename)
        self.set_data(data, sampling_rate)

    def read_file_partial(self, filename, read_samples, start_idx):
        data, sampling_rate = soundfile.read(filename, read_samples, start_idx)
        self.set_data(data, sampling_rate)

    def read_file_metadata(self, filename):
        with soundfile.SoundFile(filename) as f:
            return {
                "sampling_rate": f.samplerate,
                "frames": f.frames,
                "n_channels": f.channels,
                "duration": f.frames / f.samplerate
            }


class BaseAsciiSpectrogramPlugin(BaseSpectrogramPlugin, SoundFileMixin):

    def __init__(self):
        super().__init__()
        self.cmap = get_colormap(var.DEFAULT_CMAP)

    def set_cmap(self, cmap):
        self.cmap = get_colormap(cmap)

    def receive(self, data):
        raise NotImplementedError

    def size_available(self):
        """Return half the screen vertically
        """
        size = os.get_terminal_size()
        return (
            int(var.PRINT_TERMINAL_Y_FRAC * size.lines * 2),
            int(var.PRINT_TERMINAL_X_FRAC * size.columns)
        )

    def convert_audio(self, data, sampling_rate):
        spec_height, spec_width = self.size_available()
        t, f, spec, _ = spectrogram(
            data,
            sampling_rate,
            var.SPECTROGRAM_SAMPLE_RATE,
            var.SPECTROGRAM_FREQ_SPACING,
            min_freq=var.SPECTROGRAM_MIN_FREQ,
            max_freq=var.SPECTROGRAM_MAX_FREQ,
            cmplx=False
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
        return ColorBin(char=const.FULL_1, fg=0, bg=self.cmap.colors[-1])

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


class CursesSpectrogramPlugin(BaseAsciiSpectrogramPlugin, SoundFileMixin):

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.cmap = curses_cmap

    def set_cmap(self, cmap):
        self.cmap.init_colormap(cmap)

    def size_available(self):
        lines, cols = self.window.getmaxyx()
        return (2 * lines, cols)

    def render(self):
        t, f, spec = self.convert_audio(self.data, self.sampling_rate)
        chars = self.to_ascii(spec)

        for row in range(chars.shape[0]):
            for col in range(chars.shape[1]):
                char, fg_color, bg_color = chars[row, col]
                color = curses.color_pair(self.cmap.colors_to_color_slot(fg_color, bg_color))
                self.window.addstr(
                    chars.shape[0] - row,
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