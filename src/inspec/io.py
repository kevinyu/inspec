from __future__ import annotations

import abc
import glob
import os
from dataclasses import dataclass
from typing import Generic, Optional, Type, TypeVar

import numpy as np
import soundfile
from numpy.typing import NDArray
from PIL import Image, UnidentifiedImageError  # TODO: this import might be slow?


class FileInvalidError(Exception):
    pass


ReturnT = TypeVar("ReturnT")


class FileReader(Generic[ReturnT], abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def check_file(filename) -> None:
        """
        Raise FileInvalidError if it can't be read by this class
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def read_file(filename, **kwargs) -> ReturnT:
        """
        Read the file and return the data
        """
        raise NotImplementedError


@dataclass
class LoadedAudioData:
    @dataclass
    class Metadata:
        sampling_rate: int
        frames: int
        n_channels: int
        duration: float
        offset: int

    data: NDArray
    sampling_rate: int
    metadata: Optional[LoadedAudioData.Metadata] = None


class AudioReader(FileReader[LoadedAudioData]):
    @staticmethod
    def check_file(filename) -> None:
        try:
            AudioReader.read_file_metadata(filename)
        except RuntimeError:
            raise FileInvalidError

    @staticmethod
    def read_file(
        filename: str,
        read_samples: Optional[int] = None,
        start_idx: Optional[int] = None,
        channel: Optional[int] = None,
    ) -> LoadedAudioData:
        if channel is None:
            channel = 0

        if read_samples is None and start_idx is None:
            data, sampling_rate = soundfile.read(filename)
        elif read_samples is not None and start_idx is not None:
            data, sampling_rate = soundfile.read(filename, read_samples, start_idx)
        else:
            raise ValueError(
                "Must specify either both read_samples and start_idx or neither"
            )

        metadata = LoadedAudioData.Metadata(
            sampling_rate=sampling_rate,
            frames=len(data),
            n_channels=1 if data.ndim == 1 else data.shape[1],
            duration=len(data) / sampling_rate,
            offset=0,
        )

        if data.ndim > 1:
            return LoadedAudioData(data[:, channel], sampling_rate, metadata)
        else:
            return LoadedAudioData(data, sampling_rate, metadata)

    @staticmethod
    def read_file_by_time(
        filename,
        duration: Optional[float] = None,
        time_start: Optional[float] = None,
        channel: Optional[int] = None,
    ) -> LoadedAudioData:
        if duration is None and time_start is None:
            return AudioReader.read_file(filename)

        metadata = AudioReader.read_file_metadata(filename)
        if duration:
            frames = int(np.floor(duration * metadata.sampling_rate))
        else:
            frames = metadata.frames

        if time_start:
            start_idx = int(np.floor(time_start * metadata.sampling_rate))
        else:
            start_idx = 0

        if channel is not None and channel >= metadata.n_channels:
            raise IOError(
                f"Cannot read channel {channel} on a file with {metadata.n_channels} channels"
            )

        return AudioReader.read_file(
            filename, read_samples=frames, start_idx=start_idx, channel=channel
        )

    @staticmethod
    def read_file_metadata(filename: str) -> LoadedAudioData.Metadata:
        with soundfile.SoundFile(filename) as f:
            return LoadedAudioData.Metadata(
                sampling_rate=f.samplerate,
                frames=f.frames,
                n_channels=f.channels,
                duration=f.frames / f.samplerate,
                offset=0,
            )


@dataclass
class LoadedImage:
    @dataclass
    class Metadata:
        format: Optional[str]
        size: tuple
        mode: str

    data: Image.Image
    metadata: Optional[LoadedImage.Metadata] = None


class PILImageReader(FileReader[LoadedImage]):
    """Read in an image file as a PIL Image"""

    @staticmethod
    def check_file(filename) -> None:
        try:
            Image.open(filename)
        except UnidentifiedImageError:
            raise FileInvalidError

    @staticmethod
    def read_file(filename) -> LoadedImage:
        im = Image.open(filename)
        return LoadedImage(
            data=im,
            metadata=LoadedImage.Metadata(format=im.format, size=im.size, mode=im.mode),
        )


def gather_files(
    paths: list[str],
    extension: str = "*",
    filter_with_readers: Optional[list[Type[FileReader]]] = None,
) -> list[str]:
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
            for _filename in glob.glob(
                os.path.join(filename, "*.{}".format(extension))
            ):
                if filter_with_readers is not None:
                    try:
                        for reader in filter_with_readers:
                            reader.check_file(_filename)
                    except FileInvalidError:
                        pass
                    else:
                        results.append(_filename)
                else:
                    results.append(_filename)

    return results
