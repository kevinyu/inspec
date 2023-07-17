from render.display import display


def test_display():
    from render.types import Intensity, CharShape, RGB
    from render.patches import make_intensity_renderer
    from inspec_curses import get_colormap
    import numpy as np

    arr = np.vectorize(Intensity)(np.random.rand(40, 40))

    cmap = get_colormap("viridis")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)

    display(renderer.apply(arr))

    from render.patches import make_rgb_renderer

    renderer = make_rgb_renderer()

    def to_rgb(vec):
        return RGB(*vec)

    arr = np.vectorize(to_rgb, signature="(n) -> ()")(np.random.choice(256, size=(40, 40, 3)))
    display(renderer.apply(arr))

    from inspec.io import PILImageReader

    reader = PILImageReader()

    data = reader.read_file("/Users/kevin/Downloads/IMG_4002.PNG")
    original_height, original_width = data.data.height, data.data.width

    output_size = (400, 300)
    resized = data.data.resize((output_size[1], output_size[0]))
    resized = resized.convert(mode="RGB")
    resized = np.asarray(resized)[::-1]
    arr = np.vectorize(to_rgb, signature="(n) -> ()")(resized)

    renderer = make_rgb_renderer(shape=CharShape.Half)
    display(renderer.apply(arr))


if __name__ == "__main__":
    test_display()