import numpy as np

from inspec_core.colormaps import get_colormap

from . import make_intensity_renderer, make_rgb_renderer
from .display import display
from .types import RGB, CharShape, Intensity


def to_rgb(vec):
    return RGB(*vec)


def test_display():
    arr = np.vectorize(Intensity)(np.random.rand(40, 40))
    cmap = get_colormap("viridis")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    display(renderer.apply(arr))


def test_display_rgb():
    arr = np.vectorize(to_rgb, signature="(n) -> ()")(
        np.random.choice(256, size=(40, 40, 3))
    )
    renderer = make_rgb_renderer()
    display(renderer.apply(arr))


if __name__ == "__main__":
    test_display()
    test_display_rgb()
