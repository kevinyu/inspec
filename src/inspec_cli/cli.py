import sys


# Set Console Mode so that ANSI codes will work
# TODO: does this go here?
if sys.platform == "win32":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

