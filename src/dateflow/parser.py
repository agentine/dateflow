"""Date string parser — replaces dateutil.parser.parse with a zero-dependency implementation."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional, Tuple, Union

from dateflow.tz import tzoffset, tzutc


class ParserError(ValueError):
    """Raised when a date string cannot be parsed."""
    pass


# ---------------------------------------------------------------------------
# Month / weekday / AMPM name tables
# ---------------------------------------------------------------------------

_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_AMPM = {"am": "am", "a.m.": "am", "pm": "pm", "p.m.": "pm"}

_WEEKDAYS = frozenset({
    "mon", "monday", "tue", "tues", "tuesday",
    "wed", "wednesday", "thu", "thur", "thurs", "thursday",
    "fri", "friday", "sat", "saturday", "sun", "sunday",
})

# Ordinal suffixes that can appear after day numbers
_ORDINAL_SUFFIXES = frozenset({"st", "nd", "rd", "th"})

# Filler words commonly found in date strings
_FILLER_WORDS = frozenset({"of", "the", "at", "on"})

# Common timezone abbreviations -> UTC offset in seconds
_TZ_ABBREVS = {
    "UTC": 0,
    "GMT": 0,
    "Z": 0,
    "EST": -18000,   # -5h
    "EDT": -14400,   # -4h
    "CST": -21600,   # -6h
    "CDT": -18000,   # -5h
    "MST": -25200,   # -7h
    "MDT": -21600,   # -6h
    "PST": -28800,   # -8h
    "PDT": -25200,   # -7h
    "IST": 19800,    # +5:30
    "CET": 3600,     # +1h
    "CEST": 7200,    # +2h
    "EET": 7200,     # +2h
    "EEST": 10800,   # +3h
    "JST": 32400,    # +9h
    "KST": 32400,    # +9h
    "AEST": 36000,   # +10h
    "AEDT": 39600,   # +11h
    "NZST": 43200,   # +12h
    "NZDT": 46800,   # +13h
    "HST": -36000,   # -10h
    "AKST": -32400,  # -9h
    "AKDT": -28800,  # -8h
    "AST": -14400,   # -4h (Atlantic)
    "NST": -12600,   # -3:30 (Newfoundland)
    "NDT": -9000,    # -2:30 (Newfoundland Daylight)
}

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<number>\d+)                    # integer
    | (?P<word>[A-Za-z]+\.?)           # word (optionally ending with .)
    | (?P<sep>[/.:,T])                 # separator character (not - or +)
    | (?P<sign>[+\-])                  # sign (also used as date separator)
    | (?P<ws>\s+)                      # whitespace
    | (?P<other>.)                     # anything else
    """,
    re.VERBOSE,
)


def _tokenize(s: str) -> list[tuple[str, str]]:
    """Return a list of (type, value) tokens from the date string."""
    tokens = []
    for m in _TOKEN_RE.finditer(s):
        for name in ("number", "word", "sep", "sign", "ws", "other"):
            val = m.group(name)
            if val is not None:
                tokens.append((name, val))
                break
    return tokens


# ---------------------------------------------------------------------------
# Internal result accumulator
# ---------------------------------------------------------------------------

class _DateComponents:
    """Accumulates parsed date/time components."""

    __slots__ = (
        "year", "month", "day",
        "hour", "minute", "second", "microsecond",
        "tzinfo", "ampm",
    )

    def __init__(self) -> None:
        self.year: Optional[int] = None
        self.month: Optional[int] = None
        self.day: Optional[int] = None
        self.hour: Optional[int] = None
        self.minute: Optional[int] = None
        self.second: Optional[int] = None
        self.microsecond: Optional[int] = None
        self.tzinfo: Optional[tzinfo] = None
        self.ampm: Optional[str] = None

    def has_date(self) -> bool:
        return self.year is not None or self.month is not None or self.day is not None

    def has_time(self) -> bool:
        return self.hour is not None

    def to_datetime(self, default: datetime) -> datetime:
        year = self.year if self.year is not None else default.year
        month = self.month if self.month is not None else default.month
        day = self.day if self.day is not None else default.day
        hour = self.hour if self.hour is not None else default.hour
        minute = self.minute if self.minute is not None else default.minute
        second = self.second if self.second is not None else default.second
        microsecond = self.microsecond if self.microsecond is not None else default.microsecond

        # Apply AM/PM
        if self.ampm == "pm" and hour is not None and hour < 12:
            hour += 12
        elif self.ampm == "am" and hour is not None and hour == 12:
            hour = 0

        # If the parsed string had no timezone but the default does, propagate it
        tz = self.tzinfo if self.tzinfo is not None else default.tzinfo

        return datetime(
            year, month, day, hour, minute, second, microsecond,
            tzinfo=tz,
        )


