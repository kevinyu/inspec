import unittest
from unittest import mock

import numpy as np

from inspec.io import LoadedAudioData
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
)


class TestSpectrogramTransform(unittest.TestCase):

    def test_init(self):
        transform = SpectrogramTransform(
            spec_sampling_rate=500,
            spec_freq_spacing=10,
            min_freq=10,
            max_freq=8000
        )
        self.assertEqual(transform.spec_sampling_rate, 500)
        self.assertEqual(transform.spec_freq_spacing, 10)
        self.assertEqual(transform.min_freq, 10)
        self.assertEqual(transform.max_freq, 8000)

        transform = SpectrogramTransform(
            spec_sampling_rate=1000,
            spec_freq_spacing=50,
        )
        self.assertEqual(transform.spec_sampling_rate, 1000)
        self.assertEqual(transform.spec_freq_spacing, 50)
        self.assertEqual(transform.min_freq, 0)
        self.assertEqual(transform.max_freq, None)

    def test_convert(self):
        np.random.seed(420)

        data = np.random.random((48000,))
        sampling_rate = 48000

        transform = SpectrogramTransform(
            spec_sampling_rate=1000,
            spec_freq_spacing=50,
            min_freq=250,
            max_freq=10000
        )

        img, metadata = transform.convert(
            LoadedAudioData(data, sampling_rate),
            output_size=(40, 80)
        )

        self.assertEqual(img.shape, (40, 80))

        img, metadata = transform.convert(
            LoadedAudioData(data, sampling_rate),
            output_size=(49, 49)
        )

        self.assertEqual(img.shape, (49, 49))

    def test_metadata(self):
        np.random.seed(420)

        data = np.random.random((48000,))
        sampling_rate = 48000

        transform = SpectrogramTransform(
            spec_sampling_rate=1000,
            spec_freq_spacing=50,
            min_freq=250,
            max_freq=10000
        )

        img, metadata = transform.convert(
            LoadedAudioData(data, sampling_rate),
            output_size=(40, 80)
        )

        self.assertEqual(
            metadata["SpectrogramTransform"]["spec_sampling_rate"],
            1000,
        )
        self.assertEqual(
            metadata["SpectrogramTransform"]["freq_spacing"],
            50,
        )
        self.assertEqual(
            metadata["SpectrogramTransform"]["min_freq"],
            250,
        )
        self.assertEqual(
            metadata["SpectrogramTransform"]["max_freq"],
            10000,
        )


class TestAmplitudeEnvelopeTwoSidedTransform(unittest.TestCase):

    def test_init(self):
        transform = AmplitudeEnvelopeTwoSidedTransform()
        self.assertEqual(transform.ymax, None)
        self.assertEqual(transform.gradient, (1.0, 1.0))

        transform = AmplitudeEnvelopeTwoSidedTransform(ymax=1.0, gradient=(0.2, 1.0))
        self.assertEqual(transform.ymax, 1.0)
        self.assertEqual(transform.gradient, (0.2, 1.0))

        with self.assertRaises(ValueError):
            AmplitudeEnvelopeTwoSidedTransform(ymax=1.0, gradient=True)  # type: ignore

    @mock.patch("inspec.transform.compute_ampenv")
    def test_convert(self, mock_compute_ampenv):
        transform = AmplitudeEnvelopeTwoSidedTransform()

        data = np.array([
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9
        ])
        mock_compute_ampenv.return_value = data

        img, metadata = transform.convert(LoadedAudioData(data, 1), output_size=(10, 10))
        self.assertEqual(img.shape, (10, 10))
        np.testing.assert_array_equal(img,
            np.array([
                 [0., 0., 0., 0., 0., 0., 0., 0., 0., 1.,],
                 [0., 0., 0., 0., 0., 0., 0., 1., 1., 1.,],
                 [0., 0., 0., 0., 0., 1., 1., 1., 1., 1.,],
                 [0., 0., 0., 1., 1., 1., 1., 1., 1., 1.,],
                 [0., 1., 1., 1., 1., 1., 1., 1., 1., 1.,],
                 [0., 1., 1., 1., 1., 1., 1., 1., 1., 1.,],
                 [0., 0., 0., 1., 1., 1., 1., 1., 1., 1.,],
                 [0., 0., 0., 0., 0., 1., 1., 1., 1., 1.,],
                 [0., 0., 0., 0., 0., 0., 0., 1., 1., 1.,],
                 [0., 0., 0., 0., 0., 0., 0., 0., 0., 1.,],
            ])
        )

    @mock.patch("inspec.transform.compute_ampenv")
    def test_metadata(self, mock_compute_ampenv):
        transform = AmplitudeEnvelopeTwoSidedTransform(gradient=(0.5, 0.8))

        data = np.array([
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9
        ])
        mock_compute_ampenv.return_value = data

        img, metadata = transform.convert(LoadedAudioData(data, 1), output_size=(10, 10))
        self.assertEqual(metadata["AmplitudeEnvelopeTwoSidedTransform"]["ymax"], 9.)
        self.assertEqual(metadata["AmplitudeEnvelopeTwoSidedTransform"]["gradient"], (0.5, 0.8))

    @mock.patch("inspec.transform.compute_ampenv")
    def test_gradient(self, mock_compute_ampenv):
        transform = AmplitudeEnvelopeTwoSidedTransform(gradient=(0.2, 1.0))

        data = np.array([
            0, 1, 2, 3, 4, 5, 0, 1, 2, 3
        ])
        mock_compute_ampenv.return_value = data

        img, metadata = transform.convert(LoadedAudioData(data, 1), output_size=(8, 10))
        self.assertEqual(metadata["AmplitudeEnvelopeTwoSidedTransform"]["ymax"], 5.)
        self.assertEqual(metadata["AmplitudeEnvelopeTwoSidedTransform"]["gradient"], (0.2, 1.0))

        np.testing.assert_array_almost_equal(
            img,
            np.array([
                [0.,  0.,  0.,  0.,  0.,  1.,  0.,  0.,  0.,  0., ],
                [0.,  0.,  0.,  0.,  0.8, 0.8, 0.,  0.,  0.,  0., ],
                [0.,  0.,  0.6, 0.6, 0.6, 0.6, 0.,  0.,  0.6, 0.6,],
                [0.,  0.4, 0.4, 0.4, 0.4, 0.4, 0.,  0.4, 0.4, 0.4,],
                [0.,  0.4, 0.4, 0.4, 0.4, 0.4, 0.,  0.4, 0.4, 0.4,],
                [0.,  0.,  0.6, 0.6, 0.6, 0.6, 0.,  0.,  0.6, 0.6,],
                [0.,  0.,  0.,  0.,  0.8, 0.8, 0.,  0.,  0.,  0., ],
                [0.,  0.,  0.,  0.,  0.,  1.,  0.,  0.,  0.,  0., ],
            ])
        )
