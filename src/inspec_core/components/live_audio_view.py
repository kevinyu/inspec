from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator, Optional

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

from inspec_core.audio_utils import compute_spectrogram, db_scale, resize, stream_audio
from inspec_core.render.types import Intensity

from .base_view import FileStreamer, View
from .size import Size


class TimeRange(BaseModel):
    start: float
    end: float


class ListenConfig(BaseModel):
    device: Optional[int] = None
    channels: int = 1
    chunk_size: int = 1024
    step_chunks: int = 2  # no. of chunks per spectrogram calculation
    sampling_rate: Optional[int] = None


class LiveAudioViewState(View):
    gain: float = 0.0
    spec_max: float = 600.0  # Not sure what units this is. Maybe better to make it a magic constant and control everything with gain?

    # Microphone parameters
    listen: ListenConfig = ListenConfig()

    # Spectrogram parameters
    spec_sampling_rate: int = 200
    spec_freq_spacing: float = 50.0
    min_freq: float = 100.0
    max_freq: Optional[float] = 2_000.0

    class Config:
        arbitrary_types_allowed = True


class LiveAudioComponent(BaseModel, FileStreamer[Intensity, LiveAudioViewState]):
    executor: ThreadPoolExecutor

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._output_queue: asyncio.Queue[NDArray] = asyncio.Queue()
        return super().model_post_init(__context)

    async def _listen(self, view: LiveAudioViewState, size: Size.FixedSize) -> None:
        buffer = np.zeros(
            (view.listen.chunk_size * view.listen.step_chunks, view.listen.channels)
        )
        counter = 0
        async for chunk in stream_audio():
            buffer[counter * chunk.frames : (counter + 1) * chunk.frames,] = chunk.data
            counter = (counter + 1) % view.listen.step_chunks
            if counter % view.listen.step_chunks == 0:
                self.executor.submit(
                    self._conversion,
                    1 * buffer,
                    chunk.sample_rate,
                    view,
                    size,
                )

    def _conversion(
        self,
        buffer: NDArray,
        sampling_rate: int,
        view: LiveAudioViewState,
        size: Size.FixedSize,
    ) -> None:
        assert self._loop is not None
        desired_rows = size.height
        desired_cols = size.width
        buffer = db_scale(buffer, view.gain)
        arrays = []
        for channel in range(buffer.shape[1]):
            _, _, spec = compute_spectrogram(
                buffer[:, channel],
                sampling_rate,
                spec_sample_rate=view.spec_sampling_rate,
                freq_spacing=view.spec_freq_spacing,
                min_freq=view.min_freq,
                max_freq=view.max_freq,
            )
            spec = resize(spec, (desired_rows, desired_cols))
            arrays.append(spec)
        data = np.stack(arrays, axis=2)
        # scale to 0 to 1
        data = np.clip(data / view.spec_max, 0, 1)
        self._loop.call_soon_threadsafe(
            self._output_queue.put_nowait,
            data,
        )

    async def stream_view(
        self,
        view: LiveAudioViewState,
        size: Size.FixedSize,
    ) -> AsyncIterator[NDArray[Intensity]]:  # type: ignore
        self._loop = asyncio.get_running_loop()
        listen_task = self._loop.create_task(self._listen(view, size))
        try:
            while True:
                yield np.vectorize(Intensity)(await self._output_queue.get())
        finally:
            listen_task.cancel()

    def get_view(self, view: LiveAudioViewState) -> LiveAudioViewState:
        return view
