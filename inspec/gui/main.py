"""Testing color maps and windows

TODO: toggle channel views
TODO: change redraw flag and time start info to be per file
TODO: visual indicator of time scale at bottom of each file
TODO: refactored view objects so we dont need to repeat BUFFER_CHARs everywhere
"""
import curses
import curses.panel
import curses.textpad
import os
import time

import click
import soundfile
import numpy as np

from inspec import const, var
from inspec.plugins.audio.spectrogram_view import CursesSpectrogramPlugin
from inspec.plugins.colormap import load_cmap, VALID_CMAPS

from .state import GlobalState, ViewStateLocal
from .utils import (
    annotate_window,
    create_pad,
    draw_instructions,
    prompt,
)


def main(stdscr, rows, cols, files, cmap="greys", jump_to_time=0.0):
    """Main application loop
    """
    curses.use_default_colors()
    stdscr.refresh()

    n_panels = len(files)
    G = GlobalState(rows, cols, files, load_cmap(cmap))

    padx = 0
    pady = 0

    def initialize_display(rows, cols):
        G.set_shape(rows, cols)
        maxy, maxx = stdscr.getmaxyx()
        pageline = curses.newwin(1, maxx - 1, maxy - 2, 0)
        logline = curses.newwin(1, maxx - 1, maxy - 1, 0)

        pad, coords, page_size = create_pad(
            curses.LINES - 2,
            curses.COLS,
            rows,
            cols,
            n_panels,
            padx=padx,
            pady=pady
        )

        old_time_starts = [v.time_start for v in G.view_states]
        G.view_states = []
        for i, (filename, coord) in enumerate(zip(G.filenames, coords)):
            window = pad.subwin(*coord)
            inset_window = pad.subwin(
                coord[0] - 2,
                coord[1] - 2,
                coord[2] + 1,
                coord[3] + 1
            )

            view_state = ViewStateLocal(
                G,
                window,
                CursesSpectrogramPlugin(inset_window),
                filename,
                i,
                time_start=old_time_starts[i] if len(old_time_starts) else 0.0
            )
            G.view_states.append(view_state)
            view_state.viewer.set_cmap(G.cmap)
            view_state.decorate()

        G.current_page = G.paginator.item_to_page(G.current_selection)

        return pad, coords, page_size, pageline, logline

    def update_page():
        """Have all panels in the visible screen refresh their plots"""
        maxy, maxx = stdscr.getmaxyx()
        pad.refresh(0, page_size * (G.current_page), pady, padx, maxy - 1 - pady, maxx - 1 - padx)

        for visible_idx in G.paginator.items_on_page(G.current_page):
            view_state = G.view_states[visible_idx]
            view_state.refresh_view()

        maxy, maxx = stdscr.getmaxyx()
        pad.refresh(0, page_size * (G.current_page), pady, padx, maxy - 1 - pady, maxx - 1 - padx)
        pagestr = "p{}/{}".format(G.current_page + 1, G.paginator.n_pages)
        pageline.addstr(0, pageline.getmaxyx()[1] - 1 - len(pagestr), pagestr, curses.A_BOLD)
        draw_instructions(logline)
        logline.refresh()
        pageline.refresh()

    def move(move_direction):
        changed, curr, prev = getattr(G, move_direction)()
        if changed:
            G.view_states[curr].decorate()
            G.view_states[prev].decorate()
            update_page()

    pad, coords, page_size, pageline, logline = initialize_display(rows, cols)

    # Jump to time if possible on the first
    for view_state in G.view_states:
        view_state.jump_to_time(jump_to_time)

    update_page()

    last_size = stdscr.getmaxyx()
    running = True
    while running:
        ch = stdscr.getch()
        if ch == ord("q"):
            running = False
            stdscr.clear()
        elif ch == curses.KEY_RESIZE:
            curr_size = stdscr.getmaxyx()
            if curr_size != last_size:
                # logger.debug("Debug: resizing terminal to {}".format(curr_size))
                curses.resizeterm(*curr_size)
                stdscr.clear()
                stdscr.refresh()
                pad, coords, page_size, pageline, logline = initialize_display(rows, cols)
                update_page()
                last_size = curr_size
        elif ch == curses.KEY_SLEFT or ch == ord("H"):
            G.current_view_state.time_left()
            update_page()
        elif ch == curses.KEY_SRIGHT or ch == ord("L"):
            G.current_view_state.time_right()
            update_page()
        elif ch == curses.KEY_LEFT or ch == ord("h"):
            move("left")
        elif ch == curses.KEY_RIGHT or ch == ord("l"):
            move("right")
        elif ch == curses.KEY_UP or ch == ord("k"):
            move("up")
        elif ch == curses.KEY_DOWN or ch == ord("j"):
            move("down")
        elif ch == ord("m"):
            resp = prompt(logline, "Choose colormap ['greys', 'viridis', 'plasma', ...]: ")
            resp = resp.strip()
            if resp in VALID_CMAPS:
                cmap = load_cmap(resp)

            for vs in G.view_states:
                vs.viewer.set_cmap(cmap)
                vs.out_of_date = True
            update_page()
        elif ch == ord("s"):
            resp = prompt(logline, "Set timescale (max {}, blank for default): ".format(var.MAX_TIMESCALE))
            if resp is None or not resp.strip():
                G.time_scale = None
            else:
                try:
                    scale = float(resp)
                except ValueError:
                    pass
                else:
                    if var.MIN_TIMESCALE < scale <= var.MAX_TIMESCALE:
                        G.time_scale = scale
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("t"):
            resp = prompt(logline, "Jump to time: ")
            if resp is None or not resp.strip():
                pass
            else:
                try:
                    time_start = float(resp)
                except ValueError:
                    pass
                else:
                    if 0 < time_start:
                        G.current_view_state.jump_to_time(time_start)
                        G.current_view_state.refresh_view(force=True)
            update_page()
        elif ch == ord("-"):
            if G.time_scale is not None:
                G.time_scale = min(var.MAX_TIMESCALE, G.time_scale * 2)
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("+"):
            if G.time_scale is not None:
                G.time_scale = max(var.MIN_TIMESCALE, G.time_scale / 2)
            else:
                G.time_scale = G.current_view_state.duration / 2
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("r"):
            resp = prompt(stdscr, "Set rows [0-9]: ")
            if resp is not None:
                try:
                    rows = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= rows <= 9:
                        stdscr.clear()
                        stdscr.refresh()
                        pad, coords, page_size, pageline, logline = initialize_display(rows, G.cols)
                        update_page()
        elif ch == ord("c"):
            resp = prompt(stdscr, "Set cols [0-9]: ")
            if resp is not None:
                try:
                    cols = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= cols <= 9:
                        stdscr.clear()
                        stdscr.refresh()
                        pad, coords, page_size, pageline, logline = initialize_display(G.rows, cols)
                        update_page()
