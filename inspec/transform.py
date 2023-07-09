import abc
from ast import Load
from dataclasses import dataclass
from typing import Generic, Literal, Optional

import numpy as np
from numpy.typing import NDArray

from inspec import var
from inspec.io import LoadedAudioData, LoadedImage, ReturnT


def _get_frequencies(signal_length: int, sample_rate: int):
    freq = np.fft.fftfreq(signal_length, d=1.0 / sample_rate)
    nz = freq >= 0.0
    return freq[nz]


def _calculate_fft(
    signal: NDArray[np.float64],
    sample_rate: int,
    nstd: float,
) -> tuple[NDArray[np.float64], NDArray[np.complex128]]:
    assert signal.ndim == 1

    win_size = len(signal)
    if win_size % 2 == 0:
        win_size += 1
    half_win_size = win_size // 2

    # Construct the window
    gauss_t = np.arange(-half_win_size, half_win_size + 1, 1.0)
    gauss_std = float(win_size) / float(nstd)
    gauss_window = np.exp(-(gauss_t**2) / (2.0 * gauss_std**2)) / (
        gauss_std * np.sqrt(2 * np.pi)
    )

    # Window the signal and take the FFT
    fft_len = len(signal)
    windowed_slice = signal[:fft_len] * gauss_window[:fft_len]
    s_fft = np.fft.fft(windowed_slice, n=fft_len)
    freq = np.fft.fftfreq(fft_len, d=1.0 / sample_rate)
    nz = freq >= 0.0

    return freq[nz], s_fft[nz]


def _get_window_length(freq_spacing: float, nstd: float) -> float:
    return nstd / (2.0 * np.pi * freq_spacing)


TimeArray = NDArray[np.float64]
FrequencyArray = NDArray[np.float64]
SpectrogramArray = NDArray[np.float64]  # Expect a 2D array


def compute_spectrogram(
    signal: NDArray[np.float64],
    sampling_rate: int,
    spec_sample_rate: int,
    freq_spacing: float,
    nstd: int = 6,
    min_freq: float = 0,
    max_freq: Optional[float] = None,
) -> tuple[TimeArray, FrequencyArray, SpectrogramArray]:
    """Spectrogram computation

    Copied/adapted from https://github.com/theunissenlab/soundsig to remove
    dependency and avoid slow import
    """
    assert signal.ndim == 1

    increment = 1.0 / spec_sample_rate
    window_length = _get_window_length(freq_spacing, nstd)

    if max_freq is None:
        max_freq = sampling_rate / 2.0

    # Compute lengths in # of samples
    win_size = int(sampling_rate * window_length)
    if win_size % 2 == 0:
        win_size += 1
    half_win_size = win_size // 2

    if len(signal) < win_size:
        win_size = len(signal)
        if win_size % 2 == 0:
            win_size -= 1
        half_win_size = win_size // 2

    # assert len(signal) > win_size, "len(s)=%d, win_size=%d" % (len(signal), win_size)

    # Get the values for the frequency axis by estimating the spectrum of a dummy slice
    full_freq = _get_frequencies(win_size, sampling_rate)
    freq_index = (full_freq >= min_freq) & (full_freq <= max_freq)
    freq_arr = full_freq[freq_index]
    nfreq = freq_index.sum()

    nincrement = int(np.round(sampling_rate * increment))
    nwindows = len(signal) // nincrement
    # Pad the signal with zeros
    zeros = np.zeros([len(signal) + 2 * half_win_size])
    zeros[half_win_size:-half_win_size] = signal
    window_centers = np.arange(nwindows) * nincrement + half_win_size

    # Take the FFT of each segment, padding with zeros when necessary to keep window length the same
    spec = np.zeros([nfreq, nwindows], dtype="complex")
    for k in range(nwindows):
        center = window_centers[k]
        start_idx = center - half_win_size
        end_idx = center + half_win_size + 1

        spec_freq, est = _calculate_fft(
            zeros[start_idx:end_idx],
            sampling_rate,
            nstd,
        )
        findex = (spec_freq <= max_freq) & (spec_freq >= min_freq)
        spec[:, k] = est[findex]

    # Note that the desired spectrogram rate could be slightly modified
    t_arr = np.arange(0, nwindows, 1.0) * float(nincrement) / sampling_rate
    spec = np.abs(spec)

    return t_arr, freq_arr, spec


