"""Timezone utilities — replaces dateutil.tz, built on stdlib zoneinfo."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 backport
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# UTC singleton
# ---------------------------------------------------------------------------

UTC: tzinfo = timezone.utc
"""UTC timezone — singleton ``datetime.timezone.utc``."""


class tzutc(tzinfo):
    """UTC timezone class, compatible with dateutil.tz.tzutc.

    Provided for API compatibility; prefer using ``UTC`` directly.
    """

    _ZERO = timedelta(0)
    _instance: Optional[tzutc] = None

    def __new__(cls) -> tzutc:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        return self._ZERO

    def dst(self, dt: Optional[datetime]) -> timedelta:
        return self._ZERO

    def tzname(self, dt: Optional[datetime]) -> str:
        return "UTC"

    def __repr__(self) -> str:
        return "tzutc()"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tzutc):
            return True
        if other is timezone.utc:
            return True
        if isinstance(other, tzoffset) and other._offset == self._ZERO:
            return True
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.utcoffset(None))


# ---------------------------------------------------------------------------
# tzoffset — fixed offset timezone
# ---------------------------------------------------------------------------

class tzoffset(tzinfo):
    """Fixed-offset timezone.

    Parameters
    ----------
    name : str or None
        Timezone name (e.g. ``"EST"``).
    offset : int, float, or timedelta
        UTC offset in seconds (int/float) or as a timedelta.
    """

    def __init__(self, name: Optional[str], offset: Union[int, float, timedelta]) -> None:
        if isinstance(offset, timedelta):
            self._offset = offset
        else:
            self._offset = timedelta(seconds=int(offset))
        self._name = name or f"UTC{self._format_offset()}"

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        return self._offset

    def dst(self, dt: Optional[datetime]) -> timedelta:
        return timedelta(0)

    def tzname(self, dt: Optional[datetime]) -> str:
        return self._name

    def _format_offset(self) -> str:
        total = int(self._offset.total_seconds())
        sign = "+" if total >= 0 else "-"
        total = abs(total)
        hours, remainder = divmod(total, 3600)
        minutes = remainder // 60
        if minutes:
            return f"{sign}{hours:02d}:{minutes:02d}"
        return f"{sign}{hours:02d}"

    def __repr__(self) -> str:
        return f"tzoffset({self._name!r}, {int(self._offset.total_seconds())})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tzoffset):
            return self._offset == other._offset
        if isinstance(other, tzutc) and self._offset == timedelta(0):
            return True
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._offset)


# ---------------------------------------------------------------------------
# tzlocal — system local timezone
# ---------------------------------------------------------------------------

class tzlocal(tzinfo):
    """Local system timezone.

    Wraps the system's local timezone, detecting UTC offset and DST
    from the C library's ``time.localtime()``.
    """

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        if dt is None:
            # Use current time to determine offset.
            tt = time.localtime()
        else:
            # Convert dt to a timestamp-like value for localtime.
            try:
                stamp = dt.replace(tzinfo=None).timestamp()  # type: ignore[call-overload]
            except (OSError, OverflowError, ValueError):
                try:
                    stamp = time.mktime(dt.replace(tzinfo=None).timetuple())
                except (OSError, OverflowError, ValueError):
                    # Extreme datetime (e.g. datetime.min) — fall back to
                    # current local offset.
                    return timedelta(seconds=time.localtime().tm_gmtoff)
            tt = time.localtime(stamp)
        return timedelta(seconds=tt.tm_gmtoff)

    def dst(self, dt: Optional[datetime]) -> timedelta:
        if dt is None:
            tt = time.localtime()
        else:
            try:
                stamp = dt.replace(tzinfo=None).timestamp()  # type: ignore[call-overload]
            except (OSError, OverflowError, ValueError):
                try:
                    stamp = time.mktime(dt.replace(tzinfo=None).timetuple())
                except (OSError, OverflowError, ValueError):
                    # Extreme datetime — fall back to current DST info.
                    tt = time.localtime()
                    if tt.tm_isdst > 0:
                        std_offset = -(time.timezone)
                        dst_offset = tt.tm_gmtoff
                        return timedelta(seconds=dst_offset - std_offset)
                    return timedelta(0)
            tt = time.localtime(stamp)
        if tt.tm_isdst > 0:
            std_offset = -(time.timezone)
            dst_offset = tt.tm_gmtoff
            return timedelta(seconds=dst_offset - std_offset)
        return timedelta(0)

    def tzname(self, dt: Optional[datetime]) -> str:
        if dt is None:
            return time.tzname[0]
        try:
            stamp = dt.replace(tzinfo=None).timestamp()  # type: ignore[call-overload]
        except (OSError, OverflowError, ValueError):
            try:
                stamp = time.mktime(dt.replace(tzinfo=None).timetuple())
            except (OSError, OverflowError, ValueError):
                # Extreme datetime — fall back to current tzname.
                return time.tzname[0]
        tt = time.localtime(stamp)
        return time.tzname[1] if tt.tm_isdst > 0 else time.tzname[0]

    def __repr__(self) -> str:
        return "tzlocal()"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tzlocal):
            return True
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("tzlocal",))


# ---------------------------------------------------------------------------
# gettz — timezone lookup by name
# ---------------------------------------------------------------------------

def gettz(name: Optional[str] = None) -> Optional[tzinfo]:
    """Get a timezone by IANA name.

    Parameters
    ----------
    name : str or None
        IANA timezone name (e.g. ``"America/New_York"``), or ``None``
        for the local timezone.

    Returns
    -------
    tzinfo or None
        A tzinfo instance, or ``None`` if the name is not recognized.
    """
    if name is None:
        return tzlocal()

    # Normalize common aliases.
    upper = name.upper()
    if upper == "UTC" or upper == "GMT":
        return UTC

    if upper == "LOCAL":
        return tzlocal()

    try:
        return ZoneInfo(name)
    except (KeyError, Exception):
        return None


# ---------------------------------------------------------------------------
# DST helpers
# ---------------------------------------------------------------------------

def enfold(dt: datetime, fold: int = 1) -> datetime:
    """Return *dt* with the ``fold`` attribute set to *fold*.

    This is useful for disambiguating times during fall-back DST
    transitions (PEP 495).
    """
    return dt.replace(fold=fold)


def resolve_imaginary(dt: datetime) -> datetime:
    """If *dt* falls in a spring-forward DST gap, shift it forward.

    If *dt* is not imaginary (i.e., it exists), return it unchanged.
    """
    if dt.tzinfo is None:
        return dt

    # A time is imaginary if the UTC offset differs between fold=0 and fold=1
    # in a way that makes the wall time non-existent.
    offset0 = dt.replace(fold=0).utcoffset()
    offset1 = dt.replace(fold=1).utcoffset()

    if offset0 is None or offset1 is None:
        return dt

    if offset0 == offset1:
        return dt  # Not in a transition.

    # In a gap, fold=0 gives the pre-transition offset and fold=1 gives the
    # post-transition offset. The gap width is the difference.
    gap = offset1 - offset0

    if gap > timedelta(0):
        # Fall-back (overlap, not a gap) — offset1 < offset0 in fall-back.
        # Actually if gap > 0, it means offset1 > offset0 which is spring-forward.
        # Spring-forward: wall clock jumps ahead. The imaginary time should be
        # shifted forward by the gap amount.
        return dt + gap
    else:
        # gap < 0 means fall-back overlap, dt exists, return unchanged.
        return dt


def datetime_exists(dt: datetime, tz: Optional[tzinfo] = None) -> bool:
    """Return ``False`` if *dt* is in a spring-forward DST gap.

    A time is "imaginary" (non-existent) if the local clock skips over
    it during a DST transition.

    Parameters
    ----------
    dt : datetime
        The datetime to check.
    tz : tzinfo or None
        If provided and *dt* is naive, attach this timezone before checking.
    """
    if tz is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    if dt.tzinfo is None:
        return True

    # A non-existent time: fold=0 and fold=1 produce different offsets,
    # and the fold=1 offset is larger (spring-forward).
    offset0 = dt.replace(fold=0).utcoffset()
    offset1 = dt.replace(fold=1).utcoffset()

    if offset0 is None or offset1 is None:
        return True

    if offset0 == offset1:
        return True

    # In a spring-forward gap, offset1 > offset0.
    # In a fall-back overlap, offset0 > offset1.
    # If offset1 > offset0, the time doesn't exist.
    return offset1 <= offset0


def datetime_ambiguous(dt: datetime, tz: Optional[tzinfo] = None) -> bool:
    """Return ``True`` if *dt* is in a fall-back DST overlap.

    An ambiguous time occurs twice during the fall-back transition.

    Parameters
    ----------
    dt : datetime
        The datetime to check.
    tz : tzinfo or None
        If provided and *dt* is naive, attach this timezone before checking.
    """
    if tz is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    if dt.tzinfo is None:
        return False

    offset0 = dt.replace(fold=0).utcoffset()
    offset1 = dt.replace(fold=1).utcoffset()

    if offset0 is None or offset1 is None:
        return False

    # Ambiguous if the offsets differ and offset0 > offset1 (fall-back).
    return offset0 != offset1 and offset0 > offset1
