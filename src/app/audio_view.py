from __future__ import annotations

from typing import Optional

import numpy as np
import soundfile
from inspec.transform import compute_spectrogram, resize
from inspec_core.base_view import FileReader, Size, View
from numpy.typing import NDArray
from pydantic import BaseModel
from render.types import Intensity


class TimeRange(BaseModel):
    start: float
    end: float


class AudioViewState(View):
    expect_size: Size.FixedSize
    time_range: TimeRange
    channel: int

    spec_sampling_rate: int = 1000
    spec_freq_spacing: float = 50.0
    min_freq: float = 250.0
    max_freq: Optional[float] = 8_000.0

    class Config:
        arbitrary_types_allowed = True


class AudioReaderComponent(BaseModel, FileReader[Intensity, AudioViewState]):
    class LoadedData(BaseModel):
        audio: NDArray[np.float64]
        sample_rate: int
        channels: list[int]

        class Config:
            arbitrary_types_allowed = True

    filename: str
    data: Optional[LoadedData] = None

    def _ensure_data(self) -> LoadedData:
        if self.data is None:
            audio, sample_rate = soundfile.read(self.filename, always_2d=True)
            channels = list(range(audio.shape[1]))
            self.data = AudioReaderComponent.LoadedData(
                audio=audio, sample_rate=sample_rate, channels=channels
            )
        return self.data

    def get_view(self, view: AudioViewState) -> NDArray:
        data = self._ensure_data()
        start_idx = int(view.time_range.start * data.sample_rate)
        end_idx = int(view.time_range.end * data.sample_rate)

        _, _, spec = compute_spectrogram(
            data.audio[start_idx:end_idx, view.channel],
            data.sample_rate,
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
