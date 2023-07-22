from typing import Any, Optional
import pydantic


class Event(pydantic.BaseModel):
    pass


class QuitEvent(Event):
    pass


class NextPage(Event):
    pass


class PrevPage(Event):
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


class Back(Event):
    pass


class KeyPress(Event):
    key: str


class ShowHelp(Event):
    pass


class CloseHelp(Event):
    passthru_event: Optional[Event] = None
