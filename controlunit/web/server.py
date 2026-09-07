"""The web view that stands beside the Qt window.

A Flask application on a daemon thread inside the ControlUnit process. It
never imports PyQt and never touches a worker: it reads a small locked status
record the Qt main thread keeps up to date, asks the two neighbouring
services how they are, and — for the Control tab — appends checked commands
to a queue the main thread drains on its own timer.

Four tabs are served. Live is the rig's values and three strip charts; Control
starts and stops a run and sets what the rig holds; Log is the same message
log the Qt Log dock shows; Lab is the three services of the lab ensemble and
how each is started.

Reading is open to anyone on the lab network. Setting needs a name chosen in
the browser, the Remote switch turned on beside the rig's own screen so that
gas flow and cathode current never move past a person who is not there, the
lab's word where the machine serving the page holds one, and control of the
rig, which the first browser to send a setter holds and a second person takes
over in the open. Stopping every output is the one exception and is always
allowed.
"""

import math
import threading

from flask import Flask, jsonify, make_response, render_template, request

from controlunit._version import __version__
from controlunit.web import commands as command_desk
from controlunit.web import fence as fence_line
from controlunit.web import neighbours as neighbourhood
from controlunit.web import roster as people_list
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

#: The lab's word this browser has typed, where the machine serving the page
#: asks for one. It is carried rather than proved: a fence one may walk over,
#: kept for the same thirty days as the name, and never anybody's password.
FENCE_COOKIE = "fence"

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


