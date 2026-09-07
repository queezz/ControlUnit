"""The web view that stands beside the Qt window.

A Flask application on a daemon thread inside the ControlUnit process. It
never imports PyQt and never touches a worker: it reads a small locked status
record the Qt main thread keeps up to date, asks the two neighbouring
services how they are, and — for the Control tab — appends checked commands
to a queue the main thread drains on its own timer.

Four tabs are served. Live is the rig's values and two strip charts; Control
sets what the rig holds; Log is the same message log the Qt Log dock shows;
Lab is the three services of the lab ensemble and how each is started.

Reading is open to anyone on the lab network. Setting needs a name chosen in
the browser, the Remote switch turned on beside the rig's own screen so that
gas flow and cathode current never move past a person who is not there, and
control of the rig, which the first browser to send a setter holds and a
second person takes over in the open. Stopping every output is the one
exception and is always allowed.
"""

import threading

from flask import Flask, jsonify, make_response, render_template, request

from controlunit._version import __version__
from controlunit.web import commands as command_desk
from controlunit.web import neighbours as neighbourhood
from controlunit.web.status import (
    MAX_POINTS,
    RigStatus,
    SERVICE,
    ZERO_CHANNELS,
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
    ("checking", "this machine is asking now and has not heard back"),
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
    ("control", "Control", "control"),
    ("log", "Log", "log"),
    ("lab", "Lab", "lab"),
)

#: The name a browser carries, so the log can say who asked for a setpoint.
#: A label, never an identity: it proves nothing and is not a credential.
ACTOR_COOKIE = "actor"
ACTOR_MAX_AGE = 60 * 60 * 24 * 30

#: The Control tab's own groups, in operating order. The right rail's index
#: is built from this, so the page cannot promise a section it does not have.
SECTIONS = (
    ("sec-acquisition", "Acquisition"),
    ("sec-gas", "Gas flow"),
    ("sec-plasma", "Plasma current"),
    ("sec-gauge", "Gauge and sync"),
    ("sec-baselines", "Baselines"),
)

#: The two gas lines, by the gas each carries on this rig.
GASES = ((1, "H₂"), (2, "O₂"))


