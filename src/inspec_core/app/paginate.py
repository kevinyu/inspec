"""
Stateless pagination utility functions
"""
import math
from typing import Any

import pydantic


class Position(pydantic.BaseModel):
    page: int
    abs_idx: int
    rel_idx: int


class GridPaginator(pydantic.BaseModel):
    """
    Represent page numbers, absolute position, and relative position in a paginated grid

     page 0        page 1
    ┌────┬────┐  ┌────┬────┐
    │ 0 0│ 1 1│  │ 4 0│ 5 1│
    ├────┼────┤  ├────┼────┤
    │ 2 2│ 3 3│  │ 6 2│ 7 3│
    └────┴────┘  └────┴────┘

    In these examples

     page x
    ┌────┐
    │ y z│
    └────┘

    x is the page number
    y is the absolute position
    z is the relative position

    Generally, given the page size (rows * cols), you can make these transformations:

    [page]    x = y // (rows * cols)
    [abs_idx] y = x * (rows * cols) + z
    [rel_idx] z = y % (rows * cols)

    These tranforms are represented by the following methods:

    locate_abs(abs_idx) -> Position(page, abs_idx, rel_idx, row, col)
    locate_rel(page, rel_idx) -> Position(page, abs_idx, rel_idx, row, col)
    """

    rows: int
    cols: int

    def model_post_init(self, __context: Any) -> None:
        assert self.rows > 0
        assert self.cols > 0

    @property
    def page_size(self) -> int:
        return self.rows * self.cols

    def n_pages(self, n_items: int) -> int:
        return max(1, math.ceil(n_items / self.page_size))

    def locate_abs(self, abs_idx: int) -> Position:
        page = abs_idx // self.page_size
        index_in_page = abs_idx % self.page_size
        return Position(page=page, abs_idx=abs_idx, rel_idx=index_in_page)

    def locate_rel(self, page: int, rel_idx: int) -> Position:
        abs_idx = page * self.page_size + rel_idx
        return Position(page=page, abs_idx=abs_idx, rel_idx=rel_idx)

    def page_slice(self, page_index: int) -> slice:
        return slice(page_index * self.page_size, (page_index + 1) * self.page_size)
