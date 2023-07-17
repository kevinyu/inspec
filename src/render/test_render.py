import numpy as np
from inspec.io import PILImageReader
from inspec_curses import get_colormap
from render.display import display
from render.patches import make_intensity_renderer, make_rgb_renderer
from render.types import RGB, CharShape, Intensity


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


def test_display_image():
    reader = PILImageReader()
    data = reader.read_file("demo/mandrill.jpg")
    output_size = (100, 50)
    resized = data.data.resize((output_size[1], output_size[0]))
    resized = resized.convert(mode="RGB")
    resized = np.asarray(resized)[::-1]
    arr = np.vectorize(to_rgb, signature="(n) -> ()")(resized)
    renderer = make_rgb_renderer(shape=CharShape.Half)
    display(renderer.apply(arr))


if __name__ == "__main__":
    test_display()
    test_display_rgb()
    test_display_image()
