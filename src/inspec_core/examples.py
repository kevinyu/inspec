import asyncio
import enum
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np
from colormaps import get_colormap
from inspec_core.base_view import Size
from inspec_core.live_audio_view import LiveAudioComponent, LiveAudioViewState
from render.display import display
from render.renderer import make_intensity_renderer
from render.types import CharShape


class PrintMode(str, enum.Enum):
    Scroll = "scroll"
    Fixed = "fixed"


async def print_live_audio(
    channel: int = 0,
    width: Optional[int] = None,
    cmap: str = "viridis",
    mode: PrintMode = PrintMode.Fixed,
    gain: float = 0.0,
    spec_sampling_rate: int = 200,
    spec_freq_spacing: float = 50.0,
    min_freq: float = 400.0,
    max_freq: Optional[float] = 2_000.0,
):
    component = LiveAudioComponent(executor=ThreadPoolExecutor(max_workers=1))

    size = Size.FixedSize(
        height=width or os.get_terminal_size().columns,  # 'width'
        width=1,  # 'height'
    )
    view = LiveAudioViewState(
        # This is transposed since we want to print out spectrogram vertically
        gain=gain,
        spec_sampling_rate=spec_sampling_rate,
        spec_freq_spacing=spec_freq_spacing,
        min_freq=min_freq,
        max_freq=max_freq,
    )

    colormap = get_colormap(cmap)
    renderer = make_intensity_renderer(colormap, shape=CharShape.Full)
    async for arr in component.stream_view(view, size):
        display(
            renderer.apply(arr[:, :, channel].T),
            end="\n" if mode is PrintMode.Scroll else "\r",
        )


if __name__ == "__main__":
    asyncio.run(print_live_audio())
