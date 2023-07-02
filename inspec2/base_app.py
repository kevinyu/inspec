"""
Core curses functionality

We have a state machine that operates between two states:

- RunningState: the app is running
- EndedState: the app is closing

The main event loop runs while in the RunningState. On each loop, it will
- Check for input
- Check for new data
- Render the current state (and refresh display if needed)
- Sleep for a bit (refresh rate)
"""

from __future__ import annotations
import asyncio
import curses
import math
from typing import Callable, Generic, Literal, Optional, Type, TypeVar, Union

import numpy as np
from pydantic import BaseModel


T = TypeVar("T")


class MaybeDirty(Generic[T], BaseModel):
    """
    Core rendering type that can hold data, and flag if it has changed.
    """
    value: Optional[T]
    dirty: bool = False

    def set(self, value: Optional[T]) -> None:
        if self.value != value:
            self.dirty = True
            self.value = value

    def clear(self) -> None:
        self.set(None)

    def __repr__(self) -> str:
        return repr(f"MaybeDirty({self.value}")


class Padding(BaseModel):
    x: int
    y: int


class Dimensions(BaseModel):
    width: int
    height: int


class WindowPosition(BaseModel):
    """Represent the position of a panel in the app"""
    nlines: int
    ncols: int
    y: int
    x: int

    def to_window(self) -> curses.window:
        return curses.newwin(self.nlines, self.ncols, self.y, self.x)

    def to_subwindow(self, parent: curses.window) -> curses.window:
        return parent.subwin(self.nlines, self.ncols, self.y, self.x)


class CursesAppConfig(BaseModel):
    class DebugSettings(BaseModel):
        pass

    # -- Display settings --
    padding: Padding  # Padding for top-level panels
    grid_padding: Padding  # Padding for grid panels
    status_height: int = 1
    toast_height: int = 2

    # -- App settings --
    poll_interval: float = 0.01
    refresh_rate: float = 40

    # -- Debug settings --
    debug_settings: DebugSettings = DebugSettings()


class AppWindowPositions(BaseModel):
    """The positions of the panels that make up an app"""
    main: WindowPosition
    status: WindowPosition
    toast: WindowPosition


class WindowHistory(BaseModel):
    """Records a history window information to detect changes"""
    maxyx: tuple[int, int]


class GridLayout(BaseModel):
    rows: int
    cols: int


class MainPad(BaseModel):
    parent: curses.window
    children: list[curses.window]
    container_size: Dimensions
    grid_layout: GridLayout = GridLayout(rows=1, cols=1)

    class Config:
        arbitrary_types_allowed=True

    def panel_dimensions(self) -> Dimensions:
        return Dimensions(
            width=self.container_size.width // self.grid_layout.cols,
            height=self.container_size.height // self.grid_layout.rows,
        )


class InitializedApp(BaseModel):
    """
    +-----------------+-----------------+
    |+---------------------------------+|
    ||                                 ||
    ||              Main               || Stdscr
    ||                                 ||
    |+---------------------------------+|
    +-----------------+-----------------+
    |                                   | Status
    +-----------------+-----------------+
    |                                   | Toast
    +-----------------+-----------------+
    """
    stdscr: curses.window
    main_panel: MainPad
    status_panel: curses.window
    toast_panel: curses.window
    config: CursesAppConfig

    window_history: WindowHistory

    class Config:
        arbitrary_types_allowed=True


def get_panel_positions(stdscr: curses.window, config: CursesAppConfig) -> AppWindowPositions:
    screen_height, screen_width = stdscr.getmaxyx()

    # Enforce even number of columns. its easier this way. trust me.
    if screen_width % 2:
        screen_width -= 1

    main_area = WindowPosition(
        nlines=(
            screen_height
            - (2 * config.padding.y)
            - config.status_height
            - config.status_height
        ),
        ncols=screen_width - (2 * config.padding.x),
        y=config.padding.y,
        x=config.padding.x,
    )

    status_area = WindowPosition(
        nlines=config.status_height,
        ncols=screen_width - (2 * config.padding.x),
        y=main_area.nlines + main_area.y,
        x=config.padding.x,
    )

    toast_area = WindowPosition(
        nlines=config.toast_height,
        ncols=screen_width - (2 * config.padding.x),
        y=status_area.nlines + status_area.y,
        x=config.padding.x,
    )

    return AppWindowPositions(main=main_area, status=status_area, toast=toast_area)


def construct_screen() -> curses.window:
    """
    Call once to initialize the screen.
    """
    stdscr = curses.initscr()
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    stdscr.refresh()
    return stdscr


