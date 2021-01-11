from inspec import var
# from inspec.maps import QuarterCharMap
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
    PILImageGreyscaleTransform,
    PILImageRGBTransform,
)
from inspec.render import (StdoutRenderer, StdoutRGBRenderer)
from inspec.maps import (
    FullCharMap,
    HalfCharMap,
    QuarterCharMap,
    FullCharMapRGB,
    HalfCharMapRGB,
    QuarterCharMapRGB,
)


DEFAULTS = {
    "audio": {
        "spec_transform": SpectrogramTransform(
            spec_sampling_rate=var.DEFAULT_SPECTROGRAM_SAMPLE_RATE,
            spec_freq_spacing=var.DEFAULT_SPECTROGRAM_FREQ_SPACING,
            min_freq=var.DEFAULT_SPECTROGRAM_MIN_FREQ,
            max_freq=var.DEFAULT_SPECTROGRAM_MAX_FREQ
        ),
        "amp_transform": AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7))
    },
    "image": {
        "transform": {
            "greyscale": PILImageGreyscaleTransform(
                keep_aspect_ratio=True,
                character_aspect_ratio=var.TERM_CHAR_ASPECT_RATIO
            ),
            "rgb": PILImageRGBTransform(
                keep_aspect_ratio=True,
                thumbnail=False,
                character_aspect_ratio=var.TERM_CHAR_ASPECT_RATIO,
            )
        },
        "render": {
            "greyscale": StdoutRenderer,
            "rgb": StdoutRGBRenderer,
        },
        "map": {
            "greyscale": {
                "full": FullCharMap,
                "half": HalfCharMap,
                "quarter": QuarterCharMap,
            },
            "rgb": {
                "full": FullCharMapRGB,
                "half": HalfCharMapRGB,
                "quarter": QuarterCharMapRGB,
            }
        },
    },
    "cmap": "greys"
}
