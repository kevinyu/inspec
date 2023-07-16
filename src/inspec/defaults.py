from typing import TypedDict

from inspec import var
from inspec.transform import (
    AmplitudeEnvelopeTwoSidedTransform,
    PilImageGreyscaleTransform,
    SpectrogramTransform,
)


class _AudioDefaults(TypedDict):
    spec_transform: SpectrogramTransform
    amp_transform: AmplitudeEnvelopeTwoSidedTransform


class _ImageDefaults(TypedDict):
    transform: PilImageGreyscaleTransform


class _Defaults(TypedDict):
    audio: _AudioDefaults
    image: _ImageDefaults
    cmap: str


DEFAULTS: _Defaults = {
    "audio": {
        "spec_transform": SpectrogramTransform(
            spec_sampling_rate=var.DEFAULT_SPECTROGRAM_SAMPLE_RATE,
            spec_freq_spacing=var.DEFAULT_SPECTROGRAM_FREQ_SPACING,
            min_freq=var.DEFAULT_SPECTROGRAM_MIN_FREQ,
            max_freq=var.DEFAULT_SPECTROGRAM_MAX_FREQ,
        ),
        "amp_transform": AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7)),
    },
    "image": {
        "transform": PilImageGreyscaleTransform(
            keep_aspect_ratio=True, character_aspect_ratio=var.TERM_CHAR_ASPECT_RATIO
        )
    },
    "cmap": "greys",
}

__all__ = ["DEFAULTS"]
