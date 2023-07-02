import asyncio
import curses
from typing import TypeVar
from inspec2.base_app import (
    States,
    MaybeDirty,
    InitializedApp,
    CursesAppConfig,
    Padding,
    construct_screen,
    initialize_app,
    AppRunner,
)

T = TypeVar("T")


class SimpleRunningState(States.RunningState):
    current_toast: MaybeDirty[str] = MaybeDirty(value=None, dirty=False)
    status_msg: MaybeDirty[str] = MaybeDirty(value=None, dirty=False)

    """Simple app state that just updates toasts"""
    async def render(self, app: InitializedApp) -> None:
        if self.current_toast.dirty:
            if self.current_toast.value is not None:
                _, toast_window_width = app.toast_panel.getmaxyx()
                app.toast_panel.addstr(0, 0, self.current_toast.value[:toast_window_width])
                app.toast_panel.addstr(1, 0, self.current_toast.value[toast_window_width: 2 * toast_window_width])
            elif self.current_toast.dirty:
                app.toast_panel.clear()
            app.toast_panel.refresh()

        if self.status_msg.dirty:
            if self.status_msg.value is not None:
                _, status_window_width = app.status_panel.getmaxyx()
                app.status_panel.addstr(0, 0, self.status_msg.value[:status_window_width])
            elif self.status_msg.dirty:
                app.status_panel.clear()
            app.status_panel.refresh()

        for window in app.main_panel.children:
            window.border(1, 1, 1, 1)
            window.refresh()


def set_for(obj: MaybeDirty[T], value: T, timeout: float) -> None:
    obj.set(value)
    event_loop = asyncio.get_event_loop()
    event_loop.call_later(timeout, lambda: obj.set(None))


def handle_key(app: InitializedApp, state: SimpleRunningState, ch: int) -> States.State:
    if ch == ord("q"):
        return States.EndedState()
    else:
        set_for(state.current_toast, f"DEBUG: pressed {ch}", timeout=1.0)
        return state


async def main() -> None:
    state = SimpleRunningState()
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
    state.status_msg.set("Hit q to quit")
    set_for(state.current_toast, "Hello world!", timeout=1.0)
    await runner.run(runner.app, state, handle_key)


if __name__ == "__main__":
    asyncio.run(main())