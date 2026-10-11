"""Hardware feedback, isolated from application logic.

Events: boot, quest_started, quest_completed, new_activity, game_running, game_finished.
"""
import logging
import shlex
import subprocess
from typing import Protocol

log = logging.getLogger("commonground.hardware")


class Display(Protocol):
    def show(self, event: str) -> None: ...


class NullDisplay:
    """Used when no hardware is present (development machine, tests)."""

    def __init__(self):
        self.events: list[str] = []

    def show(self, event: str) -> None:
        self.events.append(event)
        self.events = self.events[-50:]


class CommandDisplay(NullDisplay):
    """Runs a user-supplied command (e.g. a script that talks to the UNO Q MCU / LED matrix)."""

    def __init__(self, command: str):
        super().__init__()
        self.command = shlex.split(command)

    def show(self, event: str) -> None:
        super().show(event)
        try:
            subprocess.Popen(self.command + [event], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # missing hardware must never break the app
            log.warning("LED command failed: %s", exc)


def make_display(command: str) -> Display:
    return CommandDisplay(command) if command else NullDisplay()
