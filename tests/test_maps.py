import unittest

import numpy as np

from inspec import const
from inspec.maps import (
    Char,
    CharMap,
    FullCharMap,
    HalfCharMap,
    QuarterCharMap,
)


class TestBaseCharMap(unittest.TestCase):

    def setUp(self):
        class MockCharMap(CharMap):
            patch_dimensions = (2, 3)
        self.MockCharMap = MockCharMap

    def test_max_img_shape(self):

        self.assertEqual(
            self.MockCharMap.max_img_shape(char_rows=10, char_cols=10),
            (20, 30)
        )

        self.assertEqual(
            self.MockCharMap.max_img_shape(char_rows=1, char_cols=7),
            (2, 21)
        )

    def test_iter_patches(self):
        test_arr = np.arange(600).reshape((20, 30))
        patches = list(self.MockCharMap.iter_patches(test_arr))
        self.assertEqual(
            len(patches),
            100,
        )

        self.assertEqual(patches[0][0], (0, 0))
        np.testing.assert_array_equal(patches[0][-1], np.array([
            [0, 1, 2],
            [30, 31, 32],
        ]))

        self.assertEqual(patches[1][0], (0, 1))
        np.testing.assert_array_equal(patches[1][-1], np.array([
            [3, 4, 5],
            [33, 34, 35],
        ]))

        self.assertEqual(patches[10][0], (1, 0))
        np.testing.assert_array_equal(patches[10][-1], np.array([
            [60, 61, 62],
            [90, 91, 92],
        ]))

        self.assertEqual(patches[-1][0], (9, 9))
        np.testing.assert_array_equal(patches[-1][-1], np.array([
            [567, 568, 569],
            [597, 598, 599],
        ]))

    def test_invalid_iter_patches(self):
        test_arr = np.zeros((19, 30))
        with self.assertRaises(ValueError):
            list(self.MockCharMap.iter_patches(test_arr))

        test_arr = np.zeros((20, 29))
        with self.assertRaises(ValueError):
            list(self.MockCharMap.iter_patches(test_arr))


class TestFullCharMap(unittest.TestCase):

    def test_max_img_shape(self):
        self.assertEqual(
            FullCharMap.max_img_shape(char_rows=10, char_cols=10),
            (10, 10)
        )
        self.assertEqual(
            FullCharMap.max_img_shape(char_rows=1, char_cols=7),
            (1, 7)
        )

    def test_iter_patches(self):
        test_arr = np.arange(100).reshape((10, 10))
        patches = list(FullCharMap.iter_patches(test_arr))
        self.assertEqual(
            len(patches),
            100,
        )

        self.assertEqual(patches[-1][0], (9, 9))
        np.testing.assert_array_equal(patches[-1][-1], np.array([
            [99],
        ]))

    def test_patch_to_char(self):
        result = FullCharMap.patch_to_char(np.array([[0.2]]))
        self.assertEqual(result, Char(
            char=const.FULL_1,
            fg=0.2,
            bg=0.2
        ))


class TestHalfCharMap(unittest.TestCase):

    def test_max_img_shape(self):
        self.assertEqual(
            HalfCharMap.max_img_shape(char_rows=10, char_cols=10),
            (20, 10)
        )
        self.assertEqual(
            HalfCharMap.max_img_shape(char_rows=1, char_cols=7),
            (2, 7)
        )

    def test_iter_patches(self):
        test_arr = np.arange(100).reshape((10, 10))
        patches = list(HalfCharMap.iter_patches(test_arr))
        self.assertEqual(
            len(patches),
            50,
        )

        self.assertEqual(patches[-1][0], (4, 9))
        np.testing.assert_array_equal(patches[-1][-1], np.array([
            [89],
            [99],
        ]))

    def test_patch_to_char(self):
        result = HalfCharMap.patch_to_char(np.array([[0.7], [0.2]]))
        self.assertEqual(result, Char(
            char=const.HALF_10,
            fg=0.7,
            bg=0.2
        ))

        result = HalfCharMap.patch_to_char(np.array([[0.2], [0.7]]))
        self.assertEqual(result, Char(
            char=const.HALF_10,
            fg=0.2,
            bg=0.7
        ))

        result = HalfCharMap.patch_to_char(np.array([[0.5], [0.5]]))
        self.assertEqual(result, Char(
            char=const.FULL_1,
            fg=0.5,
            bg=0.5
        ))

        result = HalfCharMap.patch_to_char(np.array([[0.0], [0.0]]))
        self.assertEqual(result, Char(
            char=const.FULL_0,
            fg=0.0,
            bg=0.0
        ))

class TestQuarterCharMap(unittest.TestCase):

    def test_max_img_shape(self):
        self.assertEqual(
            QuarterCharMap.max_img_shape(char_rows=10, char_cols=10),
            (20, 20)
        )
        self.assertEqual(
            QuarterCharMap.max_img_shape(char_rows=1, char_cols=7),
            (2, 14)
        )

    def test_iter_patches(self):
        test_arr = np.arange(100).reshape((10, 10))
        patches = list(QuarterCharMap.iter_patches(test_arr))
        self.assertEqual(
            len(patches),
            25,
        )

        self.assertEqual(patches[-1][0], (4, 4))
        np.testing.assert_array_equal(patches[-1][-1], np.array([
            [88, 89],
            [98, 99],
        ]))

    def test_patch_to_char(self):
        result = QuarterCharMap.patch_to_char(np.array([
            [0.2, 0.2],
            [0.2, 0.2]
        ]))
        self.assertEqual(result, Char(
            char=const.FULL_1,
            fg=0.2,
            bg=0.2
        ))

        result = QuarterCharMap.patch_to_char(np.array([
            [0.0, 0.0],
            [0.0, 0.0]
        ]))
        self.assertEqual(result, Char(
            char=const.FULL_0,
            fg=0.0,
            bg=0.0
        ))

        result = QuarterCharMap.patch_to_char(np.array([
            [0.7, 0.2],
            [0.2, 0.5]
        ]))
        self.assertEqual(result, Char(
            char=const.QTR_1001,
            fg=0.6,
            bg=0.2
        ))

        result = QuarterCharMap.patch_to_char(np.array([
            [0.7, 0.7],
            [0.2, 0.3]
        ]))
        self.assertEqual(result, Char(
            char=const.QTR_1010,
            fg=0.7,
            bg=0.25
        ))

        result = QuarterCharMap.patch_to_char(np.array([
            [0.1, 0.65],
            [0.65, 0.65]
        ]))
        self.assertEqual(result, Char(
            char=const.QTR_0111,
            fg=0.65,
            bg=0.1
        ))
