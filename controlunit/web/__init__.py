"""ControlUnit's web view: a Flask application beside the Qt window.

This module stays empty of imports on purpose. `controlunit.web.status` is
plain standard library and the Qt side reads it on every boot; the Flask
application in `controlunit.web.server` is imported only when `--web` is
given, so a machine without Flask still starts the window exactly as before.

Nothing under this package imports PyQt or touches a worker.
"""
