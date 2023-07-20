"""
Stateless pagination utility functions
"""
import enum
import math
from typing import Any

import pydantic


class Position(pydantic.BaseModel):
    page: int
    row: int
    col: int


class GridPaginator(pydantic.BaseModel):
    class Direction(str, enum.Enum):
        RowMajor = "row_major"
        ColumnMajor = "column_major"

    rows: int
    cols: int
    direction: Direction = Direction.RowMajor

    def model_post_init(self, __context: Any) -> None:
        assert self.rows > 0
        assert self.cols > 0

    @property
    def page_size(self) -> int:
        return self.rows * self.cols

    def n_pages(self, n_items: int) -> int:
        return max(1, math.ceil(n_items / self.page_size))

    def locate(self, index: int) -> Position:
        page = index // self.page_size
        index_in_page = index % self.page_size
        if self.direction is self.Direction.RowMajor:
            row = index_in_page // self.cols
            col = index_in_page % self.cols
        elif self.direction is self.Direction.ColumnMajor:
            row = index_in_page % self.rows
            col = index_in_page // self.rows
        else:
            raise ValueError(f"Unknown direction {self.direction}")
        return Position(page=page, row=row, col=col)

    def invert(self, position: Position) -> int:
        if self.direction is self.Direction.RowMajor:
            index = position.row * self.cols + position.col
        elif self.direction is self.Direction.ColumnMajor:
            index = position.col * self.rows + position.row
        else:
            raise ValueError(f"Unknown direction {self.direction}")
        return position.page * self.page_size + index

    def page_slice(self, page_index: int) -> slice:
        return slice(page_index * self.page_size, (page_index + 1) * self.page_size)
