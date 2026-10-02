"""What the rig's own screen remembers of a run.

The data file is the record; this is only what the window draws and what a
baseline averages over. It used to be one pandas frame that every delivery
copied whole, so a delivery cost as much as the run was long: on the run
started 2026-09-30 at 0.1 s the main thread needed 1.3 s for work that
arrived every 0.3 s, fell 25 hours behind, and the rows waiting behind it
were lost when the frozen program was killed (2026-10-02).

Here a delivery costs what it brings. Columns are plain arrays filled in
place, and the store is bounded: when it is full the older half is thinned
to every second row, so a long run stays on the screen whole, at a
resolution that falls with age, and never grows past `MAX_ROWS`.
"""

import numpy as np
import pandas as pd

#: Rows kept at most. At the rig's fast 0.1 s this is five and a half hours
#: at full resolution; at 10 s it is three weeks.
MAX_ROWS = 200_000

#: The first allocation; the store doubles from here up to `MAX_ROWS`.
FIRST_ROWS = 4096

DATE = "datetime64[ns]"


class RunHistory:
    """A bounded, columnar memory of one device's delivered rows."""

    def __init__(self, max_rows=MAX_ROWS):
        self.max_rows = max(2, int(max_rows))
        self._columns = {}
        self._rows = 0
        self._capacity = 0
        #: How many times the older half has been thinned; a test and the
        #: log can tell a full-resolution history from a thinned one.
        self.thinned = 0

    def __len__(self):
        return self._rows

    @property
    def empty(self):
        return self._rows == 0

    @property
    def columns(self):
        return list(self._columns)

    def clear(self):
        """Forget the run. The arrays are dropped, not just emptied, so the
        next run's first batch decides the columns again."""
        self._columns = {}
        self._rows = 0
        self._capacity = 0
        self.thinned = 0

    # -- writing -------------------------------------------------------------

    @staticmethod
    def _as_array(series):
        """One batch column as an array this store can hold, or None."""
        if pd.api.types.is_datetime64_any_dtype(series):
            return series.to_numpy(dtype=DATE)
        try:
            return series.to_numpy(dtype=float)
        except (TypeError, ValueError):
            return None

    def _allocate(self, arrays):
        self._capacity = min(self.max_rows, FIRST_ROWS)
        self._columns = {
            name: np.empty(self._capacity, dtype=values.dtype)
            for name, values in arrays.items()
        }

    def _make_room(self, incoming):
        """Grow up to the bound, then thin the older half, until it fits."""
        while self._rows + incoming > self._capacity:
            if self._capacity < self.max_rows:
                capacity = min(self.max_rows, self._capacity * 2)
                for name, store in self._columns.items():
                    grown = np.empty(capacity, dtype=store.dtype)
                    grown[: self._rows] = store[: self._rows]
                    self._columns[name] = grown
                self._capacity = capacity
                continue
            half = self._rows // 2
            keep = np.concatenate(
                (np.arange(0, half, 2), np.arange(half, self._rows))
            )
            for store in self._columns.values():
                store[: keep.size] = store[keep]
            self._rows = int(keep.size)
            self.thinned += 1

    def append(self, frame):
        """Add one delivered batch. Columns the first batch did not have,
        and columns that are not numbers or times, are left out."""
        count = len(frame)
        if not count:
            return
        arrays = {}
        for name in frame.columns:
            values = self._as_array(frame[name])
            if values is not None:
                arrays[name] = values
        if not self._columns:
            self._allocate(arrays)
        if count > self.max_rows:
            arrays = {name: values[-self.max_rows:] for name, values in arrays.items()}
            count = self.max_rows
        self._make_room(count)
        end = self._rows + count
        for name, store in self._columns.items():
            if name in arrays:
                store[self._rows:end] = arrays[name]
            elif store.dtype.kind == "f":
                store[self._rows:end] = np.nan
        self._rows = end

    # -- reading -------------------------------------------------------------

    def column(self, name):
        """Every kept row of one column, oldest first; a view, not a copy."""
        return self._columns[name][: self._rows]

    def tail(self, name, rows):
        """The last `rows` rows of one column."""
        return self.column(name)[max(0, self._rows - max(0, int(rows))):]

    def view(self, seconds=0, max_points=3000, time_column="date"):
        """The last `seconds` of the run (all of it for zero or less),
        thinned to about `max_points` rows: a dict of column views.

        The window is found by bisection on the time column and the
        thinning is a stride, so the cost does not grow with the run.
        """
        start = 0
        if seconds and seconds > 0 and self._rows and time_column in self._columns:
            stamps = self.column(time_column)
            cutoff = stamps[-1] - np.timedelta64(int(round(seconds * 1e9)), "ns")
            start = int(np.searchsorted(stamps, cutoff, side="right"))
        rows = self._rows - start
        step = 1
        if max_points and rows > max_points:
            step = rows // int(max_points) + 1
        return {
            name: store[start:self._rows:step] for name, store in self._columns.items()
        }
