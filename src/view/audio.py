from __future__ import annotations

from typing import Optional

import numpy as np
import soundfile
from inspec.transform import compute_spectrogram, resize
from numpy.typing import NDArray
from pydantic import BaseModel
from render.types import Intensity
from inspec_core.base_view import FileReader, Size, View


class BasicAudioView(View):
    # mode: Literal["spectrogram", "waveform"]

    expect_size: Size.FixedSize
    channel: int = 0

    spec_sampling_rate: int = 1000
    spec_freq_spacing: float = 50.0
    min_freq: float = 250.0
    max_freq: Optional[float] = 8_000.0


class BasicAudioReader(BaseModel, FileReader[Intensity, BasicAudioView]):
    filename: str

    def get_view(self, view: BasicAudioView) -> NDArray:
        data, sampling_rate = soundfile.read(self.filename)

        _, _, spec = compute_spectrogram(
            data[:, view.channel],
            sampling_rate,
            spec_sample_rate=view.spec_sampling_rate,
            freq_spacing=view.spec_freq_spacing,
            min_freq=view.min_freq,
            max_freq=view.max_freq,
        )

        min_val = np.min(spec)
        max_val = np.max(spec)
        arr = (spec - min_val) / (max_val - min_val)
        arr = resize(
            arr,
            target_height=view.expect_size.height,
            target_width=view.expect_size.width,
        )
        arr = np.vectorize(Intensity)(arr)

        return arr
