from __future__ import annotations

import abc
import os
from typing import AsyncIterator, Generic, Self, TypeVar, Union

from numpy.typing import NDArray
from pydantic import BaseModel
from render.types import CharShape

T = TypeVar("T", covariant=True)


class BaseWidthHeight(BaseModel):
    width: int
    height: int

    def __post_init__(self):
        assert self.width > 0
        assert self.height > 0

    @property
    def T(self) -> Self:
        return type(self)(width=self.height, height=self.width)

    @classmethod
    def fill_terminal(cls, shape: CharShape = CharShape.Full) -> Self:
        termsize = os.get_terminal_size()
        size = cls.fit_characters(termsize.lines, termsize.columns, shape=shape)
        size.height -= 1  # Shave off one for the terminal input line
        return size

    @classmethod
    def fit_characters(
        cls, rows: int, cols: int, shape: CharShape = CharShape.Full
    ) -> Self:
        if shape is CharShape.Full:
            return cls(width=cols, height=rows)
        elif shape is CharShape.Half:
            return cls(width=cols, height=rows * 2)
        elif shape is CharShape.Quarter:
            return cls(width=cols * 2, height=rows * 2)
        else:
            raise ValueError(f"Unknown shape {shape}")


class Size:
    class FixedSize(BaseWidthHeight):
        pass

    class FixedWidth(BaseModel):
        width: int

    class FixedHeight(BaseModel):
        height: int

    class MaxSize(BaseWidthHeight):
        pass

    class MinSize(BaseWidthHeight):
        pass

    Size = Union[FixedSize, FixedWidth, FixedHeight, MaxSize, MinSize]


class View(BaseModel):
    """
    Attributes
    ----------
    expect_size : Size
        The size to shape the output array. This corresponds to the width and height in units of
        terminal characters. So, to fill the entire terminal for CharShape.Half, you would want to
        pass in Size(width=cols, height=rows * 2 - 1).
    """

    expect_size: Size.Size


ViewT = TypeVar("ViewT", bound=View)


class FileReader(Generic[T, ViewT], abc.ABC):
    @abc.abstractmethod
    def get_view(self, view: ViewT) -> NDArray[T]:  # type: ignore
        raise NotImplementedError


class FileStreamer(Generic[T, ViewT], abc.ABC):
    @abc.abstractmethod
    async def stream_view(self, view: ViewT) -> AsyncIterator[NDArray[T]]:  # type: ignore
        raise NotImplementedError


__all__ = [
    "Size",
    "View",
    "ViewT",
    "FileReader",
    "FileStreamer",
]