def create_app(status=None, board=None, commands=None):
    """Build the application.

    `status` is the record the Qt thread writes; `commands` is the queue it
    drains. Without a queue the Control tab still renders and every setter
    answers 409, which is what a test client and a read-only run both want.
    """
    rig = status if status is not None else RigStatus()
    services = board if board is not None else neighbourhood.NeighbourBoard()
    desk = commands if commands is not None else command_desk.CommandQueue()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config["RIG_STATUS"] = rig
    app.config["NEIGHBOUR_BOARD"] = services
    app.config["COMMAND_QUEUE"] = desk

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

    def who_is_asking():
        """The name this browser carries and the address it is asking from."""
        return (
            command_desk.clean_actor(request.cookies.get(ACTOR_COOKIE)),
            request.remote_addr or "",
        )

    def control_now():
        """Who holds control, and whether that is the browser asking.

        A page cannot tell its own address from a response — nothing here
        carries one except the holder line, which is the whole point of it —
        so whether the reader is the holder is answered here rather than
        compared there.
        """
        actor, origin = who_is_asking()
        body = desk.control.read()
        body["mine"] = desk.control.held_by(actor, origin)
        body["line"] = command_desk.holder_sentence(body)
        return body

    def page_state():
        return state_body(rig, __version__, control=control_now())

    # -- pages ---------------------------------------------------------------

    @app.route("/")
    def live():
        return render_template(
            "live.html",
            active="live",
            windows=WINDOWS,
            default_window=DEFAULT_WINDOW,
            pens=PENS,
            state=page_state(),
        )

    @app.route("/control")
    def control():
        return render_template(
            "control.html",
            active="control",
            state=page_state(),
            sections=SECTIONS,
            gases=GASES,
            zero_channels=ZERO_CHANNELS,
            gauge_modes=command_desk.GAUGE_MODES,
            gauge_range=range(
                command_desk.GAUGE_RANGE_LOW, command_desk.GAUGE_RANGE_HIGH + 1
            ),
            mfc_max=command_desk.MFC_MAX_MV,
            plasma_max=command_desk.PLASMA_MAX_A,
            actor=command_desk.clean_actor(request.cookies.get(ACTOR_COOKIE)),
        )

    @app.route("/log")
    def log():
        return render_template(
            "log.html",
            active="log",
            state=page_state(),
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
        return jsonify(page_state())

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

    # -- what the Control tab sends -----------------------------------------

    @app.route("/api/identify", methods=["POST"])
    def identify():
        """Remember, in this browser, the name to write beside a command."""
        name = command_desk.clean_actor(_json_body().get("name"))
        if not name:
            return jsonify({"reason": "type a name first"}), 400
        answer = make_response(jsonify({"actor": name}))
        answer.set_cookie(
            ACTOR_COOKIE,
            name,
            max_age=ACTOR_MAX_AGE,
            samesite="Lax",
            httponly=True,
        )
        return answer

    def send(kind, number=None):
        """Check a command, weigh the gate, and queue it. One shape for all.

        Nothing here calls the rig. A queued command is `202` and an id; the
        browser learns what actually happened from the next `/api/state`,
        never by assuming its own request succeeded.
        """
        actor, origin = who_is_asking()
        snapshot = rig.read()

        refused = command_desk.refusal(
            kind, snapshot.get("remote"), actor, origin=origin, control=desk.control
        )
        if refused:
            return jsonify({"reason": refused}), 403
        if command_desk.needs_acquisition(kind) and not snapshot.get("acquiring"):
            return jsonify({"reason": command_desk.NO_ACQUISITION}), 409

        try:
            value = command_desk.validate(kind, _json_body(), number=number)
            queued = desk.submit(kind, value, actor=actor, origin=origin)
        except command_desk.Invalid as reason:
            code = 409 if str(reason) == command_desk.TOO_MANY else 400
            return jsonify({"reason": str(reason)}), code

        return jsonify({"id": queued.id, "value": queued.summary()}), 202

    @app.route("/api/take-over", methods=["POST"])
    def take_over():
        """Move control of the rig to this browser, deliberately.

        The lock moves here, in the thread that was asked, so the answer is
        true when it is given; the main thread then logs it with the new
        name, where it came from and when, like any other command. Taking
        over when you already hold it changes nothing and says so.
        """
        actor, origin = who_is_asking()
        refused = command_desk.refusal("take_over", rig.read().get("remote"), actor)
        if refused:
            return jsonify({"reason": refused}), 403
        changed, previous = desk.control.take_over(actor, origin)
        if changed:
            try:
                desk.submit("take_over", {"from": previous}, actor=actor, origin=origin)
            except command_desk.Invalid:
                # The queue is full of setpoints. Control has still moved;
                # only the log line for it is lost, which is not worth
                # refusing a person the rig in front of them.
                pass
        return jsonify({"changed": changed, "control": control_now()})

    @app.route("/api/stop-all", methods=["POST"])
    def stop_all():
        return send("stop_all")

    @app.route("/api/mfc/<int:number>", methods=["POST"])
    def mfc(number):
        return send("mfc", number=number)

    @app.route("/api/plasma-current", methods=["POST"])
    def plasma_current():
        return send("plasma")

    @app.route("/api/gauge", methods=["POST"])
    def gauge():
        return send("gauge")

    @app.route("/api/sync", methods=["POST"])
    def sync():
        return send("sync")

    @app.route("/api/zero", methods=["POST"])
    def zero():
        return send("zero")

    return app


def _json_body():
    """The request's JSON object, or an empty one; never an exception."""
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _bounded_int(text, default, low, high):
    """An integer query value clamped to [low, high], or the default."""
    try:
        value = int(text)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def serve_in_thread(status, commands=None, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Start the web view on a daemon thread and return the thread.

    A daemon thread simply stops answering when the process ends, so the
    hardware-first shutdown order the Qt side owns is left exactly as it was.
    """
    app = create_app(status, commands=commands)

    def run():
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)

    thread = threading.Thread(target=run, name="webview", daemon=True)
    thread.start()
    return thread
