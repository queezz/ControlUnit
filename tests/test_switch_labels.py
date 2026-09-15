"""The words on the painted switches, held inside the switch that paints them.

A toggle here is drawn by hand, and Qt clips a widget's painting at the
widget's own edge. For years each switch drew itself at the size written into
its class whatever size the layout had actually given it, so a switch wider
than its column lost its ends. On the Control dock's top row, four widgets
share the width, and at the dock's usual width on the rig that is about 110 px
each against the Remote switch's wished-for 148: the owner's screenshot showed
LOCAL as ".OCAL" (queezz, 2026-09-15).

Nothing here looks at pixels, which is just as well — the offscreen platform
has no font database to draw glyphs with. The check is the measurement the
painting itself uses: `label_rect` asks `label_font` and `thumb_rect` where
the word will land, exactly as `paintEvent` does, and the word has to land
inside the widget. Both states of every switch, because only one of them is
on screen at a time and the other is the one that surprises you.
"""

import os

import pytest

# Before PyQt is imported by anything: these tests draw no window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The Control dock on the rig's screen, from the owner's screenshot. Four
# widgets share this row, so each gets about a quarter of it.
DOCK_WIDTH = 480


@pytest.fixture(scope="module")
def qt_app():
    """One QApplication for the module; Qt allows exactly one per process."""
    QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
    existing = QtWidgets.QApplication.instance()
    if existing is not None:
        return existing
    try:
        return QtWidgets.QApplication([])
    except Exception as error:  # a machine with no usable Qt platform
        pytest.skip("no Qt platform available: {}".format(error))


def _top_row(qt_app):
    """The Control dock at the rig's width, laid out, with its top row."""
    from controlunit.ui.docks.control import ControlDock

    dock = ControlDock()
    dock.resize(DOCK_WIDTH, 420)
    dock.widget.resize(DOCK_WIDTH, 420)
    dock.show()
    qt_app.processEvents()
    dock.widget.layout.activate()
    qt_app.processEvents()
    switches = [dock.OnOffSW, dock.remoteSW, dock.qmsSigSw]
    # The row really was laid out and really is as narrow as the rig's is.
    assert all(0 < s.rect().width() < DOCK_WIDTH // 3 for s in switches)
    return dock, switches


def test_every_switch_on_the_control_row_holds_both_its_words(qt_app):
    """At the rig's dock width, no state of any switch paints off its edge."""
    dock, switches = _top_row(qt_app)
    for switch in switches:
        name = type(switch).__name__
        assert switch.rect().contains(switch.track_rect()), f"{name} track clipped"
        for checked in (False, True):
            label = switch.labels[0] if checked else switch.labels[1]
            where = switch.label_rect(checked)
            assert switch.rect().contains(where), (
                f"{name} paints {label!r} at {where} outside its "
                f"{switch.rect().width()}x{switch.rect().height()} widget"
            )


def test_a_switch_does_not_answer_to_a_touch_outside_itself(qt_app):
    """The same overreach seen from the other side, and in older API.

    A switch that painted past its edge also took its clickable area from
    the size it wished for, so the Remote switch counted a press one pixel
    to the left of the widget as a press on itself. Nothing but a test can
    put a finger there, but it is the one symptom of this bug that can be
    measured without the geometry the fix introduced.
    """
    from PyQt5.QtCore import QPoint

    dock, switches = _top_row(qt_app)
    for switch in switches:
        middle = switch.rect().center().y()
        for outside in (QPoint(-1, middle), QPoint(switch.rect().width(), middle)):
            assert not switch.hitButton(outside), (
                f"{type(switch).__name__} takes a press at {outside} as its own"
            )


def test_a_switch_does_not_resize_its_word_when_it_is_thrown(qt_app):
    """Both labels are measured together, so throwing it moves nothing else."""
    dock, switches = _top_row(qt_app)
    for switch in switches:
        off = switch.label_font(False).pointSize()
        on = switch.label_font(True).pointSize()
        assert off == on, f"{type(switch).__name__} changes size when thrown"


def test_a_switch_keeps_the_size_it_asks_for_when_the_room_is_there(qt_app):
    """Fitting is a squeeze, not a redesign: given room, nothing changes.

    The rest of the program puts these switches in wider places, and this
    holds the fix to the case it was made for.
    """
    from controlunit.ui.buttons.toggles import RemoteSwitch

    switch = RemoteSwitch()
    switch.resize(2 * switch.width + 8, 40)
    assert switch.track_rect().width() == 2 * switch.width
    assert switch.track_rect().height() == 2 * switch.radius
    for checked in (False, True):
        assert switch.rect().contains(switch.label_rect(checked))


def test_a_switch_squeezed_to_its_minimum_still_holds_its_words(qt_app):
    """Down to the narrowest the widget will ever be, the word still fits."""
    from controlunit.ui.buttons.toggles import (
        MySwitch,
        OnOffSwitch,
        QmsSwitch,
        RemoteSwitch,
    )

    for cls in (MySwitch, OnOffSwitch, QmsSwitch, RemoteSwitch):
        switch = cls()
        switch.resize(switch.minimumWidth(), switch.minimumHeight())
        assert switch.rect().contains(switch.track_rect())
        for checked in (False, True):
            label = switch.labels[0] if checked else switch.labels[1]
            assert switch.rect().contains(switch.label_rect(checked)), (
                f"{cls.__name__} clips {label!r} at its minimum width"
            )
