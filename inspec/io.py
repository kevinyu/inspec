import glob
import os

import numpy as np
import soundfile


class AudioReader(object):

    @staticmethod
    def read_file(filename, read_samples=None, start_idx=None, channel=None):
        if channel is None:
            channel = 0

        if read_samples is not None:
            data, sampling_rate = soundfile.read(filename, read_samples, start_idx)
        else:
            data, sampling_rate = soundfile.read(filename)

        metadata = {
            "sampling_rate": sampling_rate,
            "frames": len(data),
            "n_channels": 1 if data.ndim == 1 else data.shape[1],
            "duration": len(data) / sampling_rate,
            "offset": 0
        }

        if data.ndim > 1:
            return data[:, channel], sampling_rate, metadata
        else:
            return data, sampling_rate, metadata

    @staticmethod
    def read_file_by_time(filename, duration=None, time_start=None, channel=None):
        if duration is None and time_start is None:
            return AudioReader.read_file(filename)

        metadata = AudioReader.read_file_metadata(filename)
        if duration:
            frames = int(np.floor(duration * metadata["sampling_rate"]))
        else:
            frames = metadata["frames"]

        if time_start:
            start_idx = int(np.floor(time_start * metadata["sampling_rate"]))
        else:
            start_idx = 0

        if channel >= metadata["n_channels"]:
            raise IOError("Cannot read channel {} on a file with {} channels".format(channel, metadata["n_channels"]))

        return AudioReader.read_file(filename, read_samples=frames, start_idx=start_idx, channel=channel)

    @staticmethod
    def read_file_metadata(filename):
        with soundfile.SoundFile(filename) as f:
            return {
                "sampling_rate": f.samplerate,
                "frames": f.frames,
                "n_channels": f.channels,
                "duration": f.frames / f.samplerate
            }


def gather_files(paths, extension):
    if extension.startswith("."):
        extension = extension[1:]

    if isinstance(paths, str):
        paths = [paths]

    if not len(paths):
        paths = ["."]

    results = []
    for filename in paths:
        if not os.path.isdir(filename):
            results.append(filename)
        else:
            for _filename in glob.glob(os.path.join(filename, "*.{}".format(extension))):
                results.append(_filename)

    return results



class ImageReader(object):

    @staticmethod
    def read_file(filename):
        import cv2
        return cv2.imread(filename)[::-1], {}
