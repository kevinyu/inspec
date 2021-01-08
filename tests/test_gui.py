import unittest

from inspec.gui.utils import (
    PositionSlider,
    generate_position_slider,
    slider_to_character_positions,
)


class TestPositionSlider(unittest.TestCase):
    def test_slider_calculation(self):
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
                slider_to_character_positions(
                    PositionSlider(0.2, 0.6, 1.0), nchars
                ),
                (start, stop)
            )

    def test_slider_print(self):
        expected_results = [
            (3, " ▖ "),
            (4, " ▗  "),
            (5, " ▗▄  "),
            (6, "  ▄▖  "),
            (7, "  ▄▄   "),
            (8, "  ▄▄▖   "),
            (9, "  ▗▄▄    "),
            (10, "  ▗▄▄▄    "),
            (11, "   ▄▄▄▖    "),
            (12, "   ▄▄▄▄     "),
            (13, "   ▄▄▄▄▖     "),
            (14, "   ▗▄▄▄▄      "),
            (15, "   ▗▄▄▄▄▄      "),
            (16, "    ▄▄▄▄▄▖      "),
            (17, "    ▄▄▄▄▄▄       "),
            (18, "    ▄▄▄▄▄▄▖       "),
            (19, "    ▗▄▄▄▄▄▄        "),
            (20, "    ▗▄▄▄▄▄▄▄        "),
            (21, "     ▄▄▄▄▄▄▄▖        "),
        ]
        for nchars, expect in expected_results:
            self.assertEqual(
                expect,
                generate_position_slider(
                    PositionSlider(0.4, 1.2, 2.0), nchars
                )
            )
