from dataclasses import dataclass


@dataclass
class Paginator:
    rows: int
    cols: int
    total: int

    @property
    def n_pages(self) -> int:
        return 1 + (self.total - 1) // (self.rows * self.cols)

    @property
    def items_per_page(self) -> int:
        return self.rows * self.cols

    def items_on_page(self, page_idx: int) -> list[int]:
        if page_idx < 0:
            raise ValueError("Page < 0 out of range")
        elif page_idx > self.n_pages - 1:
            raise ValueError("Page > {} out of range".format(self.n_pages - 1))
        return list(
            range(
                page_idx * self.items_per_page,
                min((page_idx + 1) * self.items_per_page, self.total),
            )
        )

    def item_to_page(self, item_idx: int) -> int:
        return item_idx // (self.rows * self.cols)
