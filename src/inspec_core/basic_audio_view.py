from __future__ import annotations

from typing import Optional

import numpy as np
import soundfile
from audio_utils import compute_spectrogram, resize
from inspec_core.base_view import FileReader, Size, View
from numpy.typing import NDArray
from pydantic import BaseModel
from render.types import Intensity


class BasicAudioView(View):
    # mode: Literal["spectrogram", "waveform"]

    channel: int = 0

    spec_sampling_rate: int = 1000
    spec_freq_spacing: float = 50.0
    min_freq: float = 250.0
    max_freq: Optional[float] = 8_000.0


class BasicAudioReader(BaseModel, FileReader[Intensity, BasicAudioView]):
    filename: str
    spec: Optional[NDArray] = None

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: BasicAudioView, size: Size.FixedSize) -> NDArray:
        if self.spec is None:
            data, sampling_rate = soundfile.read(self.filename)
            _, _, self.spec = compute_spectrogram(
                data[:, view.channel],
                sampling_rate,
                spec_sample_rate=view.spec_sampling_rate,
                freq_spacing=view.spec_freq_spacing,
                min_freq=view.min_freq,
                max_freq=view.max_freq,
            )

        min_val = np.min(self.spec)
        max_val = np.max(self.spec)
        arr = (self.spec - min_val) / (max_val - min_val)
        arr = resize(
            arr,
            target_height=size.height,
            target_width=size.width,
        )
        arr = np.vectorize(Intensity)(arr)

        return arr
