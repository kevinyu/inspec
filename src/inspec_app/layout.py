"""
Utils for computing a grid layout.
"""

from __future__ import annotations

import curses


def grid(
    window: curses.window,
    rows: int,
    cols: int,
    pad_rows: int = 0,
    pad_cols: int = 0,
) -> list[curses.window]:
    max_rows, max_cols = window.getmaxyx()
    if rows > max_rows:
        raise ValueError(f"rows {rows} > max_rows {max_rows}")
    if cols > max_cols:
        raise ValueError(f"cols {cols} > max_cols {max_cols}")

    usable_rows = max_rows - pad_rows
    usable_cols = max_cols - pad_cols

    row_height = usable_rows // rows
    col_width = usable_cols // cols

    return [
        window.derwin(
            nlines=row_height,
            ncols=col_width,
            begin_y=row_height * row_idx,
            begin_x=col_width * col_idx,
        )
        for row_idx in range(rows)
        for col_idx in range(cols)
    ]
