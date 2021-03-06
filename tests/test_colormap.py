import unittest
from unittest import mock

import numpy as np

from inspec.colormap import (
    _registered_colormaps,
    Colormap,
    ColormapNotFound,
    CursesColormapSingleton,
    PairedColormap,
    VALID_CMAPS,
    curses_cmap,
    load_cmap,
)


class TestPairedColormap(unittest.TestCase):

    def test_init_colors(self):
        cmap = PairedColormap(range(10))
        for i, color in enumerate(cmap.colors):
            self.assertTrue(isinstance(color, Colormap.Color256))
            self.assertEqual(color.idx, i)

    def test_default_bin_edges(self):
        colors = [0, 1, 2, 3]
        expected_edges = np.array([0.25, 0.5, 0.75])

        np.testing.assert_array_equal(
            PairedColormap.default_bin_edges(colors),
            expected_edges,
        )

        colors = list(range(10))
        expected_edges = np.array(np.arange(1, 10) / 10)
        np.testing.assert_array_equal(
            PairedColormap.default_bin_edges(colors),
            expected_edges,
        )

    def test_invalid_colors(self):
        too_few = [0]
        with self.assertRaises(ValueError):
            PairedColormap(too_few)

        too_few = [1]
        with self.assertRaises(ValueError):
            PairedColormap(too_few)

        too_many = list(range(23))
        with self.assertRaises(ValueError):
            PairedColormap(too_many)

    def test_scale(self):
        # Should have 10 levels
        colors = list(range(10))
        cmap = PairedColormap(range(10))
        expected_edges = np.array(np.arange(1, 10) / 10)
        assert len(colors) == 10
        np.testing.assert_array_equal(
            cmap.bin_edges,
            expected_edges,
        )
        self.assertEqual(cmap.scale(0), colors[0])
        self.assertEqual(cmap.scale(1.0), colors[-1])

        for i in range(len(expected_edges)):
            # Test boundaries of edges and that being right on an edge is consistent
            self.assertEqual(cmap.scale(expected_edges[i] - 0.01), colors[i])
            self.assertEqual(cmap.scale(expected_edges[i]), colors[i])
            self.assertEqual(cmap.scale(expected_edges[i] + 0.01), colors[i + 1])