# ---------------------------------------------------------------------------
# ISO 8601 fast path
# ---------------------------------------------------------------------------

_ISO_FULL_RE = re.compile(
    r"^(\d{4})-(\d{1,2})-(\d{1,2})"
    r"(?:[T ](\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?"
    r"(Z|[+\-]\d{2}:?\d{2})?"
    r")?$"
)


def _try_iso(s: str) -> Optional[_DateComponents]:
    """Attempt a fast ISO 8601 parse."""
    m = _ISO_FULL_RE.match(s)
    if m is None:
        return None

    comp = _DateComponents()
    comp.year = int(m.group(1))
    comp.month = int(m.group(2))
    comp.day = int(m.group(3))

    if m.group(4) is not None:
        comp.hour = int(m.group(4))
        comp.minute = int(m.group(5))
        if m.group(6) is not None:
            comp.second = int(m.group(6))
        if m.group(7) is not None:
            frac = m.group(7)
            frac = frac[:6].ljust(6, "0")
            comp.microsecond = int(frac)
        if m.group(8) is not None:
            tz_str = m.group(8)
            if tz_str == "Z":
                comp.tzinfo = tzutc()
            else:
                sign = 1 if tz_str[0] == "+" else -1
                tz_str = tz_str[1:]
                if ":" in tz_str:
                    parts = tz_str.split(":")
                    hours = int(parts[0])
                    minutes = int(parts[1])
                else:
                    hours = int(tz_str[:2])
                    minutes = int(tz_str[2:4]) if len(tz_str) >= 4 else 0
                total = sign * (hours * 3600 + minutes * 60)
                comp.tzinfo = tzoffset(None, total)

    return comp


# ---------------------------------------------------------------------------
# Token-based parser
# ---------------------------------------------------------------------------

class _TokenStream:
    """Provides lookahead over a list of non-whitespace tokens."""

    def __init__(self, raw_tokens: list[tuple[str, str]]) -> None:
        # Keep the original tokens for skip tracking
        self._raw = raw_tokens
        # Build clean (non-whitespace) list with original indices
        self._clean: list[tuple[int, str, str]] = []
        for i, (ttype, tval) in enumerate(raw_tokens):
            if ttype != "ws":
                self._clean.append((i, ttype, tval))
        self.pos = 0
        self.consumed: set[int] = set()

    def __len__(self) -> int:
        return len(self._clean)

    @property
    def remaining(self) -> int:
        return len(self._clean) - self.pos

    def peek(self, offset: int = 0) -> Optional[tuple[int, str, str]]:
        idx = self.pos + offset
        if 0 <= idx < len(self._clean):
            return self._clean[idx]
        return None

    def advance(self, count: int = 1) -> None:
        for _ in range(count):
            if self.pos < len(self._clean):
                self.consumed.add(self._clean[self.pos][0])
                self.pos += 1

    def consume_at(self, offset: int) -> None:
        idx = self.pos + offset
        if 0 <= idx < len(self._clean):
            self.consumed.add(self._clean[idx][0])

    def at_end(self) -> bool:
        return self.pos >= len(self._clean)

    def skipped_tokens(self) -> list[str]:
        result = []
        for i, (ttype, tval) in enumerate(self._raw):
            if i not in self.consumed and ttype != "ws":
                result.append(tval)
        return result


def _parse_numeric_offset(stream: _TokenStream) -> Optional[tzinfo]:
    """Try to parse a numeric UTC offset at stream.pos (expects sign token).

    Returns None without advancing the stream if the offset is out of range
    (hours > 23 or minutes > 59), so the tokens can be interpreted as date
    components instead.
    """
    p = stream.peek()
    if p is None or p[1] != "sign":
        return None

    sign_char = p[2]
    sign = 1 if sign_char == "+" else -1

    p1 = stream.peek(1)
    if p1 is None or p1[1] != "number":
        return None

    num_str = p1[2]

    # Check for colon-separated form: +05:30
    p2 = stream.peek(2)
    p3 = stream.peek(3)

    if (p2 is not None and p2[1] == "sep" and p2[2] == ":"
            and p3 is not None and p3[1] == "number"):
        hours = int(num_str)
        minutes = int(p3[2])
        # Validate range before advancing
        if hours > 23 or minutes > 59:
            return None
        stream.advance(4)
    else:
        num = int(num_str)
        if len(num_str) <= 2:
            hours = num
            minutes = 0
        else:
            hours = num // 100
            minutes = num % 100
        # Validate range before advancing
        if hours > 23 or minutes > 59:
            return None
        stream.advance(2)

    total_seconds = sign * (hours * 3600 + minutes * 60)
    return tzoffset(None, total_seconds)


