from .base_view import Size
from .size import Shape, preserve_aspect_ratio


def test_preserve_aspect_ratio():
    original_width = 10
    original_height = 20

    assert preserve_aspect_ratio(
        Size.FixedSize(width=100, height=120),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=100, height=120)

    assert preserve_aspect_ratio(
        Size.FixedWidth(width=100),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=100, height=200)

    assert preserve_aspect_ratio(
        Size.FixedHeight(height=100),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=50, height=100)

    assert preserve_aspect_ratio(
        Size.MaxSize(width=2, height=3),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=1, height=3)

    assert preserve_aspect_ratio(
        Size.MinSize(width=2, height=3),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=2, height=4)

    assert preserve_aspect_ratio(
        Size.FixedHeight(height=100),
        original_width=original_width,
        original_height=original_height,
    ) == Shape(width=50, height=100)
