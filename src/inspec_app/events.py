from typing import Any
import pydantic


class Event(pydantic.BaseModel):
    pass


class QuitEvent(Event):
    pass


class NextPageEvent(Event):
    pass


class PrevPageEvent(Event):
    pass


class LogEvent(Event):
    msg: str

    def model_post_init(self, __context: Any) -> None:
        assert len(self.msg.split("\n")) == 1
        return super().model_post_init(__context)

class WindowResized(Event):
    pass


class Move:
    class Right(Event):
        pass

    class Left(Event):
        pass

    class Up(Event):
        pass

    class Down(Event):
        pass


class Select(Event):
    pass


class Undo(Event):
    pass


class KeyPress(Event):
    key: str
