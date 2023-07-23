import curses


def setup_curses(stdscr: curses.window):
    stdscr.nodelay(True)
    curses.use_default_colors()
    stdscr.refresh()
