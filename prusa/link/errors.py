"""Prusa Link error states.html

For more information see prusa-link_states.txt.
"""

import itertools
from enum import Enum

from typing import Optional
from poorwsgi import state
from poorwsgi.response import JSONResponse, TextResponse

from prusa.connect.printer.errors import ErrorState, INTERNET, HTTP, TOKEN, \
    API

assert HTTP is not None
assert TOKEN is not None


class Categories(Enum):
    """Error categories, so we don't index them by order"""
    PRINTER = "Printer"
    NETWORK = "Network"
    HARDWARE = "Hardware"


OK_MSG = {"ok": True, "message": "OK"}

DEVICE = ErrorState("Device",
                    "Eth|WLAN device does not exist",
                    short_msg="No WLAN device")
PHY = ErrorState("Phy",
                 "Eth|WLAN device is not connected",
                 prev=DEVICE,
                 short_msg="No WLAN conn")
LAN = ErrorState("Lan",
                 "Eth|WLAN has no IP address",
                 prev=PHY,
                 short_msg="No WLAN IP addr")

INTERNET.prev = LAN

SERIAL = ErrorState("Port", "Serial device does not exist")
RPI_ENABLED = ErrorState("RPIenabled", "RPi port is not enabled", prev=SERIAL)
ID = ErrorState("ID", "Device is not a Prusa printer", prev=RPI_ENABLED)
FW = ErrorState("Firmware", "Firmware is not up-to-date", prev=ID)
JOB_ID = ErrorState("JobID", "Job ID cannot be obtained", prev=FW)
SN = ErrorState("SN", "Serial number cannot be obtained", prev=JOB_ID)

HW = ErrorState("HW", "Firmware detected a hardware issue")

# first and last elements for all available error state chains
HEADS = {Categories.PRINTER: SERIAL,
         Categories.NETWORK: DEVICE,
         Categories.HARDWARE: HW}
TAILS = {Categories.PRINTER: SN,
         Categories.NETWORK: API,
         Categories.HARDWARE: HW}


def status():
    """Return a dict with representation of all current error states """
    result = []
    for head in HEADS.values():
        chain = {}
        current = head
        while current is not None:
            chain[current.name] = (current.ok, current.long_msg)
            current = current.next
        result.append(chain)
    return result


def printer_status():
    """Returns a dict with representation of current printer error states"""
    if TAILS[Categories.PRINTER].ok and TAILS[Categories.HARDWARE].ok:
        return OK_MSG
    result = {}
    printer = itertools.chain(HW, SERIAL)
    for error in printer:
        if not error.ok:
            return {"ok": False, "message": error.long_msg}
    return result


def connect_status():
    """Returns a dict with representation of current Connect error states"""
    if TAILS[Categories.NETWORK].ok:
        return OK_MSG
    result = {}
    for error in DEVICE:
        if not error.ok:
            return {"ok": False, "message": error.long_msg}
    return result


def get_error_states_for_head(head):
    """Gets the string of errors starting at the one given"""
    error_states = []
    current = head
    while current is not None:
        error_states.append(current)
        current = current.next
    return error_states


def get_printer_error_states():
    """
    Proxy for getting errors that cause the printer to report
    being in an ERROR state"""
    errors = get_error_states_for_head(SERIAL)
    errors.extend(get_error_states_for_head(HW))
    return errors


def get_all_error_states():
    """Return a list of all ErrorStates"""
    error_states = []
    for head in HEADS.values():
        error_states.extend(get_error_states_for_head(head))
    return error_states


class LinkError(RuntimeError):
    """Link error structure."""
    title: str
    text: str
    id: Optional[str] = None
    status_code: int
    path: Optional[str] = None
    url: str = ''

    def __init__(self):
        if self.id:
            self.path = '/error/' + self.id
        # pylint: disable=consider-using-f-string
        self.template = 'error-%s.html' % self.id
        super().__init__(self.text)

    def set_url(self, req):
        """Set url from request and self.path."""
        self.url = req.construct_url(self.path) if self.path else ''

    def gen_headers(self):
        """Return headers with Content-Location if id was set."""
        return {'Content-Location': self.url} if self.url else {}

    def json_response(self):
        """Return JSONResponse for error."""
        kwargs = dict(title=self.title, text=self.text)
        if self.url:
            kwargs['url'] = self.url
        return JSONResponse(status_code=self.status_code,
                            headers=self.gen_headers(),
                            **kwargs)

    def text_response(self):
        """Return TextResponse for error."""
        url = "\n\nSee: " + self.url if self.url else ''
        # pylint: disable=consider-using-f-string
        return TextResponse("%s\n%s%s" % (self.title, self.text, url),
                            status_code=self.status_code,
                            headers=self.gen_headers())


class BadRequestError(LinkError):
    """400 Bad Request error"""
    status_code = state.HTTP_BAD_REQUEST


