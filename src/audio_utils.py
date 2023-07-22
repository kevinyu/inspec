from __future__ import annotations
import asyncio
import dataclasses
from typing import Any, AsyncIterator, Optional, TypeVar

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray


@dataclasses.dataclass
class AudioChunk:
    """
    A chunk of audio data
    """

    data: NDArray
    frames: int
    channels: int
    sample_rate: int


def list_devices():
    """
    List the available audio devices
    """
    return sd.query_devices()


async def stream_audio(
    device_idx: Optional[int] = None
) -> AsyncIterator[AudioChunk]:
    """
    Stream audio from audio device (defualt None)
    """
    q: asyncio.Queue[AudioChunk] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def cb(
        indata: NDArray[np.int16],
        frames: int,
        __time: Any,
        __status: sd.CallbackFlags
    ):
        loop.call_soon_threadsafe(
            q.put_nowait,
            AudioChunk(
                data=indata.copy(),
                frames=frames,
                channels=indata.shape[1],
                sample_rate=int(stream.samplerate),
            ),
        )

    device_info = sd.query_devices(sd.default.device[0])
    assert isinstance(device_info, dict)
    stream = sd.InputStream(
        device=None,
        samplerate=device_info["default_samplerate"],
        dtype=np.int16,
        callback=cb,
    )
    try:
        stream.start()
        while True:
            yield await q.get()
    finally:
        stream.stop()


async def test_listen():
    async for chunk in stream_audio(0):
        pass


T = TypeVar("T", NDArray, float)


def db_scale(x: T, dB: float) -> T:
    """
    Scale the channels of a signal (in dB) independently
    """
    return np.power(10.0, dB / 20.0) * x


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


def resize(
    spec: SpectrogramArray, target_height: int, target_width: int
) -> SpectrogramArray:
    """Resize a 2D array with bilinear interpolation

    A modified version of https://chao-ji.github.io/jekyll/update/2018/07/19/BilinearResize.html

    `image` is a 2-D numpy array
    `height` and `width` are the desired spatial dimension of the new 2-D array.
    """
    assert spec.ndim == 2

    original_height, original_width = spec.shape
    resized = np.empty([target_height, target_width])

    if target_height == 1:
        return resize_1d(spec[0], target_width)[None, :]

    if target_width == 1:
        return resize_1d(spec[:, 0], target_height)[:, None]

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


def compute_ampenv(signal: NDArray) -> NDArray:
    assert signal.ndim == 1
    return np.abs(signal)