def _parse_tokens(
    raw_tokens: list[tuple[str, str]],
    dayfirst: bool = False,
    yearfirst: bool = False,
) -> tuple[_DateComponents, list[str]]:
    """Parse tokens into date components. Return (components, skipped_tokens)."""

    comp = _DateComponents()
    stream = _TokenStream(raw_tokens)
    date_numbers: list[int] = []

    while not stream.at_end():
        p = stream.peek()
        assert p is not None
        orig_idx, ttype, tval = p

        # ----- Word tokens -----
        if ttype == "word":
            lower = tval.lower().rstrip(".")

            # Month name
            if lower in _MONTH_NAMES and comp.month is None:
                comp.month = _MONTH_NAMES[lower]
                stream.advance()
                # Consume a following dash used as date separator (e.g. Jan-15-2024)
                ps = stream.peek()
                if ps is not None and ps[1] == "sign" and ps[2] == "-":
                    ps2 = stream.peek(1)
                    if ps2 is not None and ps2[1] == "number":
                        stream.advance()
                continue

            # AM/PM
            if lower in _AMPM:
                comp.ampm = _AMPM[lower]
                stream.advance()
                continue

            # Dotted AM/PM: "a.m." / "p.m." tokenized as "a." + "m."
            if lower in ("a", "p"):
                pnext = stream.peek(1)
                if pnext is not None and pnext[1] == "word" and pnext[2].lower().rstrip(".") == "m":
                    comp.ampm = "am" if lower == "a" else "pm"
                    stream.advance(2)
                    continue

            # Ordinal suffix after a day number
            if lower in _ORDINAL_SUFFIXES:
                stream.advance()
                continue

            # Filler word
            if lower in _FILLER_WORDS:
                stream.advance()
                continue

            # Weekday name — consume silently
            if lower in _WEEKDAYS:
                stream.advance()
                continue

            # Timezone abbreviation
            upper = tval.upper().rstrip(".")
            if upper in _TZ_ABBREVS and comp.tzinfo is None:
                offset = _TZ_ABBREVS[upper]
                if offset == 0:
                    comp.tzinfo = tzutc()
                else:
                    comp.tzinfo = tzoffset(upper, offset)
                stream.advance()
                continue

            # 'T' as ISO separator
            if upper == "T" and len(tval) == 1:
                stream.advance()
                continue

            # Unknown word — don't consume (will become a skipped token)
            stream.pos += 1
            continue

        # ----- 'T' separator -----
        if ttype == "sep" and tval == "T":
            stream.advance()
            continue

        # ----- Time pattern: N:N[:N[.N]] -----
        if ttype == "number" and comp.hour is None:
            p1 = stream.peek(1)
            p2 = stream.peek(2)
            if (p1 is not None and p1[1] == "sep" and p1[2] == ":"
                    and p2 is not None and p2[1] == "number"):
                # This is a time
                comp.hour = int(tval)
                comp.minute = int(p2[2])
                stream.advance(3)

                # Seconds?
                ps = stream.peek()
                ps1 = stream.peek(1)
                if (ps is not None and ps[1] == "sep" and ps[2] == ":"
                        and ps1 is not None and ps1[1] == "number"):
                    sec_str = ps1[2]
                    comp.second = int(sec_str)
                    stream.advance(2)

                    # Fractional seconds? (.NNNNNN)
                    pf = stream.peek()
                    pf1 = stream.peek(1)
                    if (pf is not None and pf[1] == "sep" and pf[2] == "."
                            and pf1 is not None and pf1[1] == "number"):
                        frac = pf1[2][:6].ljust(6, "0")
                        comp.microsecond = int(frac)
                        stream.advance(2)

                # Timezone offset after time?
                pt = stream.peek()
                if pt is not None and pt[1] == "sign" and comp.tzinfo is None:
                    tz = _parse_numeric_offset(stream)
                    if tz is not None:
                        comp.tzinfo = tz
                elif pt is not None and pt[1] == "word" and pt[2].upper() == "Z":
                    comp.tzinfo = tzutc()
                    stream.advance()

                continue

        # ----- Bare number + AM/PM (e.g. "3pm", "3 pm", "11am") -----
        if ttype == "number" and comp.hour is None:
            # Check if the next non-ws token is an AM/PM word
            p1 = stream.peek(1)
            if p1 is not None and p1[1] == "word" and p1[2].lower().rstrip(".") in _AMPM:
                comp.hour = int(tval)
                comp.minute = 0
                comp.ampm = _AMPM[p1[2].lower().rstrip(".")]
                stream.advance(2)
                continue

        # ----- Standalone offset sign -----
        if ttype == "sign" and comp.tzinfo is None:
            tz = _parse_numeric_offset(stream)
            if tz is not None:
                comp.tzinfo = tz
                continue
            # If parsing failed, _parse_numeric_offset didn't advance
            stream.pos += 1
            continue

        # ----- Number (potential date component) -----
        if ttype == "number":
            date_numbers.append(int(tval))
            stream.advance()

            # Consume a following date separator (- / .)
            ps = stream.peek()
            if ps is not None and ps[1] == "sep" and ps[2] in "/.":
                stream.advance()
            # Consume a following dash (sign token used as date separator)
            elif ps is not None and ps[1] == "sign" and ps[2] == "-":
                # Only treat as separator if followed by a number or month word (date context)
                ps2 = stream.peek(1)
                if ps2 is not None and (
                    ps2[1] == "number"
                    or (ps2[1] == "word" and ps2[2].lower().rstrip(".") in _MONTH_NAMES)
                ):
                    stream.advance()
            # Also consume a following comma
            elif ps is not None and ps[1] == "sep" and ps[2] == ",":
                stream.advance()
            continue

        # ----- Other separators -----
        if ttype == "sep":
            stream.advance()
            continue

        # ----- Anything else -----
        stream.pos += 1

    # Resolve date numbers
    _resolve_date_numbers(comp, date_numbers, dayfirst, yearfirst)

    return comp, stream.skipped_tokens()


