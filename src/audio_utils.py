from __future__ import annotations
import asyncio
import dataclasses
from typing import Any, AsyncIterator, Optional, TypeVar

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray


@dataclasses.dataclass
class AudioChunk:
    """
    A chunk of audio data
    """

    data: NDArray
    frames: int
    channels: int
    sample_rate: int


def list_devices():
    """
    List the available audio devices
    """
    return sd.query_devices()


async def stream_audio(
    device_idx: Optional[int] = None
) -> AsyncIterator[AudioChunk]:
    """
    Stream audio from audio device (defualt None)
    """
    q: asyncio.Queue[AudioChunk] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def cb(
        indata: NDArray[np.int16],
        frames: int,
        __time: Any,
        __status: sd.CallbackFlags
    ):
        loop.call_soon_threadsafe(
            q.put_nowait,
            AudioChunk(
                data=indata.copy(),
                frames=frames,
                channels=indata.shape[1],
                sample_rate=int(stream.samplerate),
            ),
        )

    device_info = sd.query_devices(sd.default.device[0])
    assert isinstance(device_info, dict)
    stream = sd.InputStream(
        device=None,
        samplerate=device_info["default_samplerate"],
        dtype=np.int16,
        callback=cb,
    )
    try:
        stream.start()
        while True:
            yield await q.get()
    finally:
        stream.stop()


async def test_listen():
    async for chunk in stream_audio(0):
        pass


T = TypeVar("T", NDArray, float)


def db_scale(x: T, dB: float) -> T:
    """
    Scale the channels of a signal (in dB) independently
    """
    return np.power(10.0, dB / 20.0) * x