def create_app(status=None, board=None, commands=None, roster=None, fence=None):
    """Build the application.

    `status` is the record the Qt thread writes; `commands` is the queue it
    drains. Without a queue the Control tab still renders and every setter
    answers 409, which is what a test client and a read-only run both want.
    `roster` is the lab's list of operator names, when this machine has a
    copy of one; without it the Acting-as field is free text, as before.
    `fence` is the lab's word, when this machine holds one; a machine that
    holds none has no fence and every route behaves as it always has.
    """
    rig = status if status is not None else RigStatus()
    services = board if board is not None else neighbourhood.NeighbourBoard()
    desk = commands if commands is not None else command_desk.CommandQueue()
    people = roster if roster is not None else people_list.Roster()
    barrier = fence if fence is not None else fence_line.Fence()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config["RIG_STATUS"] = rig
    app.config["NEIGHBOUR_BOARD"] = services
    app.config["COMMAND_QUEUE"] = desk
    app.config["ROSTER"] = people
    app.config["FENCE"] = barrier

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

    def fence_now():
        """Whether this machine asks for the lab's word, and whether this
        browser has typed it. Answered here for the same reason
        `control.mine` is: a page cannot see its own cookies, so the rig
        says where the reader stands rather than the page guessing.
        """
        word = barrier.word()
        if not word:
            return {"needed": False, "passed": False}
        carried = request.cookies.get(FENCE_COOKIE) if request else None
        return {"needed": True, "passed": str(carried or "").strip() == word}

    def fence_refusal(kind):
        """Why the lab's word stands in the way, or an empty string.

        It gates exactly what the switch gates — every locked kind and the
        taking of control — and nothing else. **Stop all outputs is never
        fenced**: a person who can see the rig must be able to zero it,
        whether or not they have been told a word.
        """
        if kind not in command_desk.LOCKED and kind != "take_over":
            return ""
        standing = fence_now()
        if standing["needed"] and not standing["passed"]:
            return command_desk.NO_FENCE_WORD
        return ""

    def page_state():
        return state_body(
            rig, __version__, control=control_now(), fence=fence_now()
        )

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
            sampling_choices=command_desk.sampling_choices(),
            actor=command_desk.clean_actor(request.cookies.get(ACTOR_COOKIE)),
            roster_names=people.names(),
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
        """The ring, by span or by what a browser has not seen yet.

        `since` is the Live tab's steady state: it fills its own history
        from the ring once and then asks only for samples newer than the
        newest stamp it holds, so a page left open all afternoon costs the
        Pi a handful of rows per poll. `window` is unchanged and still
        answers anyone who sends it; `since` wins when both arrive.
        """
        window = _bounded_int(request.args.get("window"), DEFAULT_WINDOW, 0, 10**7)
        points = _bounded_int(request.args.get("points"), MAX_POINTS, 2, MAX_POINTS)
        since = _epoch(request.args.get("since"))
        body = rig.series(
            window_seconds=window, max_points=points, since=since
        )
        body["window"] = window
        body["since"] = since
        return jsonify(body)

    @app.route("/api/log")
    def log_lines():
        since = _bounded_int(request.args.get("since"), 0, 0, 10**12)
        return jsonify(rig.log_since(since))

    # -- what the Control tab sends -----------------------------------------

    @app.route("/api/roster")
    def roster_names():
        """The lab's operator names, so a page can refresh without a reload."""
        return jsonify({"names": people.names()})

    @app.route("/api/identify", methods=["POST"])
    def identify():
        """Remember, in this browser, the name to write beside a command.

        A name is a label for the log and never a credential, so a machine
        with no roster takes whatever was typed, exactly as before. Where
        there *is* a roster the field offers it, and a name that is not on it
        is refused — not to keep anyone out, but so the lab's logs spell one
        person one way. The comparison is between cleaned names, so a roster
        entry that `clean_actor` would shorten still matches itself.
        """
        name = command_desk.clean_actor(_json_body().get("name"))
        if not name:
            return jsonify({"reason": "type a name first"}), 400
        known = [command_desk.clean_actor(person) for person in people.names()]
        if known and name not in known:
            return jsonify({"reason": "choose a name from the lab's roster"}), 400
        answer = make_response(jsonify({"actor": name}))
        answer.set_cookie(
            ACTOR_COOKIE,
            name,
            max_age=ACTOR_MAX_AGE,
            samesite="Lax",
            httponly=True,
        )
        return answer

    @app.route("/api/fence", methods=["POST"])
    def fence_word():
        """Pass the lab's word once, and carry it in this browser after.

        A machine with no word says so and stores nothing, so a browser may
        always ask and a page always knows where it stands. A wrong word is
        `403` and nothing else happens: the failed try is not written to the
        message log, because the log belongs to the Qt main thread and this
        is the web thread — and because a stranger's typing is not worth a
        line beside the gas flows.
        """
        word = barrier.word()
        if not word:
            return jsonify({"fenced": False})
        if not barrier.opens(_json_body().get("word")):
            return jsonify({"reason": command_desk.WRONG_FENCE_WORD}), 403
        answer = make_response(jsonify({"fenced": True}))
        answer.set_cookie(
            FENCE_COOKIE,
            word,
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
        # The lab's word stands beside the switch, and behind it: a rig whose
        # switch is off says so first, because that is the fact a person can
        # do something about by walking to the machine.
        refused = fence_refusal(kind)
        if refused:
            return jsonify({"reason": refused}), 403
        if command_desk.needs_acquisition(kind) and not snapshot.get("acquiring"):
            return jsonify({"reason": command_desk.NO_ACQUISITION}), 409
        # Starting is the one command that means something only while idle,
        # so it is the one refused for the opposite fact.
        if command_desk.needs_idle(kind) and snapshot.get("acquiring"):
            return jsonify({"reason": command_desk.ALREADY_ACQUIRING}), 409

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
        refused = fence_refusal("take_over")
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

    @app.route("/api/acquisition/start", methods=["POST"])
    def acquisition_start():
        return send("start")

    @app.route("/api/acquisition/stop", methods=["POST"])
    def acquisition_stop():
        return send("stop")

    @app.route("/api/sampling", methods=["POST"])
    def sampling():
        return send("sampling")

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


def _epoch(text):
    """An epoch-seconds query value, or `None` when there is not one.

    `None` is the whole point: it is how the series route tells "this
    browser holds nothing yet, give it the ring" from "this browser has
    seen everything up to here".
    """
    if text is None or text == "":
        return None
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return max(0.0, value)


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
