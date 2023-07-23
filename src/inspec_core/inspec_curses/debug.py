import curses
import inspect

import ipdb  # type: ignore

from . import context


def breakpoint():
    if stdscr := context.current_stdscr():
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()
        ipdb.set_trace(frame=inspect.currentframe().f_back)  # type: ignore
    else:
        ipdb.set_trace()
