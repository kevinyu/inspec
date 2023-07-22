import numpy as np

from audio_utils import _get_frequencies, compute_spectrogram, resize


def test_get_frequencies():
    signal_length = 200
    sampling_rate = 1000
    freq = _get_frequencies(signal_length, sampling_rate)

    # determine what we would expect
    nyquist = sampling_rate / 2
    n_freqs = np.ceil(signal_length / 2)
    expected_freq = (np.arange(n_freqs) / n_freqs) * nyquist

    np.testing.assert_array_equal(freq, expected_freq)


def test_spectrogram():
    signal = np.random.random(48000,)
    t, f, spec = compute_spectrogram(signal, 48000, 1000, 50)
    assert spec.shape == (459, 1000)

    signal = np.random.random(48000,)
    t, f, spec = compute_spectrogram(signal, 48000, 1000, 50, min_freq=1000, max_freq=10000)
    assert f[0] > 1000
    assert f[-1] < 10000


def test_resize_smaller():
    x = np.array([
        [1, 2, 3, 4],
        [3, 4, 5, 6],
        [5, 6, 7, 8],
        [7, 9, 11, 13],
    ])

    expected_3_3 = np.array([
        [1, 2.5, 4],
        [4, 5.5, 7],
        [7, 10, 13]
    ])

    x_ = resize(x, 3, 3)
    np.testing.assert_array_equal(x_, expected_3_3)

    expected_2_2 = np.array([
        [1, 4],
        [7, 13]
    ])

    x_ = resize(x, 2, 2)
    np.testing.assert_array_equal(x_, expected_2_2)


def test_resize_bigger(self):
    x = np.array([
        [1, 2, 3, 4],
        [3, 4, 5, 6],
        [5, 6, 7, 8],
        [7, 9, 11, 13],
    ])

    expected_5_5 = np.array([
        [1., 1.75, 2.5, 3.25, 4.],
        [ 2.5, 3.25, 4., 4.75, 5.5],
        [ 4., 4.75, 5.5, 6.25, 7.],
        [ 5.5, 6.4375, 7.375, 8.3125, 9.25],
        [ 7., 8.5, 10., 11.5, 13.],
    ])

    x_ = resize(x, 5, 5)
    np.testing.assert_array_equal(x_, expected_5_5)


def test_resize_realistic_size():
    x = np.random.random((200, 6000))
    x_ = resize(x, 40, 160)
    assert x_.shape == (40, 160)
