import math

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRect, QPoint


class MySwitch(QtWidgets.QPushButton):
    # The size the switch would like: `width` is half the track, so the track
    # is drawn 2*width wide. The layout hands out whatever the dock's width
    # divides into, which can be less than this, so `track_rect` below treats
    # these two as a wish rather than a measurement.
    radius = 10
    width = 38
    # 0 - On, 1 - Off
    labels = ["FULL", "NORM"]
    # colors = [Qt.green, Qt.red]
    colors = [QtGui.QColor("#e9fac5"), QtGui.QColor("#8f94c2")]

    # Half the width of the outline this paints, which straddles the edge of
    # every rect it draws and so has to stay inside the widget too.
    _pen_overhang = 2
    # Kept clear at each end of the word, so a label that only just fits does
    # not sit against the rounded end of the sliding part.
    _label_padding = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(66)
        self.setMinimumHeight(35)

    # MARK: painted geometry
    def track_rect(self):
        """The whole switch, fitted to the widget rather than to the wish.

        The wanted size used to be painted whatever the widget's size, and
        Qt clips a widget's painting at its own edge, so a switch too wide
        for its column lost its ends. The Remote switch is 148 px wide by
        the numbers above and the Control dock's top row gives it 111 at the
        rig's dock width, which took 19 px off each end: "LOCAL" reached the
        owner's screen as ".OCAL" (queezz, 2026-09-15). Everything painted
        is measured from this rect, so nothing can fall outside the widget.
        """
        margin = self._pen_overhang
        half = min(self.width, max(self.rect().width() // 2 - margin, 2))
        radius = min(self.radius, max(self.rect().height() // 2 - margin, 1), half)
        center = self.rect().center()
        return QRect(center.x() - half, center.y() - radius, 2 * half, 2 * radius)

    def thumb_rect(self, checked=None):
        """The sliding part, which is also the box the label is drawn in."""
        if checked is None:
            checked = self.isChecked()
        track = self.track_rect()
        radius = track.height() // 2
        rect = QRect(
            track.left(), track.top(), track.width() // 2 + radius, track.height()
        )
        if checked:
            rect.moveRight(track.right())
        return rect

    # MARK: the word on the switch
    def _label_fit(self, checked=None):
        """The font for both labels and, if need be, a narrowing of the word.

        The label is drawn inside the sliding part and Qt clips it there, so
        a word wider than that part arrives with its ends cut off: "REMOTE"
        reached the rig's screen as "EMOT" (queezz, 2026-09-05), and "Exp OFF"
        had been reading as "p OF" for as long as it has existed. Both of a
        switch's labels are measured together, so the word does not change
        size when the switch is thrown, and a label that already fits its
        switch is left at the size it always had.

        The room is taken from `thumb_rect`, which is taken from the widget's
        real width, so a switch squeezed by its column shrinks its word
        instead of painting it off the edge. Below six point a word stops
        being readable at arm's length from the rig, so what is left over at
        that size is taken out of the word's width instead: no font this is
        ever given can make a label leave the switch, and a narrowed word is
        still a whole one, where a clipped word is not.
        """
        room = max(self.thumb_rect(checked).width() - 2 * self._label_padding, 1)
        font = QtGui.QFont(self.font())
        size = font.pointSize()
        if size <= 0:
            size = QtGui.QFontInfo(font).pointSize() or 10
        while True:
            font.setPointSize(size)
            metrics = QtGui.QFontMetrics(font)
            widest = max(metrics.boundingRect(word).width() for word in self.labels)
            if widest <= room or size <= 6:
                break
            size -= 1
        squeeze = 1.0 if widest <= room else room / widest
        return font, squeeze

    def label_font(self, checked=None):
        """The font one state's word is painted in."""
        return self._label_fit(checked)[0]

    def label_rect(self, checked=None):
        """Where one state's word lands, in the widget's own coordinates.

        The same measurement `paintEvent` draws with, so a test can hold it
        inside `rect()` and catch a clipped label without looking at pixels.
        """
        if checked is None:
            checked = self.isChecked()
        label = self.labels[0] if checked else self.labels[1]
        thumb = self.thumb_rect(checked)
        font, squeeze = self._label_fit(checked)
        rect = QtGui.QFontMetrics(font).boundingRect(thumb, Qt.AlignCenter, label)
        if squeeze < 1.0:
            middle = thumb.center().x()
            left = middle + (rect.left() - middle) * squeeze
            # Rounded outwards at both ends: this rect is what a test holds
            # inside the widget, so it must never claim to be the smaller.
            edges = (math.floor(left), math.ceil(left + rect.width() * squeeze))
            rect = QRect(edges[0], rect.top(), edges[1] - edges[0], rect.height())
        return rect

    def paintEvent(self, event):
        checked = self.isChecked()
        label = self.labels[0] if checked else self.labels[1]
        bg_color = self.colors[0] if checked else self.colors[1]

        track = self.track_rect()
        thumb = self.thumb_rect(checked)
        radius = track.height() // 2

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor(0, 0, 0))

        pen = QtGui.QPen(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawRoundedRect(track, radius, radius)
        painter.setBrush(QtGui.QBrush(bg_color))
        painter.drawRoundedRect(thumb, radius, radius)

        font, squeeze = self._label_fit(checked)
        painter.setFont(font)
        if squeeze < 1.0:
            # Narrow the word about the middle of the sliding part, so it
            # stays centred where it was and only loses width.
            middle = thumb.center().x()
            painter.translate(middle, 0)
            painter.scale(squeeze, 1.0)
            painter.translate(-middle, 0)
        painter.drawText(thumb, Qt.AlignCenter, label)

    def hitButton(self, pos: QPoint):
        return self.track_rect().contains(pos)


class OnOffSwitch(MySwitch):
    radius = 15
    width = 40
    # 0 - On, 1 - Off
    labels = ["ON", "OFF"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class RemoteSwitch(MySwitch):
    """Whether a browser on the lab network may change a setpoint.

    Off is the resting state and the safe one: with this switch off the web
    view can only read, exactly as it did before browser control existed. It
    is a switch on the rig's own screen on purpose — gas flow and cathode
    current move on it, so a person standing at the rig decides.
    """

    # Wider than the on/off switch because its words are longer: a sliding
    # part of 88 px for a "LOCAL" of 80 on the rig's own font. It is a wish,
    # not a promise — the top row of the Control dock is narrower than this
    # at the dock's usual width, and the switch is painted at whatever it is
    # actually given, with the word shrunk to match.
    radius = 14
    width = 74

    labels = ["REMOTE", "LOCAL"]
    colors = [QtGui.QColor("#e0a63a"), QtGui.QColor("#b89c76")]


class ToggleCurrentPlot(MySwitch):
    radius = 15
    width = 30
    # 0 - On, 1 - Off
    labels = ["Ip", "no Ip"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class ToggleTemperaturePlot(MySwitch):
    radius = 15
    width = 30
    # 0 - On, 1 - Off
    labels = ["T", "no T"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class TogglePressurePlot(MySwitch):
    radius = 15
    width = 30
    # 0 - On, 1 - Off
    labels = ["P", "no P"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class changeScale(MySwitch):
    radius = 15
    width = 30
    # 0 - On, 1 - Off
    labels = ["auto", "levels"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class QmsSwitch(MySwitch):
    radius = 14
    width = 40

    labels = ["Exp ON", "Exp OFF"]
    colors = [QtGui.QColor("#33CCFF"), QtGui.QColor("#b89c76")]


class ToggleBaratronPlot(MySwitch):
    radius = 15
    width = 36
    # 0 - On, 1 - Off
    labels = ["Bartrn", "no B"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class ToggleIGPlots(MySwitch):
    """Toggle lines with IG and Pfeiffer"""

    radius = 15
    width = 36
    # 0 - On, 1 - Off
    labels = ["IGs", "no IGs"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


class ToggleYLogScale(MySwitch):
    radius = 15
    width = 30
    # 0 - On, 1 - Off
    labels = ["Log Y", "Lin Y"]
    colors = [QtGui.QColor("#8df01d"), QtGui.QColor("#b89c76")]


if __name__ == "__main__":
    pass