def resize(spec: SpectrogramArray, target_height: int, target_width: int) -> SpectrogramArray:
    """Resize a 2D array with bilinear interpolation

    A modified version of https://chao-ji.github.io/jekyll/update/2018/07/19/BilinearResize.html

    `image` is a 2-D numpy array
    `height` and `width` are the desired spatial dimension of the new 2-D array.
    """
    assert spec.ndim == 2

    original_height, original_width = spec.shape
    resized = np.empty([target_height, target_width])

    dy = (original_height - 1) / (target_height - 1)
    dx = (original_width - 1) / (target_width - 1)

    for i in range(target_height):
        for j in range(target_width):
            # Where would this point have been in the old coordinates?
            reference_i = i * dy
            reference_j = j * dx

            ref_i_lower = int(np.floor(reference_i))
            ref_i_upper = int(np.ceil(reference_i))
            ref_j_lower = int(np.floor(reference_j))
            ref_j_upper = int(np.ceil(reference_j))

            # Floating point error can lead to the reference_indices
            # being ever-so-slightly greater than original_height|width
            # When that happens, lets just round it down. It will
            # receive a negligible weight anyway
            if ref_j_upper == original_width:
                ref_j_upper -= 1
            elif ref_i_upper == original_height:
                ref_i_upper -= 1

            corner_00 = spec[ref_i_lower, ref_j_lower]
            corner_01 = spec[ref_i_lower, ref_j_upper]
            corner_10 = spec[ref_i_upper, ref_j_lower]
            corner_11 = spec[ref_i_upper, ref_j_upper]

            # Linear interpolation by distances to corners
            weight_i_lower = 1 - np.abs(reference_i - ref_i_lower)
            weight_i_upper = 1 - weight_i_lower
            weight_j_lower = 1 - np.abs(reference_j - ref_j_lower)
            weight_j_upper = 1 - weight_j_lower

            corner_00_weight = weight_i_lower * weight_j_lower
            corner_01_weight = weight_i_lower * weight_j_upper
            corner_10_weight = weight_i_upper * weight_j_lower
            corner_11_weight = weight_i_upper * weight_j_upper

            resized[i][j] = (
                corner_00 * corner_00_weight
                + corner_01 * corner_01_weight
                + corner_10 * corner_10_weight
                + corner_11 * corner_11_weight
            )

    return resized


def resize_1d(signal: NDArray, output_len: int) -> NDArray:
    assert signal.ndim == 1
    t = np.linspace(0, len(signal), output_len)
    resized = np.interp(t, np.linspace(0, len(signal), len(signal)), signal)
    return resized


def compute_ampenv(signal: NDArray, sampling_rate: int) -> NDArray:
    assert signal.ndim == 1
    return np.abs(signal)


@dataclass
class InspecTransform(Generic[ReturnT], abc.ABC):
    def convert(
        self,
        data: ReturnT,
        output_size: tuple[int, int],
        *args,
        **kwargs,
    ) -> tuple[NDArray[np.float64], dict]:
        """Take some loaded data and return a 2D image array and some metadata"""
        raise NotImplementedError


@dataclass
class AudioTransform(InspecTransform[LoadedAudioData], abc.ABC):
    def convert(
        self,
        data: LoadedAudioData,
        output_size: tuple[int, int],
        *args,
        **kwargs,
    ) -> tuple[NDArray[np.float64], dict]:
        """Convert 1D audio signal into a 2D image array

        Returns tuple of 2D image array and dictionary of metadata about the conversion
        """
        raise NotImplementedError


@dataclass
class SpectrogramTransform(AudioTransform):
    spec_sampling_rate: int
    spec_freq_spacing: float
    min_freq: int = 0
    max_freq: Optional[int] = None

    def convert(
        self, data: LoadedAudioData, output_size: tuple[int, int]
    ) -> tuple[NDArray[np.float64], dict]:
        """Convert 1D audio signal into a spectrogram

        Returns spectrogram and metadata dictionary
        """
        t, f, spec = compute_spectrogram(
            data.data,
            data.sampling_rate,
            spec_sample_rate=self.spec_sampling_rate,
            freq_spacing=self.spec_freq_spacing,
            min_freq=self.min_freq,
            max_freq=self.max_freq,
        )

        if output_size is None:
            output_size = spec.shape
        elif output_size[1] == 1:
            spec = resize(spec, output_size[0], 2)
            spec = np.mean(spec, axis=1)[:, None]
            t = np.linspace(t[0], t[-1], output_size[1])
            f = np.linspace(f[0], f[-1], output_size[0])
        else:
            spec = resize(spec, output_size[0], output_size[1])
            t = np.linspace(t[0], t[-1], output_size[1])
            f = np.linspace(f[0], f[-1], output_size[0])

        metadata = {
            "t": t,
            "f": f,
            "SpectrogramTransform": {
                "spec_sampling_rate": self.spec_sampling_rate,
                "freq_spacing": self.spec_freq_spacing,
                "min_freq": self.min_freq,
                "max_freq": self.max_freq,
            },
        }

        return spec, metadata