def apply_grid(
    pad: MainPad,
    n: int,
    grid_padding: Padding,
) -> None:
    """Apply a grid to window, assuming uniform size"""
    n_pages = int(math.ceil(n / (pad.grid_layout.rows * pad.grid_layout.cols)))
    panel_size = pad.panel_dimensions()
    # TODO (kevin): determine if we need to round up to the nearest page
    pad_width = panel_size.width * (n_pages + pad.grid_layout.cols)  # Infinitely horizontal
    pad_height = panel_size.height * pad.grid_layout.rows

    pad.parent = curses.newpad(pad_height, pad_width)
    pad.children = [
        WindowPosition(
            nlines=panel_size.height - 2 * grid_padding.y,
            ncols=panel_size.width - 2 * grid_padding.x,
            y=panel_size.height * row + grid_padding.y,
            x=panel_size.width * col + grid_padding.x,
        ).to_subwindow(pad.parent)
        for row in range(pad.grid_layout.rows)
        for col in range(pad.grid_layout.cols)
    ]


def reset_display(app: InitializedApp) -> None:
    """Clear and reset all displays in the app."""
    curr_size = app.stdscr.getmaxyx()
    curses.resizeterm(*curr_size)
    app.window_history.maxyx = curr_size
    app.stdscr.clear()
    app.stdscr.refresh()

    panel_positions = get_panel_positions(app.stdscr, app.config)
    app.toast_panel = panel_positions.toast.to_window()
    app.status_panel = panel_positions.status.to_window()
    apply_grid(app.main_panel, len(app.main_panel.children), app.config.grid_padding)

    # TODO (kevin): not sure if these are necessary.
    # app.main_panel.parent.clear()
    # app.main_panel.windows = []


def initialize_app(config: CursesAppConfig, stdscr: curses.window) -> InitializedApp:
    panel_positions = get_panel_positions(stdscr, config)
    toast_window = panel_positions.toast.to_window()
    status_window = panel_positions.status.to_window()
    main_window = curses.newpad(panel_positions.main.nlines, panel_positions.main.ncols)

    return InitializedApp(
        stdscr=stdscr,
        main_panel=MainPad(
            parent=main_window,
            children=[],
            container_size=Dimensions(
                width=panel_positions.main.ncols,
                height=panel_positions.main.nlines,
            ),
        ),
        status_panel=status_window,
        toast_panel=toast_window,
        config=config,
        window_history=WindowHistory(maxyx=stdscr.getmaxyx()),
    )


from asyncio import Queue


class States:
    """Representing an App State. Pretty simple for now."""
    class RunningState(BaseModel):
        """Subclass this for particular implementations"""
        async def render(self, app: InitializedApp) -> None:
            pass

    class EndedState(BaseModel):
        pass

    State = Union[RunningState, EndedState]


RunningStateType = TypeVar("RunningStateType", bound=States.RunningState)
HandleKeyFn = Callable[[InitializedApp, RunningStateType, int], States.State]


class AppRunner:
    class Event(BaseModel):
        pass

    class KeyPress(Event):
        key: int

    class RefreshRequest(Event):
        pass

    def __init__(self, app: InitializedApp):
        self._state: Optional[States.State] = None
        self.app = app
        self.queue = Queue()

    def set_grid(self, grid_layout: GridLayout) -> None:
        self.app.main_panel.grid_layout = grid_layout
        reset_display(self.app)  # TODO (kevin): maybe this should send an event to the main loop that says, i need a reset

    def close(self):
        curses.endwin()

    async def listen_for_keys(self, app: InitializedApp) -> None:
        while not isinstance(self._state, States.EndedState):
            ch: int = self.app.stdscr.getch()
            assert ch is not None
            if ch == curses.KEY_RESIZE:
                await self.queue.put(self.RefreshRequest())
            elif ch != -1:
                await self.queue.put(self.KeyPress(key=ch))

            await asyncio.sleep(app.config.poll_interval)

    async def main_loop(
        self,
        app: InitializedApp,
        handle_key: HandleKeyFn
    ) -> None:
        refresh_interval = 1 / app.config.refresh_rate
        try:
            event: Optional[AppRunner.Event] = None
            while isinstance(self._state, States.RunningState):
                try:
                    event = self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                else:
                    if isinstance(event, self.RefreshRequest):
                        reset_display(app)
                    elif isinstance(event, self.KeyPress):
                        self._state = handle_key(app, self._state, event.key)
                    else:
                        raise ValueError(f"Unknown event type: {event}")

                if isinstance(self._state, States.RunningState):
                    await self._state.render(app)
                    await asyncio.sleep(refresh_interval)
        finally:
            self.close()

    async def run(
        self,
        app: InitializedApp,
        initial_state: States.State,
        handle_key: HandleKeyFn
    ) -> None:
        """Runs the main event loop for the app"""
        self._state = initial_state
        asyncio.create_task(self.main_loop(app, handle_key))
        await self.listen_for_keys(app)




if __name__ == "__main__":
    def handle_key(app: InitializedApp, state: States.RunningState, ch: int) -> States.State:
        if ch == ord("q"):
            return States.EndedState()
        else:
            return state

    runner = AppRunner(
        initialize_app(
            CursesAppConfig(
                padding=Padding(x=2, y=2),
                grid_padding=Padding(x=1, y=1),
                status_height=1,
                toast_height=2,
                poll_interval=0.01,
                refresh_rate=40,
            ),
            construct_screen(),
        )
    )
    asyncio.run(runner.run(runner.app, States.RunningState(), handle_key))
