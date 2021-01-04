"""Spectrogram computation

Copied/adapted from https://github.com/theunissenlab/soundsig to remove
dependency and avoid slow import
"""
import numpy as np


def _get_frequencies(signal_length, sample_rate):
    freq = np.fft.fftfreq(signal_length, d=1.0 / sample_rate)
    nz = freq >= 0.0
    return freq[nz]


def _estimate(nstd, signal, sample_rate, start_time, end_time):
    nwinlen = len(signal)
    if nwinlen % 2 == 0:
        nwinlen += 1
    hnwinlen = nwinlen // 2

    # Construct the window
    gauss_t = np.arange(-hnwinlen, hnwinlen + 1, 1.0)
    gauss_std = float(nwinlen) / float(nstd)
    gauss_window = np.exp(-gauss_t**2 / (2.0 * gauss_std**2)) / (gauss_std * np.sqrt(2 * np.pi))

    # Window the signal and take the FFT
    fft_len = len(signal)
    windowed_slice = signal[:fft_len] * gauss_window[:fft_len]
    s_fft = np.fft.fft(windowed_slice, n=fft_len)# , overwrite_x=1)
    freq = np.fft.fftfreq(fft_len, d=1.0/sample_rate)
    nz = freq >= 0.0

    return freq[nz], s_fft[nz]


def spectrogram(signal, sampling_rate, spec_sample_rate, freq_spacing, nstd=6, min_freq=0, max_freq=None):
    increment = 1.0 / spec_sample_rate
    window_length = nstd / (2.0 * np.pi * freq_spacing)

    if max_freq is None:
        max_freq = sample_rate / 2.0

    # Compute lengths in # of samples
    nwinlen = int(sampling_rate * window_length)
    if nwinlen % 2 == 0:
        nwinlen += 1
    hnwinlen = nwinlen // 2
    assert len(signal) > nwinlen, "len(s)=%d, nwinlen=%d" % (len(signal), nwinlen)

    # Get the values for the frequency axis by estimating the spectrum of a dummy slice
    full_freq = _get_frequencies(nwinlen, sampling_rate)
    freq_index = (full_freq >= min_freq) & (full_freq <= max_freq)
    freq_arr = full_freq[freq_index]
    nfreq = freq_index.sum()

    nincrement = int(np.round(sampling_rate * increment))
    nwindows = len(signal) // nincrement
    # Pad the signal with zeros
    zs = np.zeros([len(signal) + 2 * hnwinlen])
    zs[hnwinlen:-hnwinlen] = signal
    window_centers = np.arange(nwindows) * nincrement + hnwinlen

    # Take the FFT of each segment, padding with zeros when necessary to keep window length the same
    spec = np.zeros([nfreq, nwindows], dtype='complex')
    for k in range(nwindows):
        center = window_centers[k]
        si = center - hnwinlen
        ei = center + hnwinlen + 1

        spec_freq, est = _estimate(nstd, zs[si:ei], sampling_rate, si / sampling_rate, ei / sampling_rate)
        findex = (spec_freq <= max_freq) & (spec_freq >= min_freq)
        spec[:, k] = est[findex]

    # Note that the desired spectrogram rate could be slightly modified
    t_arr = np.arange(0, nwindows, 1.0) * float(nincrement) / sampling_rate
    spec = np.abs(spec)

    return t_arr, freq_arr, spec
