class Paginator(object):
    def __init__(self, rows, cols, total):
        self.rows = rows
        self.cols = cols
        self.total = total

    @property
    def n_pages(self):
        return 1 + (self.total - 1) // (self.rows * self.cols)

    @property
    def n_visible(self):
        return self.rows * self.cols

    def items_on_page(self, page_idx):
        if page_idx < 0:
            raise ValueError("Page < 0 out of range")
        elif page_idx > self.n_pages - 1:
            raise ValueError("Page > {} out of range".format(self.n_pages - 1))
        return list(range(
            page_idx * self.n_visible,
            min((page_idx + 1) * self.n_visible, self.total)
        ))

    def item_to_page(self, item_idx):
        return item_idx // (self.rows * self.cols)
