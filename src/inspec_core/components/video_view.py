from __future__ import annotations

from typing import AsyncIterator, Optional

import cv2
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

from inspec_core.audio_utils import resize
from inspec_core.render.types import RGB, Intensity

from .base_view import FileReader, FileStreamer, Size, T, View, ViewT
from .size import preserve_aspect_ratio


def get_video_metadata(
    filename: str, cap: Optional[cv2.VideoCapture] = None
) -> VideoMetadata:
    passed_cap = cap is not None
    if cap is None:
        cap = cv2.VideoCapture(filename)
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        return VideoMetadata(
            width=width, height=height, frame_count=frame_count, fps=fps
        )
    finally:
        if not passed_cap:
            # Don't relase the cap if it was passed in!
            cap.release()


class VideoMetadata(BaseModel):
    width: int
    height: int
    frame_count: int
    fps: float


class BaseVideoReader(BaseModel, FileReader[T, ViewT]):
    filename: str
    video_metadata: Optional[VideoMetadata] = None

    def ensure_metadata(self, cap: Optional[cv2.VideoCapture] = None) -> VideoMetadata:
        if self.video_metadata is None:
            self.video_metadata = get_video_metadata(self.filename, cap=cap)

        return self.video_metadata


class VideoViewState(View):
    frame: int = 0


class GreyscaleVideoFrameReader(BaseVideoReader[Intensity, VideoViewState]):
    """
    Instead of loading the entire video into memory, this class reads a single frame on request.
    """

    loaded: Optional[
        tuple[set[int], NDArray]
    ] = None  # Keep track of which frames are loaded

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: VideoViewState, size: Size.Size) -> NDArray:
        if self.loaded is None or view.frame not in self.loaded[0]:
            cap = cv2.VideoCapture(self.filename)
            metadata = self.ensure_metadata(cap=cap)
            try:
                if self.loaded is None:
                    self.loaded = (
                        set(),
                        np.empty(
                            (metadata.frame_count, metadata.height, metadata.width),
                            np.uint8,
                        ),
                    )

                if view.frame not in self.loaded[0]:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, view.frame)
                    ret, frame = cap.read()
                    assert ret
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self.loaded[1][view.frame] = frame
                    self.loaded[0].add(view.frame)
            finally:
                cap.release()
        else:
            metadata = self.ensure_metadata()

        target_shape = preserve_aspect_ratio(
            size, original_width=metadata.width, original_height=metadata.height
        )
        frame = self.loaded[1][view.frame]
        frame = cv2.resize(frame, (target_shape.width, target_shape.height))
        frame = np.clip(frame / 255, 0, 1)
        frame = np.flipud(frame)
        return np.vectorize(Intensity)(frame)


class RGBVideoFrameReader(BaseVideoReader[RGB, VideoViewState]):
    loaded: Optional[
        tuple[set[int], NDArray]
    ] = None  # Keep track of which frames are loaded

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def _to_rgb(vec: NDArray[np.uint8]) -> RGB:
        return RGB(*vec)

    def get_view(self, view: VideoViewState, size: Size.Size) -> NDArray:
        if self.loaded is None or view.frame not in self.loaded[0]:
            cap = cv2.VideoCapture(self.filename)
            metadata = self.ensure_metadata(cap=cap)
            try:
                if self.loaded is None:
                    self.loaded = (
                        set(),
                        np.empty(
                            (metadata.frame_count, metadata.height, metadata.width, 3),
                            np.uint8,
                        ),
                    )

                if view.frame not in self.loaded[0]:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, view.frame)
                    ret, frame = cap.read()
                    assert ret
                    self.loaded[1][view.frame] = frame
                    self.loaded[0].add(view.frame)
            finally:
                cap.release()
        else:
            metadata = self.ensure_metadata()

        target_shape = preserve_aspect_ratio(
            size, original_width=metadata.width, original_height=metadata.height
        )
        frame = self.loaded[1][view.frame]
        frame = cv2.resize(frame, (target_shape.width, target_shape.height))
        frame = np.flipud(frame)
        return np.vectorize(RGBVideoFrameReader._to_rgb, signature="(n) -> ()")(frame)


class GreyscaleVideoReader(BaseVideoReader[Intensity, VideoViewState]):
    loaded: Optional[NDArray] = None

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: VideoViewState, size: Size.Size) -> NDArray:
        if self.loaded is None:
            cap = cv2.VideoCapture(self.filename)
            metadata = self.ensure_metadata(cap=cap)
            try:
                # Instead of frame by frame, hti sclass will load it all at once
                self.loaded = np.empty(
                    (metadata.frame_count, metadata.height, metadata.width), np.uint8
                )
                for _ in range(metadata.frame_count):
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    assert ret
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self.loaded[view.frame] = frame
            finally:
                cap.release()
        else:
            metadata = self.ensure_metadata()

        target_shape = preserve_aspect_ratio(
            size, original_width=metadata.width, original_height=metadata.height
        )
        frame = resize(
            self.loaded[view.frame], (target_shape.height, target_shape.width)
        )
        frame = np.clip(frame / 255, 0, 1)
        frame = np.flipud(frame)

        return np.vectorize(Intensity)(frame)


class GreyscaleVideoStreamer(BaseModel, FileStreamer[Intensity, View]):
    filename: str
    video_metadata: VideoMetadata

    class Config:
        arbitrary_types_allowed = True

    def ensure_metadata(self, cap: Optional[cv2.VideoCapture] = None) -> VideoMetadata:
        if self.video_metadata is None:
            self.video_metadata = get_video_metadata(self.filename, cap=cap)

        return self.video_metadata

    async def stream_view(
        self, view: View, size: Size.FixedSize
    ) -> AsyncIterator[NDArray]:
        cap = cv2.VideoCapture(self.filename)
        metadata = self.ensure_metadata(cap=cap)
        target_shape = preserve_aspect_ratio(
            size, original_width=metadata.width, original_height=metadata.height
        )
        try:
            ret = True
            while ret:
                ret, frame = cap.read()
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame = resize(frame, (target_shape.height, target_shape.width))
                frame = np.clip(frame / 255, 0, 1)
                frame = np.flipud(frame)
                yield np.vectorize(Intensity)(frame)
        finally:
            cap.release()
