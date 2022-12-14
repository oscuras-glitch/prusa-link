"""A place for Prusa-Link camera drivers"""
import ctypes
import fcntl
import logging
from glob import glob

import v4l2py  # type: ignore
import v4l2py.raw  # type: ignore
from v4l2py.device import PixelFormat, Device  # type: ignore

from prusa.connect.printer.camera_driver import CameraDriver
from prusa.connect.printer.camera import Resolution
from prusa.connect.printer.const import CapabilityType, NotSupported
from .util import from_422_to_jpeg

log = logging.getLogger(__name__)


class MediaDeviceInfo(ctypes.Structure):
    """A data structure for getting media device info"""
    _fields_ = [
        ("driver", ctypes.c_char * 16),
        ("model", ctypes.c_char * 32),
        ("serial", ctypes.c_char * 40),
        ("bus_info", ctypes.c_char * 32),
        ("media_version", ctypes.c_uint32),
        ("hw_revision", ctypes.c_uint32),
        ("driver_version", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 31),
    ]


PIX_FMT_TO_STRING = {PixelFormat.MJPEG: "MJPG",
                     PixelFormat.YUYV: "YUYV"}


# pylint: disable=protected-access
MEDIA_IOC_DEVICE_INFO = v4l2py.raw._IOWR('|', 0x00, MediaDeviceInfo)


def read_media_device_info(path):
    """Given a media device path, reads its associated info
    :raises PermissionError"""
    info = MediaDeviceInfo()
    # pylint: disable=unspecified-encoding
    with open(path, "r") as file:
        file_descriptor = file.fileno()
        if fcntl.ioctl(file_descriptor, MEDIA_IOC_DEVICE_INFO, info):
            raise RuntimeError("Failed getting media device info "
                               f"for device {path}")
    return info


def get_media_device_path(device: Device):
    """Gets the media device path for a video device

    Pairs /dev/video* to /dev/media*"""
    bus_info = device.info.bus_info
    paths = glob("/dev/media*")
    for path in paths:
        try:
            info = read_media_device_info(path)
        except PermissionError:
            log.exception("Failed getting a media device for %s. "
                          "This is commonly caused by the linux user "
                          "not being a member of the 'video' group",
                          device.filename)
        else:
            if bus_info == info.bus_info.decode("UTF-8"):
                return path
    return None


def param_change(func):
    """Wraps any settings change with a stop and start of the video
    stream, so the camera driver does not return it's busy"""

    def inner(self, new_param):
        # pylint: disable=protected-access
        self._stop_stream()
        func(self, new_param)
        self._start_stream()

    return inner


class V4L2Driver(CameraDriver):
    """Linux V4L2 USB webcam driver"""

    name = "V4L2"
    REQUIRES_SETTINGS = {
        "path": "Path to the V4L2 device like '/dev/video1'"
    }

    @staticmethod
    def _scan():
        """Implements the mandated scan method, returns available USB
        cameras"""
        available = {}
        devices = v4l2py.device.iter_video_capture_devices()
        for device in devices:
            # Disqualify picameras - they need special treatment
            if device.info.bus_info == "platform:bcm2835-isp":
                continue

            media_device_path = get_media_device_path(device)
            if media_device_path is None:
                continue

            path = str(device.filename)
            name = device.info.card
            try:
                info = read_media_device_info(media_device_path)
                serial = info.serial.decode("ascii")
            except (OSError, PermissionError):
                log.exception("Getting camera sn failed for camera %s at %s",
                              name, path)
                continue
            else:
                camera_id = " ".join((name, serial))
                log.info("Camera id is %s", camera_id)
                available[camera_id] = dict(path=path, name=name)
        return available

    def __init__(self, camera_id, config, unavailable_cb):
        # pylint: disable=duplicate-code
        super().__init__(camera_id, config, unavailable_cb)

        self._resolution_to_format = {}
        self.device = None
        self.stream = None

    def _connect(self):
        """Connects to the V4L2 camera"""
        path = self.config["path"]

        self._capabilities = ({
            CapabilityType.TRIGGER_SCHEME,
            CapabilityType.IMAGING,
            CapabilityType.RESOLUTION
        })

        extra_unsupported_formats = set()
        self.device = v4l2py.Device(path)
        self._available_resolutions = set()
        for frame_type in self.device.info.frame_sizes:
            resolution = Resolution(width=frame_type.width,
                                    height=frame_type.height)

            # Prefer MJPEG over others
            if resolution in self._resolution_to_format:
                if self._resolution_to_format[resolution] == "MJPG":
                    continue

            pixel_format = frame_type.pixel_format
            if pixel_format not in PIX_FMT_TO_STRING:
                if pixel_format.name not in extra_unsupported_formats:
                    log.debug("Pixel format %s not supported",
                              pixel_format.name)
                extra_unsupported_formats.add(pixel_format.name)
                continue

            str_pixel_format = PIX_FMT_TO_STRING[pixel_format]
            self._available_resolutions.add(resolution)
            self._resolution_to_format[resolution] = str_pixel_format

        if not self.available_resolutions:
            raise NotSupported(
                "Sorry, PrusaLink supports only YUYV 4:2:2 and MJPEG. "
                f"Camera {self.camera_id} supports only these formats: "
                f"{extra_unsupported_formats}")

        highest_resolution = sorted(self.available_resolutions)[-1]
        self._config["resolution"] = str(highest_resolution)

        self.device.video_capture.set_format(highest_resolution.width,
                                             highest_resolution.height)

        self._start_stream()

    def _start_stream(self):
        """Initiates stream from the webcam"""
        self.stream = v4l2py.device.VideoStream(self.device.video_capture)
        self.device.video_capture.start()

    def _stop_stream(self):
        """Stops the camera stream"""
        if self.device is not None:
            self.device.video_capture.stop()

        if self.stream is not None:
            self.stream.close()

    def take_a_photo(self):
        """Since using the threaded camera class, this takes a photo the
        blocking way"""
        self.stream.read()  # Throw the old data out
        data = self.stream.read()

        video_format = self.device.video_capture.get_format()
        width = video_format.width
        height = video_format.height
        pixel_format = video_format.pixel_format

        str_pixel_format = PIX_FMT_TO_STRING[pixel_format]
        if str_pixel_format == "YUYV":
            data = from_422_to_jpeg(data, width, height)

        return data

    @param_change
    def set_resolution(self, resolution):
        """Sets the camera resolution"""
        pixel_format = self._resolution_to_format[resolution]
        self.device.video_capture.set_format(
            resolution.width, resolution.height, pixel_format)

    def disconnect(self):
        """Disconnects from the camera"""
        if self.device is None:
            return
        try:
            self._stop_stream()
        except OSError:
            log.warning("Camera %s stream could not be closed",
                        self.camera_id)
        try:
            self.device.close()
        except OSError:
            log.warning("Camera %s file could not be closed",
                        self.camera_id)
        super().disconnect()
