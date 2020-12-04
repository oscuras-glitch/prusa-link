import os
from os.path import expanduser

from pydantic import BaseModel

from prusa.link.printer_adapter.settings import Settings

HOME = expanduser("~")

instance = None


class IntervalSettings(BaseModel):

    # Intervals are in seconds
    TELEMETRY_INTERVAL = 1
    TELEMETRY_IDLE_INTERVAL = 0.25
    TELEMETRY_PRINTING_INTERVAL = 1
    SLOW_TELEMETRY = 10  # for values, that aren't that important
    IP_UPDATE_INTERVAL = 2
    QUIT_INTERVAL = 0.1
    SD_INTERVAL = 0.1
    SD_FILESCAN_INTERVAL = 30
    DIR_RESCAN_INTERVAL = 1
    STORAGE_INTERVAL = 15
    SHOW_IP_INTERVAL = 60
    PRINTER_BOOT_WAIT = 8
    SEND_INFO_RETRY = 5
    SERIAL_REOPEN_TIMEOUT = 10
    TEMP_TIMEOUT = 60
    FW_MESSAGE_TIMEOUT = 5
    STATE_CHANGE_TIMEOUT = 5


class LCDQueueSettings(BaseModel):
    LCD_QUEUE_SIZE = 30


class SerialQueueSettings(BaseModel):
    RX_SIZE = 128
    SERIAL_QUEUE_TIMEOUT = 25
    SERIAL_QUEUE_MONITOR_INTERVAL = 1
    HISTORY_LENGTH = 30


class IsPlannerFedSettings(BaseModel):

    QUEUE_SIZE = 10000
    HEAP_RATIO = 0.95
    IGNORE_ABOVE = 1.0
    DEFAULT_THRESHOLD = 0.13
    USE_DYNAMIC_THRESHOLD = True


class LogLevelSettings(BaseModel):
    DEFAULT = "INFO"
    PRUSA_LINK = "INFO"
    SERIAL = "INFO"
    SERIAL_READER = "INFO"
    STATE_MANAGER = "INFO"
    COMMANDS = "INFO"
    LCD_PRINTER = "INFO"
    SD_CARD = "INFO"
    IP_UPDATER = "INFO"
    TELEMETRY_GATHERER = "INFO"
    SERIAL_QUEUE = "INFO"
    MOUNTPOINT = "INFO"
    LINUX_FILESYSTEM = "INFO"
    STORAGE = "INFO"
    FILE_PRINTER = "INFO"
    PRINT_STATS = "INFO"
    JOB_ID = "INFO"
    INFO_SENDER = "INFO"
    IS_PLANNER_FED = "INFO"


class MountPointSettings(BaseModel):
    # Can be used for USB sticks and network attached storage
    MOUNTPOINTS = [
    ]
    # Just directories

    # TODO: this is must be constants
    BLACKLISTED_TYPES = [
    ]
    BLACKLISTED_PATHS = [
        "/dev",
        "/sys",
        "/proc",
        "/tmp",
    ]
    BLACKLISTED_NAMES = [
        "SD Card"
    ]


class PathSettings(BaseModel):
    BASE_TMP_PATH = "/var/tmp/Prusa-Link/"
    TMP_FILE = os.path.join(BASE_TMP_PATH, "currently_printing.gcode")
    PP_FILE = os.path.join(BASE_TMP_PATH, "power_panic")
    JOB_FILE = os.path.join(BASE_TMP_PATH, "job_id_data.json")
    THRESHOLD_FILE = os.path.join(BASE_TMP_PATH, "threshold_data")
    CROTITEL_CRONU = os.path.join(BASE_TMP_PATH, "cancel_daily_cron")


class PiSetteings(BaseModel):

    RESET_PIN = 22


class FilePrinterSettings(BaseModel):

    STATS_EVERY = 100
    TAIL_COMMANDS = 10  # how many commands after the last progress report
    PRINT_QUEUE_SIZE = 4


class SettingsData(BaseModel):

    """ Object supposed to hold all settings """
    TIME: IntervalSettings = IntervalSettings()
    LCDQ: LCDQueueSettings = LCDQueueSettings()
    SQ: SerialQueueSettings = SerialQueueSettings()
    LOG: LogLevelSettings = LogLevelSettings()
    MOUNT: MountPointSettings = MountPointSettings()
    PATH: PathSettings = PathSettings()
    PI: PiSetteings = PiSetteings()
    FP: FilePrinterSettings = FilePrinterSettings()
    IPF: IsPlannerFedSettings = IsPlannerFedSettings()


def get_settings() -> SettingsData:
    global instance
    if instance is None:
        path = os.path.join('/var/tmp/Prusa-Link', "config.yaml")
        instance = Settings(SettingsData, path)
    return instance.settings