def _resolve_date_numbers(
    comp: _DateComponents,
    numbers: list[int],
    dayfirst: bool,
    yearfirst: bool,
) -> None:
    """Assign year/month/day from collected date numbers."""
    if not numbers:
        return

    # If month is already set (from a month name), we need fewer numbers
    if comp.month is not None:
        if len(numbers) == 1:
            val = numbers[0]
            if val > 31:
                comp.year = _fix_year(val)
            else:
                comp.day = val
        elif len(numbers) >= 2:
            a, b = numbers[0], numbers[1]
            if a > 31:
                comp.year = _fix_year(a)
                comp.day = b
            elif b > 31:
                comp.day = a
                comp.year = _fix_year(b)
            else:
                # Ambiguous: both could be day or year
                # Convention: first is day, second is year (most natural with month name)
                comp.day = a
                comp.year = _fix_year(b)
        return

    # No month name
    if len(numbers) == 1:
        val = numbers[0]
        if val > 31:
            comp.year = _fix_year(val)
        elif val > 12:
            comp.day = val
        else:
            comp.day = val
        return

    if len(numbers) == 2:
        a, b = numbers[0], numbers[1]
        if a > 31:
            comp.year = _fix_year(a)
            comp.month = b
        elif b > 31:
            comp.month = a
            comp.year = _fix_year(b)
        elif a > 12 and b <= 12:
            comp.day = a
            comp.month = b
        elif b > 12 and a <= 12:
            comp.month = a
            comp.day = b
        else:
            if dayfirst:
                comp.day = a
                comp.month = b
            else:
                comp.month = a
                comp.day = b
        return

    if len(numbers) >= 3:
        a, b, c = numbers[0], numbers[1], numbers[2]

        if yearfirst:
            comp.year = _fix_year(a)
            if b > 12:
                comp.day = b
                comp.month = c
            elif c > 12:
                comp.month = b
                comp.day = c
            elif dayfirst:
                comp.day = b
                comp.month = c
            else:
                comp.month = b
                comp.day = c
        elif a > 31:
            # First number is year (ISO-like)
            comp.year = _fix_year(a)
            if dayfirst:
                comp.day = b
                comp.month = c
            else:
                comp.month = b
                comp.day = c
        elif c > 31:
            # Third number is year
            if dayfirst:
                comp.day = a
                comp.month = b
            else:
                comp.month = a
                comp.day = b
            comp.year = _fix_year(c)
        elif dayfirst:
            comp.day = a
            comp.month = b
            comp.year = _fix_year(c)
        else:
            comp.month = a
            comp.day = b
            comp.year = _fix_year(c)


