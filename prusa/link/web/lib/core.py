"""WSGI application initialization."""
from hashlib import sha256
from time import time
from os.path import join, abspath

import os

try:
    from importlib.resources import files  # type: ignore
except ImportError:
    from importlib_resources import files  # 3.9 has native resources

from poorwsgi import Application
from poorwsgi.digest import PasswordMap

STATIC_DIR = abspath(
    os.environ.get('PRUSA_LINK_STATIC', join(str(files('prusa.link')),
                                             'static')))


class PrusaLink(Application):
    """Extended Application object."""
    cfg = None
    settings = None
    daemon = None
    wizard = None
    api_key = None
    posting_data = False


app = application = PrusaLink(__package__)
app.keep_blank_values = 1
app.auto_form = False  # only POST /api/files/<target> endpoints get HTML form
app.document_root = STATIC_DIR

app.secret_key = sha256(str(time()).encode()).hexdigest()
app.auth_type = 'Digest'
app.auth_timeout = 60
app.auth_map = PasswordMap()
