from inspec_app.paginate import GridPaginator, Position


def test_grid_paginator():
    paginator = GridPaginator(rows=2, cols=3)

    assert [
        paginator.n_pages(i)
        for i in range(15)
    ] == [0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3]


def test_grid_paginator_locate():
    paginator = GridPaginator(rows=1, cols=1)

    assert paginator.locate(5) == Position(page=5, row=0, col=0)

    paginator = GridPaginator(rows=2, cols=2, direction=GridPaginator.Direction.ColumnMajor)
    expected_mapping: dict[int, Position] = {
        0: Position(page=0, row=0, col=0),
        1: Position(page=0, row=1, col=0),
        2: Position(page=0, row=0, col=1),
        3: Position(page=0, row=1, col=1),
        4: Position(page=1, row=0, col=0),
        5: Position(page=1, row=1, col=0),
    }
    for i, expected in expected_mapping.items():
        assert paginator.locate(i) == expected
        assert paginator.invert(expected) == i

    paginator = GridPaginator(rows=2, cols=2, direction=GridPaginator.Direction.RowMajor)
    expected_mapping: dict[int, Position] = {
        0: Position(page=0, row=0, col=0),
        1: Position(page=0, row=0, col=1),
        2: Position(page=0, row=1, col=0),
        3: Position(page=0, row=1, col=1),
        4: Position(page=1, row=0, col=0),
        5: Position(page=1, row=0, col=1),
    }
    for i, expected in expected_mapping.items():
        assert paginator.locate(i) == expected
        assert paginator.invert(expected) == i
