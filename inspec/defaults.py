from inspec import var
from inspec.maps import QuarterCharMap
from inspec.transform import SpectrogramTransform, AmplitudeEnvelopeTwoSidedTransform


DEFAULTS = {
    "audio": {
        "map": QuarterCharMap,
        "spec_transform": SpectrogramTransform(
            spec_sampling_rate=var.DEFAULT_SPECTROGRAM_SAMPLE_RATE,
            spec_freq_spacing=var.DEFAULT_SPECTROGRAM_FREQ_SPACING,
            min_freq=var.DEFAULT_SPECTROGRAM_MIN_FREQ,
            max_freq=var.DEFAULT_SPECTROGRAM_MAX_FREQ
        ),
        "amp_transform": AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7))
    },
    "cmap": "greys"
}
