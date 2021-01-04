import soundfile


class BaseAudioPlugin(object):

    def __init__(self):
        self.data = None
        self.sampling_rate = None
        self._last_render_metadata = {}

    def set_data(self, data, sampling_rate):
        self.data = data
        self.sampling_rate = sampling_rate

    @property
    def last_render_data(self):
        return self._last_render_data

    def render(self):
        raise NotImplementedError


class SoundFileMixin(object):

    def read_file(self, filename):
        data, sampling_rate = soundfile.read(filename)
        self.set_data(data, sampling_rate)

    def read_file_partial(self, filename, read_samples, start_idx):
        data, sampling_rate = soundfile.read(filename, read_samples, start_idx)
        self.set_data(data, sampling_rate)

    def read_file_metadata(self, filename):
        with soundfile.SoundFile(filename) as f:
            return {
                "sampling_rate": f.samplerate,
                "frames": f.frames,
                "n_channels": f.channels,
                "duration": f.frames / f.samplerate
            }
