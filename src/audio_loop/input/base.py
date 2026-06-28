"""Input provider interface used by physical and future remote controls."""

from typing import Protocol


class InputHandler(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...
