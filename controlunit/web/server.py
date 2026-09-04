"""The read-only web view that stands beside the Qt window.

A Flask application on a daemon thread inside the ControlUnit process. It
never imports PyQt, never touches a worker, and never writes to the rig: it
reads a small locked status record the Qt main thread keeps up to date, and
asks the two neighbouring services how they are.

Slice one serves the Lab tab only — the three services of the lab ensemble,
their states, and how to start each one.
"""

import threading

from flask import Flask, jsonify, render_template, request

from controlunit._version import __version__
from controlunit.web import neighbours as neighbourhood
from controlunit.web.status import RigStatus, SERVICE, health_body

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4187

#: How to start each service: what it means in plain words, and the line to
#: type, which the page keeps behind a toggle rather than leading with it.
START_HOWTO = {
    "controlunit": (
        "Start this program again with its web view switched on.",
        "lab controlunit --web",
    ),
    "pihti-log": (
        "Start the lab journal on the machine that holds the vault.",
        "lab pihti-log",
    ),
    "pihti-diagram": (
        "Start the vacuum diagram on the machine it lives on.",
        "lab pihti-diagram",
    ),
}

#: Stated once, in the Lab tab's right rail, and nowhere else on the page.
STATE_LEGEND = (
    ("ok", "answered, and running the way it should"),
    ("degraded", "answered, but not fully working"),
    ("down", "answered, and said it is not working"),
    ("unreachable", "nothing answered from this machine"),
    ("not configured", "this machine has no address for it"),
)


def create_app(status=None, board=None):
    """Build the application. `status` is the record the Qt thread writes."""
    rig = status if status is not None else RigStatus()
    services = board if board is not None else neighbourhood.NeighbourBoard()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config["RIG_STATUS"] = rig
    app.config["NEIGHBOUR_BOARD"] = services

    @app.after_request
    def freshness_and_safety(response):
        # One freshness contract for the whole surface: nothing is stored, so
        # new markup never meets a stale stylesheet after an upgrade.
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def self_row():
        report = health_body(rig, __version__)
        return {
            "alias": SERVICE,
            "name": neighbourhood.DISPLAY_NAMES[SERVICE],
            "url": request.host_url.rstrip("/") if request else "",
            "state": report["status"],
            "version": report["version"],
            "detail": report["detail"],
        }

    def board_rows():
        rows = [self_row()]
        rows.extend(services.neighbours())
        for row in rows:
            meaning, command = START_HOWTO.get(row["alias"], ("", ""))
            row["meaning"] = meaning
            row["start"] = command
            row["here"] = row["alias"] == SERVICE
        return rows

    @app.route("/")
    def lab():
        return render_template(
            "lab.html",
            app_version=__version__,
            services=board_rows(),
            legend=STATE_LEGEND,
        )

    @app.route("/api/health")
    def health():
        return jsonify(health_body(rig, __version__))

    @app.route("/api/neighbours")
    def neighbours():
        return jsonify({"services": board_rows()})

    return app


def serve_in_thread(status, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Start the web view on a daemon thread and return the thread.

    A daemon thread simply stops answering when the process ends, so the
    hardware-first shutdown order the Qt side owns is left exactly as it was.
    """
    app = create_app(status)

    def run():
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)

    thread = threading.Thread(target=run, name="webview", daemon=True)
    thread.start()
    return thread
