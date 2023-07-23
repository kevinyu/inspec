from __future__ import annotations

import os
from typing import Union

from pydantic import BaseModel
from typing_extensions import Self

from inspec_core.render.types import CharShape


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


class Shape(BaseWidthHeight):
    pass


def preserve_aspect_ratio(
    size: Size.Size, *, original_width: float, original_height: float
) -> Shape:
    ar = original_height / original_width
    if isinstance(size, Size.FixedSize):
        return Shape(width=size.width, height=size.height)
    elif isinstance(size, Size.FixedWidth):
        return Shape(width=size.width, height=int(ar * size.width))
    elif isinstance(size, Size.FixedHeight):
        return Shape(width=int(size.height / ar), height=size.height)
    elif isinstance(size, Size.MinSize):
        if ar > size.height / size.width:
            return Shape(width=size.width, height=int(ar * size.width))
        else:
            return Shape(width=int(size.height / ar), height=size.height)
    elif isinstance(size, Size.MaxSize):
        if ar < size.height / size.width:
            return Shape(width=size.width, height=int(ar * size.width))
        else:
            return Shape(width=int(size.height / ar), height=size.height)
    else:
        raise ValueError(f"Unknown size {size}")


__all__ = ["Size", "Shape", "preserve_aspect_ratio"]
