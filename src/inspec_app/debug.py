import curses


def add_breakpoint(stdscr: curses.window):
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
    breakpoint()
