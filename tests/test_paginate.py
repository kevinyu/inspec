import unittest

from inspec.paginate import Paginator


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
                self.assertEqual(p.items_per_page, i * j)

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
