from __future__ import annotations

from typing import Any, Generic, Optional, Type, TypeVar

import pydantic
from typing_extensions import Self

from inspec_core.audio_view import TimeRange

T = TypeVar("T")


class Event(pydantic.BaseModel):
    def __str__(self) -> str:
        return f"{self.__class__.__name__}"


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


class NextFrame(Event):
    pass


class PrevFrame(Event):
    pass


class UserInput(Generic[T], Event):
    value: T

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    @classmethod
    def from_str(cls: Type[Self], value: str) -> Self:
        raise NotImplementedError


class JumpToFrame(UserInput[int]):
    @classmethod
    def from_str(cls, value: str) -> JumpToFrame:
        return cls(value=int(value))


class SetCols(UserInput[int]):
    @classmethod
    def from_str(cls, value: str) -> SetCols:
        return cls(value=int(value))


class SetRows(UserInput[int]):
    @classmethod
    def from_str(cls, value: str) -> SetRows:
        return cls(value=int(value))


class SetTimeRange(UserInput[TimeRange]):
    @classmethod
    def from_str(cls, value: str) -> SetTimeRange:
        values = value.split("-")
        if len(values) != 2:
            raise ValueError(f"Invalid time range {value}")
        try:
            t0 = float(values[0])
        except ValueError:
            t0 = None
        try:
            t1 = float(values[1])
        except ValueError:
            t1 = None
        return cls(value=TimeRange(start=t0, end=t1))


class RequestInput(Event):
    kind: Type[SetRows] | Type[SetCols] | Type[SetTimeRange] | Type[JumpToFrame]

    def __str__(self) -> str:
        return f"Input({str(self.kind)})"