class TestCursesColormapSingleton(unittest.TestCase):

    def setUp(self):
        self.dummy_cmap = PairedColormap(colors=[1, 2, 4, 3])
        self.expected_bins_to_slot_mappings = (
            ((1, 0), 1),
            ((2, 0), 2),
            ((3, 0), 3),
            ((2, 1), 4),
            ((3, 1), 5),
            ((3, 2), 6),
        )
        self.expected_colors_to_slot_mappings = (
            ((2, 1), 1),
            ((4, 1), 2),
            ((3, 1), 3),
            ((4, 2), 4),
            ((3, 2), 5),
            ((3, 4), 6),
        )
        self.preinstalled_cmap_name = VALID_CMAPS[0]

    def test_singleton(self):
        """Test the mapping between fg and bg bins (0-1) each to a color slot (0-255)
        """
        curses_cmap_new = CursesColormapSingleton()
        self.assertIs(curses_cmap, curses_cmap_new, "Singleton should not create a new instance")

    @mock.patch("curses.init_pair")
    def test_bins_to_color_slot(self, p):
        """Test the mapping between fg and bg bins (0-1) each to a color slot (0-255)
        """
        curses_cmap.init_colormap(self.dummy_cmap)
        assert self.dummy_cmap is curses_cmap.cmap

        with self.assertRaises(ValueError):
            curses_cmap._color_bins_to_slot(1, 1)

        with self.assertRaises(ValueError):
            curses_cmap._color_bins_to_slot(0, 1)

        with self.assertRaises(ValueError):
            curses_cmap._color_bins_to_slot(1, -1)

        with self.assertRaises(ValueError):
            curses_cmap._color_bins_to_slot(len(self.dummy_cmap.colors), 0)

        self.assertEqual(curses_cmap._color_bins_to_slot(1, 0), 1)
        self.assertEqual(curses_cmap._color_bins_to_slot(2, 0), 2)
        self.assertEqual(curses_cmap._color_bins_to_slot(3, 0), 3)
        self.assertEqual(curses_cmap._color_bins_to_slot(2, 1), 4)
        self.assertEqual(curses_cmap._color_bins_to_slot(3, 1), 5)
        self.assertEqual(curses_cmap._color_bins_to_slot(3, 2), 6)

    @mock.patch("curses.init_pair")
    def test_get_slot(self, p):
        """Test the mapping between fg and bg bins (0-1) each to a color slot (0-255)
        """
        curses_cmap.init_colormap(self.dummy_cmap)
        assert self.dummy_cmap is curses_cmap.cmap

        for (i0, i1), slot in self.expected_bins_to_slot_mappings:
            self.assertEqual(
                curses_cmap.get_slot(
                    curses_cmap.cmap.colors[i0],
                    curses_cmap.cmap.colors[i1],
                ),
                (slot, False)
            )
            self.assertEqual(
                curses_cmap.get_slot(
                    curses_cmap.cmap.colors[i1],
                    curses_cmap.cmap.colors[i0],
                ),
                (slot, True),
                "get_slot() is not returning the invert bool correctly"
            )

        self.assertEqual(
            curses_cmap.get_slot(
                curses_cmap.cmap.colors[0],
                curses_cmap.cmap.colors[0],
            ),
            (1, False)
        )

        self.assertEqual(
            curses_cmap.get_slot(
                curses_cmap.cmap.colors[1],
                curses_cmap.cmap.colors[1],
            ),
            (1, False)
        )

        self.assertEqual(
            curses_cmap.get_slot(
                curses_cmap.cmap.colors[2],
                curses_cmap.cmap.colors[2],
            ),
            (4, False)
        )

    def test_init_colormap(self):
        expected_init_pair_calls = [
            mock.call(slot, color0, color1)
            for (color0, color1), slot
            in self.expected_colors_to_slot_mappings
        ]
        with mock.patch("curses.init_pair") as p:
            curses_cmap.init_colormap(self.dummy_cmap)
            p.assert_has_calls(expected_init_pair_calls, any_order=True)
            self.assertEqual(p.call_count, len(expected_init_pair_calls))

        self.assertIs(curses_cmap.cmap, self.dummy_cmap)

    @mock.patch("curses.init_pair")
    def test_init_colormap_by_name_not_existing(self, p):
        with self.assertRaises(ColormapNotFound):
            curses_cmap.init_colormap("thiscmapdoesnotexist")

    @mock.patch("curses.init_pair")
    def test_init_colormap_by_name(self, p):
        existing_cmap = _registered_colormaps[self.preinstalled_cmap_name]
        curses_cmap.init_colormap(self.preinstalled_cmap_name)
        self.assertIs(curses_cmap.cmap, existing_cmap)



class TestLoadCmap(unittest.TestCase):
    def setUp(self):
        self.dummy_cmap = PairedColormap(colors=[1, 2, 4, 3])

    def test_load_cmap_by_cmap(self):
        self.assertIs(self.dummy_cmap, load_cmap(self.dummy_cmap))

        for preinstalled_cmap_name in VALID_CMAPS:
            existing_cmap = _registered_colormaps[preinstalled_cmap_name]
            self.assertIs(load_cmap(existing_cmap), existing_cmap)

    def test_load_cmap_by_name(self):
        for preinstalled_cmap_name in VALID_CMAPS:
            existing_cmap = _registered_colormaps[preinstalled_cmap_name]
            self.assertIs(load_cmap(preinstalled_cmap_name), existing_cmap)

        with self.assertRaises(ColormapNotFound):
            load_cmap("thiscmapdoesnotexist")

    def test_load_cmap_bad_input(self):
        with self.assertRaises(ColormapNotFound):
            load_cmap(1000.0)