class NoFileInRequest(BadRequestError):
    """400 File not found in request payload."""
    title = "Missing file in payload."
    text = "File is not send in request payload or it hasn't right name."
    id = "no-file-in-request"


class FileSizeMismatch(BadRequestError):
    """400 File size mismatch."""
    title = "File Size Mismatch"
    text = "You sent more or less data than is in Content-Length header."
    id = "file-size-mismatch"


class ForbiddenCharacters(BadRequestError):
    """400 Forbidden Characters."""
    title = "Forbidden Characters"
    text = "Forbidden characters in file or folder name."
    id = "forbidden-characters"


class FilenameTooLong(BadRequestError):
    """400 Filename Too Long"""
    title = "Filename Too Long"
    text = "File name length is too long"
    id = "filename-too-long"


class FoldernameTooLong(BadRequestError):
    """400 Foldername Too Long"""
    title = "Foldername Too Long"
    text = "Folder name length is too long"
    id = "foldername-too-long"


class ForbiddenError(LinkError):
    """403 Forbidden"""
    title = "Forbidden"
    text = "You don not have permission to access this."
    status_code = state.HTTP_FORBIDDEN
    id = "forbidden"


class NotFoundError(LinkError):
    """404 Not Found error"""
    title = "Not Found"
    text = "Resource you want not found."
    status_code = state.HTTP_NOT_FOUND
    id = "not-found"


class FileNotFound(NotFoundError):
    """404 File Not Found"""
    title = "File Not Found"
    text = "File you want was not found."


class SDCardNotSupoorted(NotFoundError):
    """404 Some operations are not possible on SDCard."""
    title = "SDCard is not Suppported"
    text = "Location `sdcard` is not supported, use local."
    id = "sdcard-not-supported"


class LocationNotFound(NotFoundError):
    """404 Location from url not found."""
    title = "Location Not Found"
    text = "Location not found, use local."
    id = "location-not-found"


class ConflictError(LinkError):
    """409 Conflict error."""
    status_code = state.HTTP_CONFLICT


class CurrentlyPrinting(ConflictError):
    """409 Printer is currently printing"""
    title = "Printer is currently printing"
    text = "Printer is currently printing."


class NotPrinting(ConflictError):
    """409 Printer is not printing"""
    title = "Printer Is Not Printing"
    text = "Operation you want can be do only when printer is printing."


class FileCurrentlyPrinted(ConflictError):
    """409 File is currently printed"""
    title = "File is currently printed"
    text = "You try to operation with file, which is currently printed."
    id = "file-currently-printed"


class TransferConflict(ConflictError):
    """409 Already in transfer process."""
    title = "Already in transfer process"
    text = "Only one file at time can be transferred."
    id = "transfer-conflict"


# TODO: html variant
class TransferStopped(ConflictError):
    """409 Transfer process was stopped by user."""
    title = "Transfer stopped"
    text = "Transfer process was stopped by user."
    id = "transfer-stoped"


class LengthRequired(LinkError):
    """411 Length Required."""
    title = "Length Required"
    text = "Missing Content-Length header or no content in request."
    id = "length-required"
    status_code = state.HTTP_LENGTH_REQUIRED


class EntityTooLarge(LinkError):
    """413 Payload Too Large"""
    title = "Request Entity Too Large"
    text = "Not enough space in storage."
    id = "entity-too-large"
    status_code = state.HTTP_REQUEST_ENTITY_TOO_LARGE


class UnsupportedMediaError(LinkError):
    """415 Unsupported Media Type"""
    title = "Unsupported Media Type"
    text = "Only G-Code for FDM printer can be uploaded."
    id = "unsupported-media-type"
    status_code = state.HTTP_UNSUPPORTED_MEDIA_TYPE


class InternalServerError(LinkError):
    """500 Internal Server Error."""
    title = "Internal Server Error"
    text = ("We're sorry, but there is a error in service. "
            "Please try again later.")
    id = "internal-server-error"
    status_code = state.HTTP_INTERNAL_SERVER_ERROR


class ResponseTimeout(InternalServerError):
    """500 Response Timeout"""
    title = "Response Timeout"
    text = "There is some problem on PrusaLink."
    id = "response-timeout"


class PrinterUnavailable(LinkError):
    """503 Printer Unavailable."""
    title = "Printer Unavailable."
    text = "PrusaLink not finished initializing or Printer not connected."
    id = "printer-unavailable"
    status_code = state.HTTP_SERVICE_UNAVAILABLE


class RequestTimeout(LinkError):
    """408 Request timeout."""
    title = "Request timeout."
    text = "PrusaLink got tired of waiting for your request. " \
           "cancelled upload?"
    id = "request-timeout"
    status_code = state.HTTP_REQUEST_TIME_OUT
