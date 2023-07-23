from __future__ import annotations

import abc
from typing import AsyncIterator, Generic, TypeVar

from numpy.typing import NDArray
from pydantic import BaseModel

from .size import Size

T = TypeVar("T", covariant=True)


class View(BaseModel):
    pass


ViewT = TypeVar("ViewT", bound=View)


class FileReader(Generic[T, ViewT], abc.ABC):
    @abc.abstractmethod
    def get_view(self, view: ViewT, size: Size.Size) -> NDArray[T]:  # type: ignore
        """
        Returns an array (height/rows, width/cols) to be displayed
        """
        raise NotImplementedError


class FileStreamer(Generic[T, ViewT], abc.ABC):
    @abc.abstractmethod
    async def stream_view(self, view: ViewT, size: Size.Size) -> AsyncIterator[NDArray[T]]:  # type: ignore
        """
        Streams arrays of (height/rows, width/cols) to be displayed
        """
        raise NotImplementedError


__all__ = [
    "Size",
    "View",
    "ViewT",
    "FileReader",
    "FileStreamer",
]