@dataclass
class AmplitudeEnvelopeTwoSidedTransform(AudioTransform):
    ymax: Optional[float] = None
    gradient: tuple[float, float] = (1.0, 1.0)

    def __post_init__(self):
        if self.gradient and (
            not isinstance(self.gradient, tuple)
            or not len(self.gradient) == 2
            or not (0 <= self.gradient[0] <= self.gradient[1] <= 1)
        ):
            raise ValueError("Gradient must be a tuple of 2 floats between 0 and 1")

    def convert(
        self, data: LoadedAudioData, output_size: tuple[int, int], scale: float = 1.0
    ) -> tuple[NDArray[np.float64], dict]:
        """Convert 1D audio signal into a spectrogram

        Returns spectrogram and metadata dictionary
        """
        ampenv = compute_ampenv(data.data, data.sampling_rate)

        t = np.linspace(0, len(data.data) / data.sampling_rate, output_size[1])
        ampenv = resize_1d(ampenv, output_size[1])

        if self.ymax is not None:
            ymax = self.ymax
        else:
            ymax = np.max(ampenv)
        if ymax == 0:
            ymax = 1.0

        img = np.zeros(output_size)
        half_height = output_size[0] // 2

        if self.gradient:
            _gradient_span = self.gradient[1] - self.gradient[0]
            _gradient_0 = self.gradient[0]
        else:
            _gradient_span = 0
            _gradient_0 = 1

        def compute_color(i):
            return _gradient_0 + ((i + 1) / half_height) * _gradient_span

        for col in range(len(ampenv)):
            n_rows_to_fill = int(np.round(scale * half_height * ampenv[col] / ymax))
            for i in range(min(n_rows_to_fill, img.shape[0] - half_height)):
                val = compute_color(i)
                img[half_height + i, col] = val
                img[half_height - i - 1, col] = val

        metadata = {
            "t": t,
            "AmplitudeEnvelopeTwoSidedTransform": {
                "ymax": ymax,
                "gradient": self.gradient,
            },
        }

        return img, metadata


@dataclass
class PilImageTransform(InspecTransform[LoadedImage]):
    keep_aspect_ratio: bool = True
    character_aspect_ratio: float = var.TERM_CHAR_ASPECT_RATIO
    thumbnail: bool = False
    pil_convert_mode: Literal["L", "RGB"] = "L"

    def convert(
        self,
        data: LoadedImage,
        output_size: tuple[int, int],
        size_multiple_of: Optional[tuple[int, int]] = None,
        rotated: bool = False,
    ):
        """Convert an PIL array into greyscale"""
        original_height, original_width = data.data.height, data.data.width

        # This is code to try to figure out what the output side shoule be that
        # 1) closely approximates the original aspect ratio
        # 2) is an even multiple of the size_multiple_of
        # 3) is no larger than the requested output_size
        # The thumbnail function does 3 automatically but does not necessarily satisfy
        # the first two conditions. Also, it comes out a lower resolution than may
        # be desired.
        if self.keep_aspect_ratio:
            aspect_ratio = original_height / original_width
            if rotated:
                pseudo_aspect_ratio = aspect_ratio * self.character_aspect_ratio
            else:
                pseudo_aspect_ratio = aspect_ratio / self.character_aspect_ratio

            if size_multiple_of is not None:
                pseudo_aspect_ratio = (
                    size_multiple_of[0] * pseudo_aspect_ratio
                ) / size_multiple_of[1]

            proposed_new_width = int(np.floor(output_size[0] / pseudo_aspect_ratio))
            proposed_new_height = int(np.floor(pseudo_aspect_ratio * output_size[1]))

            if size_multiple_of is not None:
                proposed_new_width -= proposed_new_width % size_multiple_of[1]
                proposed_new_height -= proposed_new_height % size_multiple_of[0]

            if proposed_new_width > output_size[1]:
                output_size = (proposed_new_height, output_size[1])
            else:
                output_size = (output_size[0], proposed_new_width)
        else:
            output_size = output_size

        if self.thumbnail:
            data.data.thumbnail(
                (output_size[1], output_size[0])
            )  # Thumbnail edits in place
            result = data.data.convert(mode=self.pil_convert_mode)
            result = np.asarray(result)[::-1]
            resized = resize(result, output_size[0], output_size[1])
        else:
            resized = data.data.resize((output_size[1], output_size[0]))
            resized = resized.convert(mode=self.pil_convert_mode)
            resized = np.asarray(resized)[::-1]

        return (
            resized,
            {
                "keep_aspect_ratio": self.keep_aspect_ratio,
                "character_aspect_ratio": self.character_aspect_ratio,
                "image_mode": self.pil_convert_mode,
            },
        )


@dataclass
class PilImageGreyscaleTransform(PilImageTransform):
    pil_convert_mode: Literal["L"] = "L"


@dataclass
class PilImageRGBTransform(PilImageTransform):
    pil_convert_mode: Literal["RGB"] = "RGB"
