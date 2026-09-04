"""The read-only web view that stands beside the Qt window.

A Flask application on a daemon thread inside the ControlUnit process. It
never imports PyQt, never touches a worker, and never writes to the rig: it
reads a small locked status record the Qt main thread keeps up to date, and
asks the two neighbouring services how they are.

Three tabs are served. Live is the rig's values and two strip charts; Log is
the same message log the Qt Log dock shows; Lab is the three services of the
lab ensemble, their states, and how each is started. Control is named in
the tab bar and not built: browser control waits on an owner decision.
"""

import threading

from flask import Flask, jsonify, render_template, request

from controlunit._version import __version__
from controlunit.web import neighbours as neighbourhood
from controlunit.web.status import (
    MAX_POINTS,
    RigStatus,
    SERVICE,
    health_body,
    state_body,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4187

#: Where this program runs and how it is started there. The rig launches
#: it from its desktop shortcut, which calls the launcher kept in the
#: repository; there is no `lab` on the Pi.
SELF_WHERE = "on the rig, beside its own screen"
SELF_START = "scripts/run_controlunit.sh"

#: Stated once, in the Lab tab's right rail, and nowhere else on the page.
STATE_LEGEND = (
    ("ok", "answered, and running the way it should"),
    ("degraded", "answered, but not fully working"),
    ("down", "answered, and said it is not working"),
    ("unreachable", "nothing answered from this machine"),
    ("not configured", "this machine has no address for it"),
)

#: The live window choices, the same ones the Qt control dock offers.
WINDOWS = (
    ("20 s", 20),
    ("1 m", 60),
    ("5 m", 300),
    ("15 m", 900),
    ("30 m", 1800),
    ("1 h", 3600),
    ("2 h", 7200),
    ("Full", 0),
)
DEFAULT_WINDOW = 300

#: The five signals the rig's own graph draws, in its own pen colours, so a
#: curve has one colour on the rig's screen and on a laptop.
PENS = (
    ("Ip", "#8d3de3"),
    ("Pu", "#c9004d"),
    ("Pd", "#6ac600"),
    ("Bu", "#ffb405"),
    ("Bd", "#00a3af"),
)

#: The tabs, in bar order. A tab with no endpoint is named and not built.
TABS = (
    ("live", "Live", "live"),
    ("control", "Control", None),
    ("log", "Log", "log"),
    ("lab", "Lab", "lab"),
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

    @app.context_processor
    def page_constants():
        return {"app_version": __version__, "tabs": TABS}

    def self_row():
        report = health_body(rig, __version__)
        return {
            "alias": SERVICE,
            "name": neighbourhood.DISPLAY_NAMES[SERVICE],
            "url": request.host_url.rstrip("/") if request else "",
            "state": report["status"],
            "version": report["version"],
            "detail": report["detail"],
            "where": SELF_WHERE,
            "start": SELF_START,
        }

    def board_rows():
        rows = [self_row()]
        rows.extend(services.neighbours())
        for row in rows:
            row["here"] = row["alias"] == SERVICE
        return rows

    # -- pages ---------------------------------------------------------------

    @app.route("/")
    def live():
        return render_template(
            "live.html",
            active="live",
            windows=WINDOWS,
            default_window=DEFAULT_WINDOW,
            pens=PENS,
            state=state_body(rig, __version__),
        )

    @app.route("/log")
    def log():
        return render_template(
            "log.html",
            active="log",
            state=state_body(rig, __version__),
            log=rig.log_since(0),
        )

    @app.route("/lab")
    def lab():
        return render_template(
            "lab.html",
            active="lab",
            services=board_rows(),
            legend=STATE_LEGEND,
        )

    # -- the ensemble's contract --------------------------------------------

    @app.route("/api/health")
    def health():
        return jsonify(health_body(rig, __version__))

    @app.route("/api/neighbours")
    def neighbours():
        return jsonify({"services": board_rows()})

    # -- what the Live and Log tabs poll ------------------------------------

    @app.route("/api/state")
    def state():
        return jsonify(state_body(rig, __version__))

    @app.route("/api/series")
    def series():
        window = _bounded_int(request.args.get("window"), DEFAULT_WINDOW, 0, 10**7)
        points = _bounded_int(request.args.get("points"), MAX_POINTS, 2, MAX_POINTS)
        body = rig.series(window_seconds=window, max_points=points)
        body["window"] = window
        return jsonify(body)

    @app.route("/api/log")
    def log_lines():
        since = _bounded_int(request.args.get("since"), 0, 0, 10**12)
        return jsonify(rig.log_since(since))

    return app


def _bounded_int(text, default, low, high):
    """An integer query value clamped to [low, high], or the default."""
    try:
        value = int(text)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


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
