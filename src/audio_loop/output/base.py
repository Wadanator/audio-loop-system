"""Output provider interface for active-layer indicators."""

from typing import Iterable, Protocol


class LedController(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def set_layer_active(self, instrument: int, active: bool) -> None:
        ...

    def set_all(self, active: bool, force: bool = False) -> None:
        ...

    def sync_from_active_layers(self, active_layers: Iterable[int]) -> None:
        ...