def _fix_year(year: int) -> int:
    """Convert 2-digit year to 4-digit year. 4-digit years pass through."""
    if year >= 100:
        return year
    if year <= 68:
        return 2000 + year
    return 1900 + year


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(
    timestr: str,
    default: Optional[datetime] = None,
    dayfirst: bool = False,
    yearfirst: bool = False,
    fuzzy: bool = False,
    fuzzy_with_tokens: bool = False,
) -> Union[datetime, Tuple[datetime, Tuple[str, ...]]]:
    """Parse a date/time string into a :class:`datetime.datetime`.

    Parameters
    ----------
    timestr : str
        The date/time string to parse.
    default : datetime or None
        Default datetime used to fill in missing fields.  If ``None``,
        defaults to ``datetime.now()`` with time components set to zero.
    dayfirst : bool
        If ``True``, interpret the first ambiguous number as the day
        (DD/MM/YYYY vs MM/DD/YYYY).
    yearfirst : bool
        If ``True``, interpret the first ambiguous number as the year
        (YYYY/MM/DD).
    fuzzy : bool
        If ``True``, allow the string to contain non-date text that
        will be ignored.
    fuzzy_with_tokens : bool
        If ``True``, return a ``(datetime, tuple_of_skipped_tokens)``
        tuple.  Implies ``fuzzy=True``.

    Returns
    -------
    datetime or (datetime, tuple[str, ...])
        Parsed datetime; or a 2-tuple when *fuzzy_with_tokens* is ``True``.

    Raises
    ------
    ParserError
        When the string cannot be parsed.
    """
    if not isinstance(timestr, str):
        raise TypeError(
            f"Parser must be a string or character stream, not "
            f"{type(timestr).__name__}"
        )

    if default is None:
        default = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

    if fuzzy_with_tokens:
        fuzzy = True

    stripped = timestr.strip()
    if not stripped:
        raise ParserError(f"String does not contain a date: {timestr!r}")

    # Fast path for clean ISO 8601 (only in non-fuzzy mode)
    if not fuzzy:
        iso = _try_iso(stripped)
        if iso is not None:
            try:
                result = iso.to_datetime(default)
            except (ValueError, OverflowError) as exc:
                raise ParserError(
                    f"Invalid date values in {timestr!r}: {exc}"
                ) from exc
            if fuzzy_with_tokens:
                return result, ()
            return result

    # Tokenize and parse
    tokens = _tokenize(stripped)
    comp, skipped = _parse_tokens(tokens, dayfirst=dayfirst, yearfirst=yearfirst)

    # Validate that we found date or time information
    if not comp.has_date() and not comp.has_time():
        raise ParserError(f"String does not contain a date: {timestr!r}")

    # In non-fuzzy mode, reject strings with unrecognized tokens
    if not fuzzy and skipped:
        real_skipped = [
            s for s in skipped
            if s.lower() not in _ORDINAL_SUFFIXES | _FILLER_WORDS
        ]
        if real_skipped:
            raise ParserError(
                f"Unknown string format: {timestr!r} "
                f"(unrecognized tokens: {real_skipped})"
            )

    try:
        result = comp.to_datetime(default)
    except (ValueError, OverflowError) as exc:
        raise ParserError(
            f"Invalid date values in {timestr!r}: {exc}"
        ) from exc

    if fuzzy_with_tokens:
        return result, tuple(skipped)
    return result


# ---------------------------------------------------------------------------
# ISO 8601 strict parser (isoparse)
# ---------------------------------------------------------------------------

# Compact date: 20240115 (with optional time)
_ISO_COMPACT_RE = re.compile(
    r"^(\d{4})(\d{2})(\d{2})"
    r"(?:[T ](\d{2})(\d{2})(\d{2})(?:\.(\d+))?"
    r"(Z|[+\-]\d{2}:?\d{2})?"
    r")?$"
)

