import numpy as np
import soundfile


class BaseAudioPlugin(object):

    def __init__(self):
        self.data = None
        self.sampling_rate = None
        self._last_render_data = {}

    def set_data(self, data, sampling_rate):
        self.data = data
        self.sampling_rate = sampling_rate

    def get_channel(self, channel):
        if self.data.ndim > 1:
            data = self.data[:, channel]
        else:
            data = self.data
        return data

    @property
    def last_render_data(self):
        return self._last_render_data

    def receive(self, data):
        raise NotImplementedError

    def size_available(self):
        raise NotImplementedError

    def convert_audio(self, data, sampling_rate):
        raise NotImplementedError

    def render(self):
        raise NotImplementedError


class SoundFileMixin(object):

    def read_file(self, filename, read_samples=None, start_idx=None):
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
        self.set_data(data, sampling_rate)
        return metadata

    def read_file_by_time(self, filename, duration=None, time_start=None):
        if duration is None and time_start is None:
            return self.read_file(filename)

        metadata = self.read_file_metadata(filename)
        if duration:
            frames = int(np.floor(duration * metadata["sampling_rate"]))
        else:
            frames = metadata["frames"]

        if time_start:
            start_idx = int(np.floor(time_start * metadata["sampling_rate"]))
        else:
            start_idx = 0

        return self.read_file(filename, read_samples=frames, start_idx=start_idx)

    def read_file_metadata(self, filename):
        with soundfile.SoundFile(filename) as f:
            return {
                "sampling_rate": f.samplerate,
                "frames": f.frames,
                "n_channels": f.channels,
                "duration": f.frames / f.samplerate
            }
