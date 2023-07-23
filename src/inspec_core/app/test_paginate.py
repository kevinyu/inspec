from .paginate import GridPaginator, Position


def test_grid_paginator():
    paginator = GridPaginator(rows=2, cols=3)

    assert [paginator.n_pages(i) for i in range(15)] == [
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
        2,
        2,
        3,
        3,
    ]


def test_grid_paginator_locate():
    paginator = GridPaginator(rows=1, cols=1)

    assert paginator.locate_abs(5) == Position(page=5, abs_idx=5, rel_idx=0)

    paginator = GridPaginator(rows=2, cols=2)
    expect_list: list[Position] = [
        Position(page=0, abs_idx=0, rel_idx=0),
        Position(page=0, abs_idx=1, rel_idx=1),
        Position(page=0, abs_idx=2, rel_idx=2),
        Position(page=0, abs_idx=3, rel_idx=3),
        Position(page=1, abs_idx=4, rel_idx=0),
        Position(page=1, abs_idx=5, rel_idx=1),
    ]
    for expect in expect_list:
        assert paginator.locate_abs(expect.abs_idx) == expect
        assert paginator.locate_rel(expect.page, expect.rel_idx) == expect
