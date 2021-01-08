import numpy as np


def _get_frequencies(signal_length, sample_rate):
    freq = np.fft.fftfreq(signal_length, d=1.0 / sample_rate)
    nz = freq >= 0.0
    return freq[nz]


def _estimate(signal, sample_rate, start_time, end_time, nstd):
    win_size = len(signal)
    if win_size % 2 == 0:
        win_size += 1
    half_win_size = win_size // 2

    # Construct the window
    gauss_t = np.arange(-half_win_size, half_win_size + 1, 1.0)
    gauss_std = float(win_size) / float(nstd)
    gauss_window = np.exp(-gauss_t**2 / (2.0 * gauss_std**2)) / (gauss_std * np.sqrt(2 * np.pi))

    # Window the signal and take the FFT
    fft_len = len(signal)
    windowed_slice = signal[:fft_len] * gauss_window[:fft_len]
    s_fft = np.fft.fft(windowed_slice, n=fft_len)
    freq = np.fft.fftfreq(fft_len, d=1.0/sample_rate)
    nz = freq >= 0.0

    return freq[nz], s_fft[nz]


def _get_window_length(freq_spacing, nstd):
    return nstd / (2.0 * np.pi * freq_spacing)


def compute_spectrogram(signal, sampling_rate, spec_sample_rate, freq_spacing, nstd=6, min_freq=0, max_freq=None):
    """Spectrogram computation

    Copied/adapted from https://github.com/theunissenlab/soundsig to remove
    dependency and avoid slow import
    """
    increment = 1.0 / spec_sample_rate
    window_length = _get_window_length(freq_spacing, nstd)

    if max_freq is None:
        max_freq = sampling_rate / 2.0

    # Compute lengths in # of samples
    win_size = int(sampling_rate * window_length)
    if win_size % 2 == 0:
        win_size += 1
    half_win_size = win_size // 2
    assert len(signal) > win_size, "len(s)=%d, win_size=%d" % (len(signal), win_size)

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
    spec = np.zeros([nfreq, nwindows], dtype='complex')
    for k in range(nwindows):
        center = window_centers[k]
        start_idx = center - half_win_size
        end_idx = center + half_win_size + 1

        spec_freq, est = _estimate(
            zeros[start_idx:end_idx],
            sampling_rate,
            start_idx / sampling_rate,
            end_idx / sampling_rate,
            nstd
        )
        findex = (spec_freq <= max_freq) & (spec_freq >= min_freq)
        spec[:, k] = est[findex]

    # Note that the desired spectrogram rate could be slightly modified
    t_arr = np.arange(0, nwindows, 1.0) * float(nincrement) / sampling_rate
    spec = np.abs(spec)

    return t_arr, freq_arr, spec


def resize(spec, target_height, target_width):
    """Resize a 2D array with bilinear interpolation

    A modified version of https://chao-ji.github.io/jekyll/update/2018/07/19/BilinearResize.html

    `image` is a 2-D numpy array
    `height` and `width` are the desired spatial dimension of the new 2-D array.
    """
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


def cv2_resize(spec, target_height, target_width):
    import cv2
    return cv2.resize(
        spec,
        dsize=(target_width, target_height),
        interpolation=cv2.INTER_CUBIC
    )


class AudioTransform(object):

    def convert(self, data, sampling_rate):
        """Convert 1D audio signal into a 2D image array

        Returns tuple of 2D image array and dictionary of metadata about the conversion
        """
        raise NotImplementedError


class SpectrogramTransform(AudioTransform):

    def __init__(
            self,
            spec_sampling_rate,
            spec_freq_spacing,
            min_freq=0,
            max_freq=None,
            ):
        self.spec_sampling_rate = spec_sampling_rate
        self.spec_freq_spacing = spec_freq_spacing
        self.min_freq = min_freq
        self.max_freq = max_freq

    def convert(self, data, sampling_rate, output_size=None):
        """Convert 1D audio signal into a spectrogram

        Returns spectrogram and metadata dictionary
        """
        t, f, spec = compute_spectrogram(
            data,
            sampling_rate,
            spec_sample_rate=self.spec_sampling_rate,
            freq_spacing=self.spec_freq_spacing,
            min_freq=self.min_freq,
            max_freq=self.max_freq,
        )

        if output_size is None:
            output_size = spec.shape
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
            }
        }

        return spec, metadata


def compute_ampenv(signal, sampling_rate):
    # TODO: this is just a quick implementation. replace with better later?
    return np.abs(signal)


class AmplitudeEnvelopeTwoSidedTransform(AudioTransform):

    def __init__(self, gradient=None, ymax=None):
        """Initialize an 2-sided amplitude envelope image

        Params
        ======
        ymax : float
            yscale of the output plot
        gradient : tuple or None
            if provided, is a tuple of two floats between 0 and 1. Output
            values will be scaled between these two numbers. Note that 0
            is likely the same as background and so it is advisable
            not to start it at 0 exactly
        """
        if gradient and (
                    not isinstance(gradient, tuple)
                    or not len(gradient) == 2
                    or not (0 <= gradient[0] <= gradient[1] <= 1)
                ):
            raise ValueError("Gradient must be a tuple of 2 floats between 0 and 1")
        self.ymax = ymax
        self.gradient = gradient

    def convert(self, data, sampling_rate, output_size, scale=1.0):
        """Convert 1D audio signal into a spectrogram

        Returns spectrogram and metadata dictionary
        """
        ampenv = compute_ampenv(data, sampling_rate)

        t = np.linspace(0, len(data) / sampling_rate, output_size[1])
        ampenv = np.interp(
            t,
            np.linspace(0, len(data) / sampling_rate, len(data)),
            ampenv
        )

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
            for i in range(n_rows_to_fill):
                val = compute_color(i)
                img[half_height + i, col] = val
                img[half_height - i - 1, col] = val

        metadata = {
            "t": t,
            "AmplitudeEnvelopeTwoSidedTransform": {
                "ymax": ymax,
                "gradient": self.gradient
            }
        }

        return img, metadata
