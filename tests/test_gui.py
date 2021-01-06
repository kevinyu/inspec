import unittest

from inspec.gui.paginate import Paginator
from inspec.gui.state import HighlightBar
from inspec.gui.utils import (
    generate_progress_bar_string,
    progress_bar_fractions_to_character_positions
)


class TestPaginator(unittest.TestCase):
    def test_n_pages(self):
        """Test that the paginator computes the total number of pages correctly
        """
        # Total items ->  number of pages
        expected_results_2x2 = [
            (0, 0),
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 2),
            (6, 2),
            (7, 2),
            (8, 2),
            (9, 3),
        ]

        for total, expected_pages in expected_results_2x2:
            paginator = Paginator(2, 2, total)
            self.assertEqual(paginator.n_pages, expected_pages)

        # Total items ->  number of pages
        expected_results_1x1 = [
            (0, 0),
            (1, 1),
            (2, 2),
            (3, 3),
        ]

        for total, expected_pages in expected_results_1x1:
            paginator = Paginator(1, 1, total)
            self.assertEqual(paginator.n_pages, expected_pages)

    def test_n_visible(self):
        for i in range(1, 10):
            for j in range(1, 10):
                p = Paginator(i, j, 100)
                self.assertEqual(p.n_visible, i * j)

    def test_items_on_page(self):
        # Test multiple
        p = Paginator(3, 3, 18)
        self.assertEqual(p.items_on_page(0), [0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(p.items_on_page(1), [9, 10, 11, 12, 13, 14, 15, 16, 17])
        with self.assertRaises(ValueError):
            p.items_on_page(2)

        # Test uneven
        p = Paginator(3, 3, 19)
        self.assertEqual(p.items_on_page(0), [0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(p.items_on_page(1), [9, 10, 11, 12, 13, 14, 15, 16, 17])
        self.assertEqual(p.items_on_page(2), [18])
        with self.assertRaises(ValueError):
            p.items_on_page(3)

        # Test uneven
        p = Paginator(3, 3, 4)
        self.assertEqual(p.items_on_page(0), [0, 1, 2, 3])
        with self.assertRaises(ValueError):
            p.items_on_page(1)

    def test_item_to_page(self):
        p = Paginator(3, 3, 19)
        self.assertEqual(p.item_to_page(4), 0)
        self.assertEqual(p.item_to_page(8), 0)
        self.assertEqual(p.item_to_page(9), 1)
        self.assertEqual(p.item_to_page(17), 1)
        self.assertEqual(p.item_to_page(18), 2)


class TestProgressBar(unittest.TestCase):
    def test_progress_bar_calculation(self):
        expected_results = [
            ((0.0, 0.5), 1),
            ((0.5, 1.0), 2),
            ((0.5, 2.0), 3),
            ((1.0, 2.5), 4),
            ((1.0, 3.0), 5),
            ((1.0, 3.5), 6),
            ((1.5, 4.0), 7),
            ((1.5, 5.0), 8),
            ((2.0, 5.5), 9),
            ((2.0, 6.0), 10),
            ((2.0, 6.5), 11),
            ((2.5, 7.0), 12),
            ((2.5, 8.0), 13),
            ((3.0, 8.5), 14),
            ((3.0, 9.0), 15),
            ((3.0, 9.5), 16),
            ((3.5, 10.0), 17),
            ((3.5, 11.0), 18),
            ((4.0, 11.5), 19),
        ]
        for (start, stop), nchars in expected_results:
            self.assertEqual(
                progress_bar_fractions_to_character_positions(
                    HighlightBar(0.2, 0.6, 1.0), nchars
                ),
                (start, stop)
            )

    def test_progress_bar_print(self):
        expected_results = [
            (3, "[▖]"),
            (4, "[▗ ]"),
            (5, "[▗▄ ]"),
            (6, "[ ▄▖ ]"),
            (7, "[ ▄▄  ]"),
            (8, "[ ▄▄▖  ]"),
            (9, "[ ▗▄▄   ]"),
            (10, "[ ▗▄▄▄   ]"),
            (11, "[  ▄▄▄▖   ]"),
            (12, "[  ▄▄▄▄    ]"),
            (13, "[  ▄▄▄▄▖    ]"),
            (14, "[  ▗▄▄▄▄     ]"),
            (15, "[  ▗▄▄▄▄▄     ]"),
            (16, "[   ▄▄▄▄▄▖     ]"),
            (17, "[   ▄▄▄▄▄▄      ]"),
            (18, "[   ▄▄▄▄▄▄▖      ]"),
            (19, "[   ▗▄▄▄▄▄▄       ]"),
            (20, "[   ▗▄▄▄▄▄▄▄       ]"),
            (21, "[    ▄▄▄▄▄▄▄▖       ]"),
        ]
        for nchars, expect in expected_results:
            self.assertEqual(
                expect,
                generate_progress_bar_string(
                    HighlightBar(0.4, 1.2, 2.0), nchars
                )
            )
