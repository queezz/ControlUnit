"""The lab's word, as this machine happens to hold it.

A fence, not a lock. The roster answers *what shall the log call you*; the
Remote switch on the rig answers *may the network move anything at all*.
This answers a smaller question the owner asked on 2026-09-07 — "let's add
`plasmabox` word just in case. Not security, just a fence one can walk over.
Fence is enough." — which is: has whoever is pressing been in the lab. A
word said in the room keeps "oh, I found this webui, let's push some
buttons" from becoming a gas line moving, and nothing more. It is never
anybody's password, it is never hashed, and it is compared as plain text
because a fence one may walk over is exactly what was asked for.

The word lives on the machine that serves the page and never in git,
`~/.controlunit/fence.txt`, beside the roster and the neighbours file::

    plasmabox

One line, the word, surrounding whitespace stripped. **An absent or empty
file means no fence**, so every off-rig dummy run and every test behaves
exactly as it did before unless it writes that file; only a machine that
holds a word asks for one.

Every failure means the same thing here — this machine has no fence — and
setting stays gated by the switch and the operator lock alone. A missing
file, a folder in its place, an unreadable one, bytes that are not text,
and a file holding only blank lines are all read as no word rather than as
an error: nothing here may raise into a request.
"""

import time
from pathlib import Path

from controlunit.web.neighbours import settings_home

FENCE_FILE = "fence.txt"

#: How often the file on disk may be looked at. Every gated request asks the
#: fence what it is; one `stat` per press is fine, one per poll is not.
REREAD_SECONDS = 1.0


def fence_path(home=None):
    """Where this machine keeps the lab's word."""
    return (settings_home() if home is None else Path(home)) / FENCE_FILE


def read_fence(home=None):
    """The word this machine holds, or an empty string when it holds none.

    An empty string is the answer to every kind of absence; see the module
    docstring for the list of them. This never raises.
    """
    try:
        text = fence_path(home).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""
    # One line, whatever the file was saved with: a trailing newline from an
    # editor, or a leading blank one, must not become part of the word.
    lines = text.strip().splitlines()
    return lines[0].strip() if lines else ""


class Fence:
    """The word this machine knows, reread when the file underneath changes.

    The same shape as `roster.Roster`, and for the same reason: the file is
    compared by `(mtime_ns, size)` rather than by its contents, so a word
    that has not been changed costs one `stat` and no read; and it is not
    looked at more than once a second, so a page polling hard does not turn
    into a stat call per request.
    """

    def __init__(self, home=None, clock=time.monotonic):
        self._home = home
        self._clock = clock
        self._word = ""
        self._stamp = None
        self._looked_at = None

    def _fingerprint(self):
        """What says the file has changed, or None when there is no file."""
        try:
            status = fence_path(self._home).stat()
        except OSError:
            return None
        return (status.st_mtime_ns, status.st_size)

    def word(self):
        """The lab's word; empty when this machine has no fence."""
        now = self._clock()
        if self._looked_at is not None and (now - self._looked_at) < REREAD_SECONDS:
            return self._word
        self._looked_at = now
        stamp = self._fingerprint()
        if stamp != self._stamp:
            self._stamp = stamp
            self._word = read_fence(self._home)
        return self._word

    def needed(self):
        """True when this machine holds a word and so asks for one."""
        return bool(self.word())

    def opens(self, given):
        """True when what a browser typed is the word this machine holds.

        Plain string equality after stripping. It is a fence, not a secret:
        there is nothing here to hash and nothing worth a constant-time
        comparison, and pretending otherwise would only suggest the word
        protects more than it does.
        """
        word = self.word()
        return bool(word) and str(given or "").strip() == word