# Week date: 2024-W03, 2024-W03-1, 2024W03, 2024W031
_ISO_WEEK_RE = re.compile(
    r"^(\d{4})-?W(\d{2})(?:-?(\d))?$"
)

# Ordinal date: 2024-070 or 2024070
_ISO_ORDINAL_RE = re.compile(
    r"^(\d{4})-?(\d{3})$"
)


def _parse_iso_tz(tz_str: str) -> tzinfo:
    """Parse an ISO timezone suffix (Z or +/-HH:MM)."""
    if tz_str == "Z":
        return tzutc()
    sign = 1 if tz_str[0] == "+" else -1
    tz_str = tz_str[1:]
    if ":" in tz_str:
        parts = tz_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
    else:
        hours = int(tz_str[:2])
        minutes = int(tz_str[2:4]) if len(tz_str) >= 4 else 0
    total = sign * (hours * 3600 + minutes * 60)
    return tzoffset(None, total)


def isoparse(timestr: str) -> datetime:
    """Parse an ISO 8601 date/time string strictly.

    Supports:
    - Standard: ``2024-01-15``, ``2024-01-15T10:30:00``
    - Compact: ``20240115``, ``20240115T103000``
    - Week dates: ``2024-W03``, ``2024-W03-1``, ``2024W031``
    - Ordinal dates: ``2024-070``, ``2024070``

    Parameters
    ----------
    timestr : str
        An ISO 8601 date/time string.

    Returns
    -------
    datetime
        Parsed datetime.

    Raises
    ------
    ParserError
        When the string is not valid ISO 8601.
    """
    if not isinstance(timestr, str):
        raise TypeError(
            f"isoparse argument must be a string, not {type(timestr).__name__}"
        )

    stripped = timestr.strip()
    if not stripped:
        raise ParserError(f"String does not contain a date: {timestr!r}")

    # Try standard ISO 8601 (YYYY-MM-DD with optional time) via existing path
    m = _ISO_FULL_RE.match(stripped)
    if m is not None:
        comp = _try_iso(stripped)
        if comp is not None:
            default = datetime(1, 1, 1)
            try:
                return comp.to_datetime(default)
            except (ValueError, OverflowError) as exc:
                raise ParserError(
                    f"Invalid date values in {timestr!r}: {exc}"
                ) from exc

    # Compact format: 20240115 or 20240115T103000
    m = _ISO_COMPACT_RE.match(stripped)
    if m is not None:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        hour = int(m.group(4)) if m.group(4) is not None else 0
        minute = int(m.group(5)) if m.group(5) is not None else 0
        second = int(m.group(6)) if m.group(6) is not None else 0
        microsecond = 0
        if m.group(7) is not None:
            frac = m.group(7)[:6].ljust(6, "0")
            microsecond = int(frac)
        tz = None
        if m.group(8) is not None:
            tz = _parse_iso_tz(m.group(8))
        try:
            return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tz)
        except (ValueError, OverflowError) as exc:
            raise ParserError(
                f"Invalid date values in {timestr!r}: {exc}"
            ) from exc

    # Week date: 2024-W03, 2024-W03-1, 2024W03, 2024W031
    m = _ISO_WEEK_RE.match(stripped)
    if m is not None:
        year = int(m.group(1))
        week = int(m.group(2))
        day = int(m.group(3)) if m.group(3) is not None else 1
        if week < 1 or week > 53 or day < 1 or day > 7:
            raise ParserError(f"Invalid ISO week date: {timestr!r}")
        try:
            result = datetime.strptime(f"{year}-{week}-{day}", "%G-%V-%u")
            return result
        except ValueError as exc:
            raise ParserError(
                f"Invalid ISO week date in {timestr!r}: {exc}"
            ) from exc

    # Ordinal date: 2024-070, 2024070
    m = _ISO_ORDINAL_RE.match(stripped)
    if m is not None:
        year = int(m.group(1))
        ordinal = int(m.group(2))
        if ordinal < 1 or ordinal > 366:
            raise ParserError(f"Invalid ordinal date: {timestr!r}")
        try:
            result = datetime.strptime(f"{year}-{ordinal}", "%Y-%j")
            return result
        except ValueError as exc:
            raise ParserError(
                f"Invalid ordinal date in {timestr!r}: {exc}"
            ) from exc

    raise ParserError(f"Not a valid ISO 8601 string: {timestr!r}")
