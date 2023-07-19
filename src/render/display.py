from render.types import ColoredChar, ColoredCharArray, XTermColor


def _ansi_set_color_str(fg_color: XTermColor, bg_color: XTermColor) -> str:
    return f"\u001b[38;5;{fg_color.value}m\u001b[48;5;{bg_color.value}m"


def display(arr: ColoredCharArray, end: str = "\n") -> None:
    ansi_reset_str = "\u001b[0m"
    last = len(arr) - 1
    for i, row in enumerate(arr[::-1]):
        parts = []
        for char_with_color in row:
            char_with_color: ColoredChar
            parts.append(
                _ansi_set_color_str(char_with_color.color.fg, char_with_color.color.bg)
                + char_with_color.char
            )
        print("".join(parts) + ansi_reset_str, end="\n" if i != last else end)
