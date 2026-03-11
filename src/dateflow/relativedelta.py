"""Month/year-aware date arithmetic — replaces dateutil.relativedelta."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional, Union


class weekday:
    """Represent a weekday with an optional occurrence number.

    MO, TU, WE, TH, FR, SA, SU are pre-built instances.
    Call them to get nth occurrences: FR(2) = second Friday.
    """

    __slots__ = ("weekday", "n")

    def __init__(self, weekday: int, n: Optional[int] = None) -> None:
        self.weekday = weekday
        self.n = n

    def __call__(self, n: int) -> weekday:
        if n == 0:
            raise ValueError("n must be non-zero")
        return weekday(self.weekday, n)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, weekday):
            return NotImplemented
        return self.weekday == other.weekday and self.n == other.n

    def __hash__(self) -> int:
        return hash((self.weekday, self.n))

    def __repr__(self) -> str:
        names = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
        s = names[self.weekday]
        if self.n is not None:
            s += f"({self.n:+d})"
        return s


MO = weekday(0)
TU = weekday(1)
WE = weekday(2)
TH = weekday(3)
FR = weekday(4)
SA = weekday(5)
SU = weekday(6)


class relativedelta:
    """Date arithmetic that correctly handles month-end clipping,
    year arithmetic, and weekday targeting.

    API-compatible with dateutil.relativedelta.relativedelta.
    """

    __slots__ = (
        "years",
        "months",
        "days",
        "hours",
        "minutes",
        "seconds",
        "microseconds",
        "leapdays",
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "microsecond",
        "weekday",
        "_has_time",
    )

    def __init__(
        self,
        dt1: Optional[Union[date, datetime]] = None,
        dt2: Optional[Union[date, datetime]] = None,
        *,
        years: int = 0,
        months: int = 0,
        days: int = 0,
        weeks: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        microseconds: int = 0,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        second: Optional[int] = None,
        microsecond: Optional[int] = None,
        weekday: Optional[Union[int, "weekday"]] = None,  # noqa: F811
        leapdays: int = 0,
    ) -> None:
        if dt1 is not None and dt2 is not None:
            # Compute the delta between two dates/datetimes
            self._compute_delta(dt1, dt2)
            return

        if dt1 is not None and dt2 is None:
            raise TypeError(
                "relativedelta requires either 0 or 2 positional date arguments"
            )

        # Store relative components
        self.years = years
        self.months = months
        self.days = days + weeks * 7
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.microseconds = microseconds
        self.leapdays = leapdays

        # Store absolute components
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.microsecond = microsecond

        if isinstance(weekday, int):
            self.weekday = _WEEKDAYS[weekday]
        else:
            self.weekday = weekday

        self._has_time = isinstance(dt1, datetime) if dt1 else False

        # Normalize: carry over months > 12 into years
        self._normalize()

    def _compute_delta(self, dt1: Union[date, datetime], dt2: Union[date, datetime]) -> None:
        """Compute relativedelta such that dt2 + result == dt1."""
        # Ensure both are datetimes for uniform handling
        if isinstance(dt1, datetime) or isinstance(dt2, datetime):
            self._has_time = True
        else:
            self._has_time = False

        if not isinstance(dt1, datetime):
            dt1 = datetime.combine(dt1, datetime.min.time())
        if not isinstance(dt2, datetime):
            dt2 = datetime.combine(dt2, datetime.min.time())

        # No absolute components
        self.year = None
        self.month = None
        self.day = None
        self.hour = None
        self.minute = None
        self.second = None
        self.microsecond = None
        self.weekday = None
        self.leapdays = 0

        # Compute years and months
        months_diff = (dt1.year - dt2.year) * 12 + (dt1.month - dt2.month)

        # Check if we overshot: apply months_diff to dt2 and see if we went past dt1
        dtm = _add_months(dt2, months_diff)

        # Compare the day/time portion
        if months_diff > 0 and dtm > dt1:
            months_diff -= 1
            dtm = _add_months(dt2, months_diff)
        elif months_diff < 0 and dtm < dt1:
            months_diff += 1
            dtm = _add_months(dt2, months_diff)

        self.years = int(months_diff / 12)  # truncate toward zero
        self.months = months_diff - self.years * 12

        # Remaining difference in days, hours, minutes, seconds, microseconds
        remaining = dt1 - dtm

        self.days = remaining.days
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.microseconds = 0

        if self._has_time:
            # Break out the sub-day components from the timedelta
            total_secs = remaining.days * 86400 + remaining.seconds
            self.days = 0
            sign = 1 if total_secs >= 0 else -1

            self.days = int(total_secs / 86400)
            leftover = abs(total_secs) - abs(self.days) * 86400
            self.hours = sign * (leftover // 3600)
            leftover %= 3600
            self.minutes = sign * (leftover // 60)
            self.seconds = sign * (leftover % 60)
            self.microseconds = remaining.microseconds

    def _normalize(self) -> None:
        """Carry over months >=12 into years (truncation toward zero)."""
        if abs(self.months) >= 12:
            extra = int(self.months / 12)  # truncates toward zero
            self.years += extra
            self.months -= extra * 12

    def __add__(self, other: Union[date, datetime, "relativedelta"]) -> Union[datetime, "relativedelta"]:
        if isinstance(other, relativedelta):
            return self._add_relativedelta(other)
        if isinstance(other, (date, datetime)):
            return self._apply(other)
        return NotImplemented

    def __radd__(self, other: Union[date, datetime]) -> Union[datetime, date]:
        if isinstance(other, (date, datetime)):
            return self._apply(other)
        return NotImplemented

    def __rsub__(self, other: Union[date, datetime]) -> Union[datetime, date]:
        if isinstance(other, (date, datetime)):
            return (-self)._apply(other)
        return NotImplemented

    def __sub__(self, other: "relativedelta") -> "relativedelta":
        if isinstance(other, relativedelta):
            return self._add_relativedelta(-other)
        return NotImplemented

    def __neg__(self) -> "relativedelta":
        return relativedelta(
            years=-self.years,
            months=-self.months,
            days=-self.days,
            hours=-self.hours,
            minutes=-self.minutes,
            seconds=-self.seconds,
            microseconds=-self.microseconds,
            leapdays=self.leapdays,
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            weekday=self.weekday,
        )

    def __abs__(self) -> "relativedelta":
        return relativedelta(
            years=abs(self.years),
            months=abs(self.months),
            days=abs(self.days),
            hours=abs(self.hours),
            minutes=abs(self.minutes),
            seconds=abs(self.seconds),
            microseconds=abs(self.microseconds),
            leapdays=self.leapdays,
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            weekday=self.weekday,
        )

    def __mul__(self, other: Union[int, float]) -> "relativedelta":
        if not isinstance(other, (int, float)):
            return NotImplemented
        return relativedelta(
            years=int(self.years * other),
            months=int(self.months * other),
            days=int(self.days * other),
            hours=int(self.hours * other),
            minutes=int(self.minutes * other),
            seconds=int(self.seconds * other),
            microseconds=int(self.microseconds * other),
            leapdays=self.leapdays,
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            weekday=self.weekday,
        )

    __rmul__ = __mul__

    def __bool__(self) -> bool:
        return bool(
            self.years
            or self.months
            or self.days
            or self.hours
            or self.minutes
            or self.seconds
            or self.microseconds
            or self.leapdays
            or self.year is not None
            or self.month is not None
            or self.day is not None
            or self.hour is not None
            or self.minute is not None
            or self.second is not None
            or self.microsecond is not None
            or self.weekday is not None
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, relativedelta):
            return NotImplemented
        return (
            self.years == other.years
            and self.months == other.months
            and self.days == other.days
            and self.hours == other.hours
            and self.minutes == other.minutes
            and self.seconds == other.seconds
            and self.microseconds == other.microseconds
            and self.leapdays == other.leapdays
            and self.year == other.year
            and self.month == other.month
            and self.day == other.day
            and self.hour == other.hour
            and self.minute == other.minute
            and self.second == other.second
            and self.microsecond == other.microsecond
            and self.weekday == other.weekday
        )

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result  # type: ignore[return-value]
        return not result

    def __hash__(self) -> int:
        return hash((
            self.years,
            self.months,
            self.days,
            self.hours,
            self.minutes,
            self.seconds,
            self.microseconds,
            self.leapdays,
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
            self.weekday,
        ))

    def __repr__(self) -> str:
        parts: list[str] = []
        # Relative components
        for attr in ("years", "months", "days", "hours", "minutes", "seconds", "microseconds", "leapdays"):
            val = getattr(self, attr)
            if val:
                parts.append(f"{attr}={val:+d}")
        # Absolute components
        for attr in ("year", "month", "day", "hour", "minute", "second", "microsecond"):
            val = getattr(self, attr)
            if val is not None:
                parts.append(f"{attr}={val}")
        if self.weekday is not None:
            parts.append(f"weekday={self.weekday!r}")
        return f"relativedelta({', '.join(parts)})"

    def _add_relativedelta(self, other: "relativedelta") -> "relativedelta":
        return relativedelta(
            years=self.years + other.years,
            months=self.months + other.months,
            days=self.days + other.days,
            hours=self.hours + other.hours,
            minutes=self.minutes + other.minutes,
            seconds=self.seconds + other.seconds,
            microseconds=self.microseconds + other.microseconds,
            leapdays=max(self.leapdays, other.leapdays),
            year=other.year if other.year is not None else self.year,
            month=other.month if other.month is not None else self.month,
            day=other.day if other.day is not None else self.day,
            hour=other.hour if other.hour is not None else self.hour,
            minute=other.minute if other.minute is not None else self.minute,
            second=other.second if other.second is not None else self.second,
            microsecond=(
                other.microsecond if other.microsecond is not None else self.microsecond
            ),
            weekday=other.weekday if other.weekday is not None else self.weekday,
        )

    def _apply(self, dt: Union[date, datetime]) -> Union[date, datetime]:
        """Apply this relativedelta to a date or datetime."""
        # Upgrade date to datetime if any time fields are set
        has_time_fields = (
            self.hours or self.minutes or self.seconds or self.microseconds
            or self.hour is not None or self.minute is not None
            or self.second is not None or self.microsecond is not None
        )
        if not isinstance(dt, datetime) and has_time_fields:
            dt = datetime(dt.year, dt.month, dt.day)
        is_datetime = isinstance(dt, datetime)

        # Start with absolute base (if set) or dt's value, then add relative
        base_year = self.year if self.year is not None else dt.year
        year = base_year + self.years
        base_month = self.month if self.month is not None else dt.month
        month = base_month + self.months

        # Normalize month/year
        if month > 12 or month < 1:
            extra_years, month = divmod(month - 1, 12)
            year += extra_years
            month += 1

        # Clip day to month end
        day = min(dt.day, calendar.monthrange(year, month)[1])

        # Apply absolute day
        if self.day is not None:
            day = min(self.day, calendar.monthrange(year, month)[1])

        # Handle leap day adjustment: add extra days on leap years after Feb
        leapday_offset = 0
        if self.leapdays and month > 2 and calendar.isleap(year):
            leapday_offset = self.leapdays

        if is_datetime:
            assert isinstance(dt, datetime)
            base_hour = self.hour if self.hour is not None else dt.hour
            hour = base_hour + self.hours
            base_minute = self.minute if self.minute is not None else dt.minute
            minute = base_minute + self.minutes
            base_second = self.second if self.second is not None else dt.second
            second = base_second + self.seconds
            base_microsecond = self.microsecond if self.microsecond is not None else dt.microsecond
            microsecond = base_microsecond + self.microseconds

            result = datetime(year, month, day, tzinfo=dt.tzinfo)
            result += timedelta(
                days=self.days + leapday_offset,
                hours=hour,
                minutes=minute,
                seconds=second,
                microseconds=microsecond,
            )
        else:
            result = date(year, month, day)  # type: ignore[assignment]
            result += timedelta(days=self.days + leapday_offset)  # type: ignore[assignment]

        # Weekday adjustment
        if self.weekday is not None:
            wd = self.weekday
            target_weekday = wd.weekday
            n = wd.n

            if n is None or n == 0:
                # Find the next occurrence (or same day if already on that weekday)
                current_weekday = result.weekday()
                diff = (target_weekday - current_weekday) % 7
                if diff:
                    result += timedelta(days=diff)  # type: ignore[assignment]
            elif n > 0:
                # nth occurrence forward from result
                current_weekday = result.weekday()
                diff = (target_weekday - current_weekday) % 7
                if diff == 0:
                    # Already on the target weekday, first occurrence is today
                    result += timedelta(days=7 * (n - 1))  # type: ignore[assignment]
                else:
                    result += timedelta(days=diff + 7 * (n - 1))  # type: ignore[assignment]
            else:
                # nth occurrence backward from result
                current_weekday = result.weekday()
                diff = (current_weekday - target_weekday) % 7
                if diff == 0:
                    result -= timedelta(days=7 * (-n - 1))  # type: ignore[assignment]
                else:
                    result -= timedelta(days=diff + 7 * (-n - 1))  # type: ignore[assignment]

        return result


def _add_months(dt: datetime, months: int) -> datetime:
    """Add months to a datetime, clipping the day to the last day of the month."""
    month = dt.month + months
    extra_years, month = divmod(month - 1, 12)
    year = dt.year + extra_years
    month += 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


_WEEKDAYS = [MO, TU, WE, TH, FR, SA, SU]
