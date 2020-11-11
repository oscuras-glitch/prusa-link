import logging
from threading import Thread, Event
from typing import Type, Optional

from prusa_link.command import Command, ResponseCommand
from prusa_link.default_settings import get_settings
from prusa_link.file_printer import FilePrinter
from prusa_link.informers.state_manager import StateManager
from prusa_link.input_output.connect_api import ConnectAPI
from prusa_link.input_output.serial.serial import Serial
from prusa_link.input_output.serial.serial_queue import SerialQueue
from prusa_link.input_output.serial.serial_reader import SerialReader
from prusa_link.model import Model

LOG = get_settings().LOG
TIME = get_settings().TIME


log = logging.getLogger(__name__)
log.setLevel(LOG.COMMANDS)


class CommandRunner:

    def __init__(self, serial: Serial, serial_reader: SerialReader,
                 serial_queue: SerialQueue,
                 connect_api: ConnectAPI, state_manager: StateManager, 
                 file_printer: FilePrinter, model: Model):
        self.serial = serial
        self.serial_reader = serial_reader
        self.serial_queue = serial_queue
        self.state_manager = state_manager
        self.connect_api = connect_api
        self.file_printer = file_printer
        self.model = model

        self.running = True
        self.running_command: Optional[Command] = None
        self.new_command_event = Event()

        # Can't start a new thread for every command.
        # So let's recycle one in here
        self.command_thread = Thread(target=self.handle_commands,
                                     name="command_runner")
        self.command_thread.start()

    def handle_commands(self):
        while self.running:
            if self.new_command_event.wait(timeout=TIME.QUIT_INTERVAL):
                self.new_command_event.clear()
                try:
                    self.running_command.run_command()
                except:
                    # Shall never actually happen
                    log.exception("Command failed unexpectedly, "
                                  "captured to stay alive. Might be a BUG.")

    def run(self, command_class: Type[ResponseCommand], api_response):
        """
        Used to pass additional context (as a factory?) so the command
        itself can be quite light in arguments
        """
        command = command_class(api_response=api_response,
                                serial=self.serial,
                                serial_reader=self.serial_reader,
                                serial_queue=self.serial_queue,
                                connect_api=self.connect_api,
                                state_manager=self.state_manager,
                                file_printer=self.file_printer,
                                model=self.model)

        if self.running_command is not None:
            if self.running_command.command_id == command.command_id:
                log.warning("Tried to run already running command")
                command.accept()
            else:
                command.reject("Another command is running")
        else:
            command.accept()
            command.finished_signal.connect(self.command_finished)
            self.running_command = command
            self.new_command_event.set()

    def command_finished(self, sender):
        self.running_command = None

    def stop(self):
        if self.running_command is not None:
            self.running_command.stop()
        self.running = False
        self.command_thread.join()