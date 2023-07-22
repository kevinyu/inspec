import curses
from typing import Optional
import pydantic

from inspec_app import events


class KeyHandler(pydantic.BaseModel):
    title: str
    mapping: dict[tuple[int, ...], tuple[events.Event, bool]]

    @staticmethod
    def _key_to_str(key: int) -> Optional[str]:
        if key in range(32, 127):
            return chr(key)

    @staticmethod
    def _keys_to_str(keys: tuple[int]) -> str:
        return "|".join([str(keyname) for key in keys if (keyname := KeyHandler._key_to_str(key))])

    def help(self) -> str:
        return "\n".join([
            f"[{KeyHandler._keys_to_str(keys)}]: {event.__class__.__name__}"
            for keys, (event, show_help) in self.mapping.items()
            if show_help
        ])

    def handle_unknown(self, ch: int) -> Optional[events.Event]:
        return events.LogEvent(msg=f"Unknown key {ch}")

    def handle_alphanumeric(self, ch: int) -> Optional[events.Event]:
        return self.handle_unknown(ch)

    def handle(self, ch: int) -> Optional[events.Event]:
        if ch == ord("?"):
            return events.ShowHelp()

        for keys, (event, _) in self.mapping.items():
            if ch in keys:
                return event

        if ch in range(32, 127):
            return self.handle_alphanumeric(ch)
        else:
            return self.handle_unknown(ch)


class InputHandler(KeyHandler):

    def handle_alphanumeric(self, ch: int) -> Optional[events.Event]:
        return events.KeyPress(key=chr(ch))


default_handler = KeyHandler(
    title="Main view",
    mapping={
        (ord("q"),): (events.QuitEvent(), True),
        (ord("l"),): (events.NextPageEvent(), True),
        (ord("h"),): (events.PrevPageEvent(), True),
        # Python intercepts the SIGWINCH signal and prevents curses from seeing KEY_RESIZE
        # so resizing the window is not supported.
        # (curses.KEY_RESIZE,): (events.WindowResized(), False),
        (curses.KEY_RIGHT,): (events.Move.Right(), True),
        (curses.KEY_LEFT,): (events.Move.Left(), True),
        (curses.KEY_UP,): (events.Move.Up(), True),
        (curses.KEY_DOWN,): (events.Move.Down(), True),
        (curses.KEY_ENTER, 10, ord("o")): (events.Select(), True),
    }
)


zoom_handler = KeyHandler(
    title="Zoomed view",
    mapping={
        (curses.KEY_RIGHT,): (events.Move.Right(), True),
        (curses.KEY_LEFT,): (events.Move.Left(), True),
        (curses.KEY_UP,): (events.Move.Up(), True),
        (curses.KEY_DOWN,): (events.Move.Down(), True),
        (curses.KEY_BACKSPACE, 27, ord("q"), curses.KEY_ENTER, 10): (events.Back(), True),
    }
)


help_handler = KeyHandler(
    title="Help view",
    mapping={
        (curses.KEY_BACKSPACE, 27, ord("q"), curses.KEY_ENTER, 10): (events.CloseHelp(), True),
    }
)
