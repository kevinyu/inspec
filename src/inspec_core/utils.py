from inspec_core.base_view import BaseWidthHeight, Size


class Shape(BaseWidthHeight):
    pass


def preserve_aspect_ratio(
    size: Size.Size, original_width: float, original_height: float
) -> Shape:
    ar = original_width / original_height
    if isinstance(size, Size.FixedSize):
        shape = (size.height, size.width)
    elif isinstance(size, Size.FixedWidth):
        shape = (size.width, int(ar * size.width))
    elif isinstance(size, Size.FixedHeight):
        shape = (int(ar * size.height), size.height)
    elif isinstance(size, Size.MinSize):
        if ar > size.height / size.width:
            shape = (size.width, int(ar * size.width))
        else:
            shape = (int(ar * size.height), size.height)
    elif isinstance(size, Size.MaxSize):
        if ar < size.height / size.width:
            shape = (size.width, int(ar * size.width))
        else:
            shape = (int(ar * size.height), size.height)
    else:
        raise ValueError(f"Unknown size {size}")

    return Shape(width=shape[1], height=shape[0])
