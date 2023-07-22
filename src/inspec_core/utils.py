from inspec_core.base_view import BaseWidthHeight, Size


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
