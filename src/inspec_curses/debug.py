import curses
import inspect

import ipdb

from inspec_curses import context


def breakpoint():
    if stdscr := context.current_stdscr():
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()
        ipdb.set_trace(frame=inspect.currentframe().f_back.f_back)  # type: ignore
    else:
        ipdb.set_trace()
