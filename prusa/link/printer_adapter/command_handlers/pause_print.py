import logging

from prusa.connect.printer.const import State
from prusa.link.printer_adapter.command_handlers.try_until_state import \
    TryUntilState

log = logging.getLogger(__name__)


class PausePrint(TryUntilState):
    command_name = "pause print"

    def _run_command(self):
        if self.state_manager.get_state() != State.PRINTING:
            self.failed("Cannot pause when not printing.")

        if self.file_printer.printing:
            self.file_printer.pause()

        self._try_until_state(gcode="M601", desired_state=State.PAUSED)
