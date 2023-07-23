from inspec_core.render.colors import IntensityMap
from inspec_core.render.types import XTermColor

# Define some built-in cmaps
_registered_colormaps: dict[str, IntensityMap] = {
    "greys": IntensityMap.create(
        [XTermColor(i) for i in [16, *range(232, 250), 251, 253, 255]]
    ),
    "plasma": IntensityMap.create(
        [
            XTermColor(i)
            for i in [
                16,
                232,
                17,
                18,
                19,
                20,
                21,
                57,
                56,
                55,
                91,
                127,
                163,
                169,
                168,
                167,
                166,
                172,
                208,
                214,
                220,
                221,
            ]
        ]
    ),
    "viridis": IntensityMap.create(
        [
            XTermColor(i)
            for i in [
                16,
                232,
                17,
                18,
                19,
                20,
                26,
                25,
                24,
                23,
                22,
                28,
                34,
                40,
                46,
                82,
                118,
                154,
                148,
                184,
                220,
                221,
            ]
        ]
    ),
    "blues": IntensityMap.create(
        [
            XTermColor(i)
            for i in [
                16,
                232,
                17,
                18,
                19,
                20,
                21,
                27,
                26,
                25,
                24,
                30,
                37,
                44,
                51,
                87,
                123,
                159,
                195,
                231,
                255,
            ]
        ]
    ),
    "bluered": IntensityMap.create(
        [
            XTermColor(i)
            for i in [
                21,
                27,
                33,
                39,
                45,
                51,
                87,
                123,
                159,
                195,
                231,
                255,
                231,
                224,
                217,
                210,
                203,
                196,
                160,
                124,
                88,
                52,
            ]
        ]
    ),
    "jet": IntensityMap.create(
        [
            XTermColor(i)
            for i in [
                17,
                18,
                19,
                20,
                25,
                31,
                37,
                43,
                49,
                84,
                83,
                155,
                154,
                148,
                142,
                136,
                166,
                160,
                124,
                88,
                52,
            ]
        ]
    ),
}


# Registry the reversed colormaps too
for key in list(_registered_colormaps.keys()):
    _registered_colormaps["{}_r".format(key)] = _registered_colormaps[key].inverted()


def get_colormap(name: str) -> IntensityMap:
    """
    Get a colormap by name
    """
    return _registered_colormaps[name]


def valid_colormaps() -> list[str]:
    """
    Return a list of valid colormap names
    """
    return list(_registered_colormaps.keys())
