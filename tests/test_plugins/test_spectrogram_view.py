import curses
import os
import unittest
from unittest import mock

import numpy as np

from inspec import const, var
from inspec.plugins.audio.spectrogram_view import (
    BaseAsciiSpectrogramPlugin,
    AsciiSpectrogram2x2Plugin,
    CursesSpectrogramPlugin,
    CharBin
)
from inspec.plugins.colormap import (
    _registered_colormaps,
    PairedColormap,
    curses_cmap
)


class TestBasicAsciiSpectrogramPlugin(unittest.TestCase):

    def setUp(self):
        self.COLORS = {
            "black": 232,
            "darkgrey": 240,
            "lightgrey": 248,
            "white": 255
        }
        self.plugin = BaseAsciiSpectrogramPlugin()
        self.simple_cmap = PairedColormap(colors=[
            self.COLORS["black"],
            self.COLORS["darkgrey"],
            self.COLORS["lightgrey"],
            self.COLORS["white"]
        ])

    def test_default_cmap_loaded(self):
        self.assertIn(self.plugin.cmap, _registered_colormaps.values())

    @mock.patch("os.get_terminal_size", return_value=os.terminal_size((80, 20)))
    def test_size_available(self, p):
        lines, cols = self.plugin.size_available()
        p.assert_called_once()
        self.assertEqual(lines, 40)
        self.assertEqual(cols, 80)

    @mock.patch(
        "inspec.plugins.audio.spectrogram_view.BaseAsciiSpectrogramPlugin.size_render",
        return_value=(40, 80)
    )
    def test_convert_audio(self, mock_render):
        np.random.seed(420)
        sample_data = np.random.random((24000,))
        t, f, spec = self.plugin.convert_audio(sample_data, 48000)

        self.assertEqual(spec.shape, (40, 80))
        self.assertEqual(len(t), 80)
        self.assertEqual(len(f), 40)

    def test_ascii_background_char(self):
        self.plugin.set_cmap(self.simple_cmap)
        charbin = self.plugin.ascii_background()

        self.assertEqual(charbin.char, const.FULL_0)
        self.assertEqual(charbin.bg, self.COLORS["black"])
        # this is not important to test as it is not relevant to the render:
        # self.assertEqual(charbin.bg, self.COLORS["white"])

    def test_ascii_char_conversion(self):
        self.plugin.set_cmap(self.simple_cmap)
        np.testing.assert_array_equal(self.plugin.cmap.bin_edges, np.array([0.25, 0.5, 0.75]))

        test_darkest = self.plugin.to_ascii_char(0.1, 0.2)
        self.assertEqual(
            test_darkest,
            self.plugin.ascii_background(),
            "Low values should render as background"
        )

        test_equal = self.plugin.to_ascii_char(0.6, 0.7)
        self.assertEqual(test_equal.char, const.FULL_1, "Should render as fully light grey")
        self.assertEqual(test_equal.fg, self.COLORS["lightgrey"], "Should render as fully light grey")

        test_first_greater = self.plugin.to_ascii_char(0.9, 0.4)
        self.assertEqual(
            test_first_greater,
            CharBin(
                char=const.HALF_10,
                fg=self.COLORS["white"],
                bg=self.COLORS["darkgrey"]
            ),
            "Should render as white on bottom and darkgrey on top")

        test_second_greater = self.plugin.to_ascii_char(0.4, 0.9)
        self.assertEqual(
            test_second_greater,
            CharBin(
                char=const.HALF_01,
                fg=self.COLORS["white"],
                bg=self.COLORS["darkgrey"]
            ),
            "Should render as darkgrey on bottom and white on top")

    @mock.patch("inspec.var.SPECTROGRAM_LOWER_QUANTILE", 0.0)
    @mock.patch("inspec.var.SPECTROGRAM_UPPER_QUANTILE", 1.0)
    def test_ascii_array_conversion(self):
        self.plugin.set_cmap(self.simple_cmap)
        np.testing.assert_array_equal(self.plugin.cmap.bin_edges, np.array([0.25, 0.5, 0.75]))

        spec = np.array([
            [0.0, 0.9, 0.4],
            [0.3, 0.6, 1.0],
            [0.2, 0.1, 0.33],
            [0.5, 0.6, 0.33],
        ])

        expected_charbins = np.empty((2, 3), dtype=object)
        expected_charbins[:] = [
            [
                self.plugin.to_ascii_char(0.0, 0.3),
                self.plugin.to_ascii_char(0.9, 0.6),
                self.plugin.to_ascii_char(0.4, 1.0),
            ],
            [
                self.plugin.to_ascii_char(0.2, 0.5),
                self.plugin.to_ascii_char(0.1, 0.6),
                self.plugin.to_ascii_char(0.33, 0.33),
            ],
        ]

        ascii_spec = self.plugin.to_ascii_array(spec)

        self.assertEqual(expected_charbins.shape, ascii_spec.shape)
        for i in range(ascii_spec.shape[0]):
            for j in range(ascii_spec.shape[1]):
                self.assertEqual(ascii_spec[i, j], expected_charbins[i, j])

        # Test a crazier shape
        np.random.seed(420)
        spec = np.random.random((42, 89))
        self.assertEqual(
            self.plugin.to_ascii_array(spec).shape,
            (spec.shape[0] // 2, spec.shape[1])
        )

class TestAsciiSpectrogram2x2Plugin(unittest.TestCase):

    def setUp(self):
        self.COLORS = {
            "black": 232,
            "darkgrey": 240,
            "lightgrey": 248,
            "white": 255
        }
        self.plugin = AsciiSpectrogram2x2Plugin()
        self.simple_cmap = PairedColormap(colors=[
            self.COLORS["black"],
            self.COLORS["darkgrey"],
            self.COLORS["lightgrey"],
            self.COLORS["white"]
        ])

    @mock.patch("os.get_terminal_size", return_value=os.terminal_size((80, 20)))
    def test_size_available(self, p):
        lines, cols = self.plugin.size_available()
        p.assert_called_once()
        self.assertEqual(lines, 40)
        self.assertEqual(cols, 160)

    @mock.patch(
        "inspec.plugins.audio.spectrogram_view.BaseAsciiSpectrogramPlugin.size_render",
        return_value=(40, 160)
    )
    def test_convert_audio(self, mock_render):
        np.random.seed(420)
        sample_data = np.random.random((24000,))
        t, f, spec = self.plugin.convert_audio(sample_data, 48000)

        self.assertEqual(spec.shape, (40, 160))
        self.assertEqual(len(t), 160)
        self.assertEqual(len(f), 40)

    def test_ascii_char_conversion(self):
        self.plugin.set_cmap(self.simple_cmap)
        np.testing.assert_array_equal(self.plugin.cmap.bin_edges, np.array([0.25, 0.5, 0.75]))

        # Test a simple patch
        patch = np.array([
            [0.2, 0.9],
            [0.8, 0.1]
        ])
        self.assertEqual(self.plugin.to_ascii_char(patch).char, const.QTR_0110)

        for a in [0, 1]:
            for b in [0, 1]:
                for c in [0, 1]:
                    for d in [0, 1]:
                        patch = np.array([
                            [a, c],
                            [b, d]
                        ])
                        if a == b == c == d:
                            expected_char = const.FULL_0
                        else:
                            expected_char = getattr(const, "QTR_{}{}{}{}".format(a, b, c, d))
                        charbin = self.plugin.to_ascii_char(patch)
                        self.assertEqual(charbin.char, expected_char)

    @mock.patch("inspec.var.SPECTROGRAM_LOWER_QUANTILE", 0.0)
    @mock.patch("inspec.var.SPECTROGRAM_UPPER_QUANTILE", 1.0)
    def test_ascii_array_conversion(self):
        self.plugin.set_cmap(self.simple_cmap)
        np.testing.assert_array_equal(self.plugin.cmap.bin_edges, np.array([0.25, 0.5, 0.75]))

        spec = np.array([
            [0.2, 0.9, 0.4, 1.0],
            [0.2, 0.2, 1.0, 0.4],
            [0.0, 0.0, 0.33, 0.6],
            [0.8, 0.8, 0.33, 0.6],
        ])

        expected_charbins = np.empty((2, 2), dtype=object)
        expected_charbins[:] = [
            [
                self.plugin.to_ascii_char(np.array([[0.2, 0.9], [0.2, 0.2]])),
                self.plugin.to_ascii_char(np.array([[0.4, 1.0], [1.0, 0.4]])),
            ],
            [
                self.plugin.to_ascii_char(np.array([[0.0, 0.0], [0.8, 0.8]])),
                self.plugin.to_ascii_char(np.array([[0.33, 0.6], [0.33, 0.6]])),
            ],
        ]
        expected_chars = [
            [const.QTR_0010, const.QTR_0110],
            [const.QTR_0101, const.QTR_0011]
        ]

        ascii_spec = self.plugin.to_ascii_array(spec)

        self.assertEqual(expected_charbins.shape, ascii_spec.shape)
        for i in range(ascii_spec.shape[0]):
            for j in range(ascii_spec.shape[1]):
                self.assertEqual(ascii_spec[i, j], expected_charbins[i, j])
                self.assertEqual(ascii_spec[i, j][0], expected_chars[i][j], "Wrong on {} {}".format(i, j))

        # Test a crazier shape
        np.random.seed(420)
        spec = np.random.random((42, 90))
        self.assertEqual(
            self.plugin.to_ascii_array(spec).shape,
            (spec.shape[0] // 2, spec.shape[1] // 2)
        )



class TestCursesSpectrogramPlugin(unittest.TestCase):

    def setUp(self):
        self.window = mock.Mock(spec=curses.window)
        self.simple_cmap = PairedColormap(colors=[1, 2, 3, 4])
        self.expected_colors_to_slot_mappings = (
            ((2, 1), 1),
            ((3, 1), 2),
            ((4, 1), 3),
            ((3, 2), 4),
            ((4, 2), 5),
            ((4, 3), 6),
        )
        self.plugin = CursesSpectrogramPlugin(self.window)

    def test_init(self):
        self.assertIs(self.plugin.cmap, curses_cmap)
        self.assertIs(self.plugin.window, self.window)

    @mock.patch("curses.init_pair")
    def test_set_cmap(self, p):
        self.plugin.set_cmap(self.simple_cmap)
        expected_init_pair_calls = [
            mock.call(slot, color0, color1)
            for (color0, color1), slot
            in self.expected_colors_to_slot_mappings
        ]
        p.assert_has_calls(expected_init_pair_calls, any_order=True)
        self.assertEqual(p.call_count, len(expected_init_pair_calls))

    def test_size_available(self):
        self.window.getmaxyx.return_value = 10, 40
        self.assertEqual(self.plugin.size_available(), (20, 80))

    def test_size_render(self):
        self.window.getmaxyx.return_value = 10, 40
        self.assertEqual(self.plugin.size_render(), (19, 80))

    @mock.patch("curses.init_pair")
    @mock.patch("curses.color_pair")
    @mock.patch(
        "inspec.plugins.audio.spectrogram_view.CursesSpectrogramPlugin.convert_audio",
    )
    @mock.patch(
        "inspec.plugins.audio.spectrogram_view.CursesSpectrogramPlugin.to_ascii_array",
    )
    def test_render(self, mock_to_ascii_array, mock_convert_audio, mock_color_pair, mock_init_pair):
        self.plugin.set_cmap(self.simple_cmap)

        charbins_to_render = np.empty((2, 2), dtype=object)
        charbins_to_render[:] = [
            [
                CharBin(const.QTR_1100, 2, 1),
                CharBin(const.QTR_1110, 3, 2),
            ],
            [
                CharBin(const.FULL_1, 4, 1),
                CharBin(const.QTR_0101, 4, 3),
            ],
        ]

        mock_convert_audio.return_value = (0, 0, 0)
        mock_to_ascii_array.return_value = charbins_to_render

        expected_color_pair_calls = [mock.call(1), mock.call(4), mock.call(3), mock.call(6)]
        mock_color_pair.side_effect = [100, 400, 300, 600]

        self.plugin.render()

        mock_color_pair.assert_has_calls(expected_color_pair_calls)
        self.assertEqual(mock_color_pair.call_count, len(expected_color_pair_calls))

        expected_addstr_calls = [
            mock.call(1, 0, const.QTR_1100, 100),
            mock.call(1, 1, const.QTR_1110, 400),
            mock.call(0, 0, const.FULL_1, 300),
            mock.call(0, 1, const.QTR_0101, 600),
        ]
        self.window.addstr.assert_has_calls(expected_addstr_calls)
        self.assertEqual(self.window.addstr.call_count, len(expected_addstr_calls))
