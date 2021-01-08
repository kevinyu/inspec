import asyncio
import curses
import curses.textpad
import time
from collections import namedtuple


PanelCoord = namedtuple("PanelCoord", [
    "nlines",
    "ncols",
    "y",
    "x"
])


class DataView(object):
    """Manage view state of a single panel in a gui application
    """
    def __init__(self, app, data, idx):
        self.app = app
        self.data = data
        self.idx = idx
        self.validate_data()

    def validate_data(self):
        return


class InspecCursesApp(object):

    def __init__(self, pady=0, padx=0, poll_interval=0.01, refresh_rate=40, debug=False):
        """Base class for async curses application
        """
        self.stdscr = None
        self.main_window = None
        self.debug_window = None
        self._poll_interval = poll_interval
        self._refresh_interval = 1 / refresh_rate
        self._padx = padx
        self._pady = pady
        self.debug_mode = debug
        self._debug_height = 2
        self._status_height = 1

    @property
    def panel_coords(self):
        """Helper to pre-define areas for certain panels

        Does not actually initialize any curses windows, but provides helpful access
        when you're in the heat of the moment.
        """
        screen_height, screen_width = self.stdscr.getmaxyx()

        # Enforce even number of columns. its easier this way. trust me.
        if screen_width % 2:
            screen_width -= 1

        if self.debug_mode:
            main_area = PanelCoord(
                screen_height - 2 * self._pady - self._debug_height - self._status_height,
                screen_width - 2 * self._padx,
                self._pady,
                self._padx
            )
            status_area = PanelCoord(
                self._status_height,
                screen_width - 2 * self._padx,
                main_area.nlines + main_area.y,
                self._padx
            )
            debug_area = PanelCoord(
                self._debug_height,
                screen_width,
                status_area.nlines + status_area.y,
                0
            )
        else:
            main_area = PanelCoord(
                screen_height - 2 * self._pady - self._debug_height - self._status_height,
                screen_width - 2 * self._padx,
                self._pady,
                self._padx
            )
            status_area = PanelCoord(
                self._status_height,
                screen_width - 2 * self._padx,
                main_area.nlines + main_area.y,
                self._padx
            )
            debug_area = None

        return {
            "main": main_area,
            "status": status_area,
            "debug": debug_area
        }

    async def initialize_display(self):
        panel_coords = self.panel_coords

        if self.debug_mode:
            self.debug_window = curses.newwin(
                panel_coords["debug"].nlines,
                panel_coords["debug"].ncols,
                panel_coords["debug"].y,
                panel_coords["debug"].x
            )
        else:
            self.debug_window = None

        self.status_window = curses.newwin(
            panel_coords["status"].nlines,
            panel_coords["status"].ncols,
            panel_coords["status"].y,
            panel_coords["status"].x
        )

    def debug(self, msg, timeout=1.0):
        msg = "DEBUG: {}".format(msg)
        if self.debug_mode and self.debug_window is not None:
            debug_window_height, debug_window_width = self.debug_window.getmaxyx()
            self.debug_window.addstr(0, 0, msg[:debug_window_width])
            self.debug_window.addstr(1, 0, msg[debug_window_width:2*debug_window_width])
            self.debug_window.refresh()

        if timeout:
            event_loop = asyncio.get_event_loop()
            event_loop.call_later(timeout, self.erase_debug)

    def erase_debug(self):
        if self.debug_window:
            self.debug_window.clear()

    async def refresh(self):
        """Called each 1/refresh_rate, for updating the display"""
        if self.debug_window:
            self.debug_window.refresh()

    def close(self):
        """End the main loop"""
        self._running = False
        self.cleanup()

    def cleanup(self):
        """Called after loop stop"""
        pass

    def prompt(self, msg, type_):
        resp = ""
        status_coord = self.panel_coords["status"]

        self.stdscr.addstr(
            status_coord.y,
            status_coord.x,
            msg + (status_coord.ncols - 2 * status_coord.x - len(msg)) * " "
        )
        self.stdscr.refresh()

        resp_window = self.stdscr.subwin(
            1,
            status_coord.ncols - len(msg) - 2,
            status_coord.y,
            1 + len(msg),
        )

        resp_input = curses.textpad.Textbox(resp_window)
        try:
            resp_input.edit()
        except KeyboardInterrupt:
            return
        else:
            resp = resp_input.gather()
        finally:
            del resp_window

        self.stdscr.addstr(
            status_coord.y,
            status_coord.x,
            " " * (status_coord.ncols - 1)
        )
        self.stdscr.refresh()

        if not str(resp).strip():
            return None

        try:
            return type_(str(resp).strip())
        except ValueError:
            return None

    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == ord("q"):
            self.close()
        else:
            pass

    async def listen_to_key_inputs(self):
        while self._running:
            ch = await self.get_key_input()
            await self.handle_key(ch)

    async def get_key_input(self):
        if self.stdscr is None:
            raise Exception("stdscr is has not been initialized for some reason")

        while True:
            ch = self.stdscr.getch()
            if ch == -1 or ch is None:
                await asyncio.sleep(self._poll_interval)
            else:
                return ch

    async def run(self):
        while self._running:
            _t = time.time()
            await self.refresh()
            _dt = time.time() - _t
            if self._refresh_interval > _dt:
                await asyncio.sleep(self._refresh_interval - _dt)
            else:
                await asyncio.sleep(0)
                self.debug("\nFramerate lower than defined refresh {:.1f}: {:.2f}".format(1/self._refresh_interval, 1/_dt))

    def start_tasks(self):
        asyncio.create_task(self.run())

    def pre_display(self):
        pass

    def post_display(self):
        pass

    async def main(self, stdscr):
        """Initialize display and then run a refresh loop and keyboard listener simultaneously
        """
        self._running = True
        self._app_started_at = time.time()

        self.stdscr = stdscr
        self.stdscr.nodelay(1)
        curses.use_default_colors()
        self.stdscr.refresh()

        self.pre_display()
        await self.initialize_display()
        self.post_display()
        self.start_tasks()

        # Does it make sense for the lisnen to key inputs to be the main thing keeping the app running?
        await self.listen_to_key_inputs()
