"""RFC 5545 recurrence rules -- replaces dateutil.rrule.

Provides:
  - Frequency constants: YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY
  - Weekday constants: MO, TU, WE, TH, FR, SA, SU
  - rrule class: generate recurring datetimes per RFC 5545
  - rruleset class: combine rrules with rdates and exclusions
  - rrulestr function: parse iCalendar RRULE strings
"""

from __future__ import annotations

import calendar
import heapq
import itertools
from datetime import date, datetime, timedelta
from typing import (
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from dateflow.easter import easter as _easter_func
from dateflow.relativedelta import weekday, MO, TU, WE, TH, FR, SA, SU

# ---------------------------------------------------------------------------
# Frequency constants (compatible with dateutil.rrule)
# ---------------------------------------------------------------------------
YEARLY = 0
MONTHLY = 1
WEEKLY = 2
DAILY = 3
HOURLY = 4
MINUTELY = 5
SECONDLY = 6

_FREQ_NAMES = {
    "YEARLY": YEARLY,
    "MONTHLY": MONTHLY,
    "WEEKLY": WEEKLY,
    "DAILY": DAILY,
    "HOURLY": HOURLY,
    "MINUTELY": MINUTELY,
    "SECONDLY": SECONDLY,
}

_WEEKDAY_MAP = {
    "MO": MO,
    "TU": TU,
    "WE": WE,
    "TH": TH,
    "FR": FR,
    "SA": SA,
    "SU": SU,
}

_WEEKDAY_INDICES = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_weekday(val: Union[int, weekday]) -> weekday:
    """Convert an integer (0-6) to a weekday object, or pass through."""
    if isinstance(val, int):
        return weekday(val)
    return val


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _iso_week_number(dt: datetime) -> int:
    return dt.isocalendar()[1]


def _year_day(dt: datetime) -> int:
    return dt.timetuple().tm_yday


def _make_datetime(d: Union[date, datetime]) -> datetime:
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day)


def _clamp(dt: datetime, until: Optional[datetime]) -> bool:
    """Return True if dt exceeds until."""
    if until is None:
        return False
    return dt > until


# ---------------------------------------------------------------------------
# rrule
# ---------------------------------------------------------------------------

class rrule:
    """RFC 5545 recurrence rule.

    API-compatible with dateutil.rrule.rrule.
    """

    def __init__(
        self,
        freq: int,
        dtstart: Optional[datetime] = None,
        interval: int = 1,
        wkst: Optional[Union[int, weekday]] = None,
        count: Optional[int] = None,
        until: Optional[datetime] = None,
        bysetpos: Optional[Union[int, Sequence[int]]] = None,
        bymonth: Optional[Union[int, Sequence[int]]] = None,
        bymonthday: Optional[Union[int, Sequence[int]]] = None,
        byyearday: Optional[Union[int, Sequence[int]]] = None,
        byeaster: Optional[Union[int, Sequence[int]]] = None,
        byweekno: Optional[Union[int, Sequence[int]]] = None,
        byweekday: Optional[Union[int, weekday, Sequence[Union[int, weekday]]]] = None,
        byhour: Optional[Union[int, Sequence[int]]] = None,
        byminute: Optional[Union[int, Sequence[int]]] = None,
        bysecond: Optional[Union[int, Sequence[int]]] = None,
        cache: bool = False,
    ) -> None:
        if count is not None and until is not None:
            raise ValueError("count and until are mutually exclusive")

        if dtstart is None:
            dtstart = datetime.now().replace(microsecond=0)
        self._dtstart = _make_datetime(dtstart)
        self._freq = freq
        self._interval = interval
        self._count = count
        self._until = _make_datetime(until) if until is not None else None

        if wkst is None:
            self._wkst = 0  # Monday
        elif isinstance(wkst, weekday):
            self._wkst = wkst.weekday
        else:
            self._wkst = wkst

        # Normalize all BYXXX to tuples or None
        self._bysetpos = self._normalize_int_seq(bysetpos)
        self._bymonth = self._normalize_int_seq(bymonth)
        self._bymonthday = self._normalize_int_seq(bymonthday)
        self._byyearday = self._normalize_int_seq(byyearday)
        self._byeaster = self._normalize_int_seq(byeaster)
        self._byweekno = self._normalize_int_seq(byweekno)
        self._byhour = self._normalize_int_seq(byhour)
        self._byminute = self._normalize_int_seq(byminute)
        self._bysecond = self._normalize_int_seq(bysecond)

        # byweekday: normalize to tuple of weekday objects
        if byweekday is not None:
            if isinstance(byweekday, (int, weekday)):
                byweekday = (byweekday,)
            self._byweekday: Optional[Tuple[weekday, ...]] = tuple(
                _to_weekday(w) for w in byweekday
            )
        else:
            self._byweekday = None

        self._cache_enabled = cache
        self._cache_list: Optional[List[datetime]] = None

        # Apply default BYXXX based on freq when no explicit BYXXX given
        self._apply_defaults()

    @staticmethod
    def _normalize_int_seq(
        val: Optional[Union[int, Sequence[int]]],
    ) -> Optional[Tuple[int, ...]]:
        if val is None:
            return None
        if isinstance(val, int):
            return (val,)
        return tuple(val)

    def _apply_defaults(self) -> None:
        """Set implicit BYXXX rules based on freq and dtstart (RFC 5545 sec 3.3.10).

        For each time component (second, minute, hour), a default from dtstart is
        only set when the frequency is *coarser* than that component.  For example,
        SECONDLY never gets a default bysecond (the iterator already steps by
        seconds), MINUTELY gets bysecond but not byminute, etc.
        """

        if self._freq == YEARLY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)
            if self._byminute is None:
                self._byminute = (self._dtstart.minute,)
            if self._byhour is None:
                self._byhour = (self._dtstart.hour,)
            if (
                self._bymonth is None
                and self._bymonthday is None
                and self._byweekday is None
                and self._byyearday is None
                and self._byweekno is None
                and self._byeaster is None
            ):
                self._bymonth = (self._dtstart.month,)
                self._bymonthday = (self._dtstart.day,)

        elif self._freq == MONTHLY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)
            if self._byminute is None:
                self._byminute = (self._dtstart.minute,)
            if self._byhour is None:
                self._byhour = (self._dtstart.hour,)
            if self._byweekday is None and self._bymonthday is None:
                self._bymonthday = (self._dtstart.day,)

        elif self._freq == WEEKLY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)
            if self._byminute is None:
                self._byminute = (self._dtstart.minute,)
            if self._byhour is None:
                self._byhour = (self._dtstart.hour,)
            if self._byweekday is None:
                self._byweekday = (_to_weekday(self._dtstart.weekday()),)

        elif self._freq == DAILY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)
            if self._byminute is None:
                self._byminute = (self._dtstart.minute,)
            if self._byhour is None:
                self._byhour = (self._dtstart.hour,)

        elif self._freq == HOURLY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)
            if self._byminute is None:
                self._byminute = (self._dtstart.minute,)

        elif self._freq == MINUTELY:
            if self._bysecond is None:
                self._bysecond = (self._dtstart.second,)

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[datetime]:
        if self._cache_enabled and self._cache_list is not None:
            yield from self._cache_list
            return

        results: List[datetime] = [] if self._cache_enabled else []  # type: ignore
        yielded = 0

        for dt in self._iter_candidates():
            if self._until is not None and dt > self._until:
                break
            if self._count is not None and yielded >= self._count:
                break
            if self._cache_enabled:
                results.append(dt)
            yield dt
            yielded += 1

        if self._cache_enabled:
            self._cache_list = results

    def _iter_candidates(self) -> Iterator[datetime]:
        """Generate candidate datetimes by advancing through time intervals."""
        if self._byeaster is not None:
            yield from self._iter_byeaster()
            return

        if self._freq == YEARLY:
            yield from self._iter_yearly()
        elif self._freq == MONTHLY:
            yield from self._iter_monthly()
        elif self._freq == WEEKLY:
            yield from self._iter_weekly()
        elif self._freq == DAILY:
            yield from self._iter_daily()
        elif self._freq == HOURLY:
            yield from self._iter_hourly()
        elif self._freq == MINUTELY:
            yield from self._iter_minutely()
        elif self._freq == SECONDLY:
            yield from self._iter_secondly()

    def _expand_time(
        self, base_date: date
    ) -> List[datetime]:
        """Expand time components (hour/minute/second) for a given date."""
        hours = self._byhour if self._byhour else (self._dtstart.hour,)
        minutes = self._byminute if self._byminute else (self._dtstart.minute,)
        seconds = self._bysecond if self._bysecond else (self._dtstart.second,)

        results = []
        for h in sorted(hours):
            for m in sorted(minutes):
                for s in sorted(seconds):
                    results.append(
                        datetime(base_date.year, base_date.month, base_date.day, h, m, s)
                    )
        return results

    def _expand_days_in_year(self, year: int) -> List[date]:
        """Expand BYXXX day rules for a whole year. Returns sorted dates."""
        dates: Set[date] = set()

        if self._byyearday is not None:
            total_days = 366 if calendar.isleap(year) else 365
            for yd in self._byyearday:
                if yd > 0:
                    d = date(year, 1, 1) + timedelta(days=yd - 1)
                else:
                    d = date(year, 12, 31) + timedelta(days=yd + 1)
                if d.year == year:
                    dates.add(d)
            return sorted(dates)

        if self._byweekno is not None:
            for wn in self._byweekno:
                dates.update(self._dates_in_isoweek(year, wn))
            # Filter by byweekday if specified
            if self._byweekday is not None:
                wd_set = {w.weekday for w in self._byweekday}
                dates = {d for d in dates if d.weekday() in wd_set}
            if self._bymonth is not None:
                dates = {d for d in dates if d.month in self._bymonth}
            return sorted(dates)

        # Start with months
        months = self._bymonth if self._bymonth else range(1, 13)

        for m in sorted(months):
            month_dates = self._expand_days_in_month(year, m)
            dates.update(month_dates)

        return sorted(dates)

    def _dates_in_isoweek(self, year: int, weekno: int) -> List[date]:
        """Return all dates that fall in the given ISO week number for the year."""
        # Find Jan 4 (always in ISO week 1) then go to the desired week
        jan4 = date(year, 1, 4)
        # Monday of week 1
        monday_wk1 = jan4 - timedelta(days=jan4.weekday())
        monday_target = monday_wk1 + timedelta(weeks=weekno - 1)

        result = []
        for i in range(7):
            d = monday_target + timedelta(days=i)
            # The date should be in the requested year
            if d.year == year or (d.isocalendar()[0] == year and d.isocalendar()[1] == weekno):
                result.append(d)
        return result

    def _expand_days_in_month(self, year: int, month: int) -> List[date]:
        """Expand day rules within a single month."""
        dim = _days_in_month(year, month)

        # Start with monthdays
        if self._bymonthday is not None:
            days: Set[int] = set()
            for md in self._bymonthday:
                if md > 0:
                    if md <= dim:
                        days.add(md)
                elif md < 0:
                    d = dim + md + 1
                    if 1 <= d <= dim:
                        days.add(d)
            # If byweekday is also set, intersect
            if self._byweekday is not None and any(w.n is None for w in self._byweekday):
                wd_set = {w.weekday for w in self._byweekday if w.n is None}
                day_dates = [date(year, month, d) for d in sorted(days)]
                return [d for d in day_dates if d.weekday() in wd_set]
            return [date(year, month, d) for d in sorted(days)]

        if self._byweekday is not None:
            return self._expand_byweekday_in_month(year, month)

        # No explicit day constraints -- use all days of the month
        # (YEARLY with bymonth defaults here)
        return [date(year, month, d) for d in range(1, dim + 1)]

    def _expand_byweekday_in_month(self, year: int, month: int) -> List[date]:
        """Expand byweekday within a month, handling nth occurrences."""
        dim = _days_in_month(year, month)
        results: List[date] = []

        for wd in self._byweekday:
            if wd.n is None:
                # Every occurrence of this weekday in the month
                for d in range(1, dim + 1):
                    dt = date(year, month, d)
                    if dt.weekday() == wd.weekday:
                        results.append(dt)
            elif wd.n > 0:
                # Nth occurrence from start
                count = 0
                for d in range(1, dim + 1):
                    dt = date(year, month, d)
                    if dt.weekday() == wd.weekday:
                        count += 1
                        if count == wd.n:
                            results.append(dt)
                            break
            else:
                # Nth occurrence from end (negative)
                count = 0
                for d in range(dim, 0, -1):
                    dt = date(year, month, d)
                    if dt.weekday() == wd.weekday:
                        count += 1
                        if count == abs(wd.n):
                            results.append(dt)
                            break

        return sorted(set(results))

    def _apply_bysetpos(self, datetimes: List[datetime]) -> List[datetime]:
        """Filter by BYSETPOS."""
        if self._bysetpos is None:
            return datetimes
        n = len(datetimes)
        result = []
        for pos in self._bysetpos:
            if pos > 0:
                idx = pos - 1
            else:
                idx = n + pos
            if 0 <= idx < n:
                result.append(datetimes[idx])
        return sorted(set(result))

    def _filter_dtstart(self, candidates: List[datetime]) -> List[datetime]:
        """Filter out candidates before dtstart."""
        return [dt for dt in candidates if dt >= self._dtstart]

    # ------------------------------------------------------------------
    # Frequency-specific iteration
    # ------------------------------------------------------------------

    def _iter_yearly(self) -> Iterator[datetime]:
        year = self._dtstart.year
        # Safety: hard limit to prevent infinite loops (counts iterations, not yields)
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            dates = self._expand_days_in_year(year)
            period_results: List[datetime] = []
            for d in dates:
                period_results.extend(self._expand_time(d))
            period_results.sort()
            period_results = self._apply_bysetpos(period_results)
            for dt in self._filter_dtstart(period_results):
                yield dt
            year += self._interval

    def _iter_monthly(self) -> Iterator[datetime]:
        year = self._dtstart.year
        month = self._dtstart.month
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            dates = self._expand_days_in_month(year, month)
            if self._bymonth is not None:
                dates = [d for d in dates if d.month in self._bymonth]
            period_results: List[datetime] = []
            for d in dates:
                period_results.extend(self._expand_time(d))
            period_results.sort()
            period_results = self._apply_bysetpos(period_results)
            for dt in self._filter_dtstart(period_results):
                yield dt
            # Advance by interval months
            month += self._interval
            while month > 12:
                month -= 12
                year += 1

    def _iter_weekly(self) -> Iterator[datetime]:
        # Find the start of the week containing dtstart (aligned to wkst)
        ds = self._dtstart
        ds_weekday = ds.weekday()
        # Offset to the wkst day
        diff = (ds_weekday - self._wkst) % 7
        week_start = date(ds.year, ds.month, ds.day) - timedelta(days=diff)

        max_iter = 100000
        iterations = 0

        while iterations < max_iter:
            iterations += 1
            # Generate days in this week
            week_dates: List[date] = []
            if self._byweekday is not None:
                for wd in self._byweekday:
                    offset = (wd.weekday - self._wkst) % 7
                    d = week_start + timedelta(days=offset)
                    week_dates.append(d)
            else:
                week_dates.append(week_start)
            week_dates.sort()

            if self._bymonth is not None:
                week_dates = [d for d in week_dates if d.month in self._bymonth]

            period_results: List[datetime] = []
            for d in week_dates:
                period_results.extend(self._expand_time(d))
            period_results.sort()
            period_results = self._apply_bysetpos(period_results)
            for dt in self._filter_dtstart(period_results):
                yield dt
            week_start += timedelta(weeks=self._interval)

    def _iter_daily(self) -> Iterator[datetime]:
        d = date(self._dtstart.year, self._dtstart.month, self._dtstart.day)
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            # Filter by BYXXX
            ok = True
            if self._bymonth is not None and d.month not in self._bymonth:
                ok = False
            if self._bymonthday is not None and d.day not in self._bymonthday:
                # Handle negative monthdays
                dim = _days_in_month(d.year, d.month)
                neg_days = {dim + md + 1 for md in self._bymonthday if md < 0}
                pos_days = {md for md in self._bymonthday if md > 0}
                if d.day not in pos_days and d.day not in neg_days:
                    ok = False
            if self._byweekday is not None:
                wd_set = {w.weekday for w in self._byweekday}
                if d.weekday() not in wd_set:
                    ok = False

            if ok:
                period_results: List[datetime] = self._expand_time(d)
                period_results.sort()
                period_results = self._apply_bysetpos(period_results)
                for dt in self._filter_dtstart(period_results):
                    yield dt
            d += timedelta(days=self._interval)

    def _iter_hourly(self) -> Iterator[datetime]:
        current = self._dtstart
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            ok = True
            if self._bymonth is not None and current.month not in self._bymonth:
                ok = False
            if self._bymonthday is not None:
                dim = _days_in_month(current.year, current.month)
                pos_days = {md for md in self._bymonthday if md > 0}
                neg_days = {dim + md + 1 for md in self._bymonthday if md < 0}
                if current.day not in pos_days and current.day not in neg_days:
                    ok = False
            if self._byweekday is not None:
                wd_set = {w.weekday for w in self._byweekday}
                if current.weekday() not in wd_set:
                    ok = False
            if self._byhour is not None and current.hour not in self._byhour:
                ok = False

            if ok:
                minutes = self._byminute if self._byminute else (current.minute,)
                seconds = self._bysecond if self._bysecond else (current.second,)
                period_results = []
                for m in sorted(minutes):
                    for s in sorted(seconds):
                        dt = current.replace(minute=m, second=s)
                        if dt >= self._dtstart:
                            period_results.append(dt)
                period_results.sort()
                period_results = self._apply_bysetpos(period_results)
                for dt in period_results:
                    yield dt

            current += timedelta(hours=self._interval)

    def _iter_minutely(self) -> Iterator[datetime]:
        current = self._dtstart
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            ok = True
            if self._bymonth is not None and current.month not in self._bymonth:
                ok = False
            if self._bymonthday is not None:
                dim = _days_in_month(current.year, current.month)
                pos_days = {md for md in self._bymonthday if md > 0}
                neg_days = {dim + md + 1 for md in self._bymonthday if md < 0}
                if current.day not in pos_days and current.day not in neg_days:
                    ok = False
            if self._byweekday is not None:
                wd_set = {w.weekday for w in self._byweekday}
                if current.weekday() not in wd_set:
                    ok = False
            if self._byhour is not None and current.hour not in self._byhour:
                ok = False
            if self._byminute is not None and current.minute not in self._byminute:
                ok = False

            if ok:
                seconds = self._bysecond if self._bysecond else (current.second,)
                period_results = []
                for s in sorted(seconds):
                    dt = current.replace(second=s)
                    if dt >= self._dtstart:
                        period_results.append(dt)
                period_results = self._apply_bysetpos(period_results)
                for dt in period_results:
                    yield dt

            current += timedelta(minutes=self._interval)

    def _iter_secondly(self) -> Iterator[datetime]:
        current = self._dtstart
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            ok = True
            if self._bymonth is not None and current.month not in self._bymonth:
                ok = False
            if self._bymonthday is not None:
                dim = _days_in_month(current.year, current.month)
                pos_days = {md for md in self._bymonthday if md > 0}
                neg_days = {dim + md + 1 for md in self._bymonthday if md < 0}
                if current.day not in pos_days and current.day not in neg_days:
                    ok = False
            if self._byweekday is not None:
                wd_set = {w.weekday for w in self._byweekday}
                if current.weekday() not in wd_set:
                    ok = False
            if self._byhour is not None and current.hour not in self._byhour:
                ok = False
            if self._byminute is not None and current.minute not in self._byminute:
                ok = False
            if self._bysecond is not None and current.second not in self._bysecond:
                ok = False

            if ok:
                period_results = self._apply_bysetpos([current])
                for dt in period_results:
                    yield dt

            current += timedelta(seconds=self._interval)

    def _iter_byeaster(self) -> Iterator[datetime]:
        """Handle byeaster: offsets from Easter Sunday."""
        year = self._dtstart.year
        max_iter = 100000
        iterations = 0
        while iterations < max_iter:
            iterations += 1
            try:
                easter_date = _easter_func(year)
            except ValueError:
                break
            period_results: List[datetime] = []
            for offset in sorted(self._byeaster):  # type: ignore
                d = easter_date + timedelta(days=offset)
                for dt in self._expand_time(d):
                    if dt >= self._dtstart:
                        period_results.append(dt)
            period_results.sort()
            period_results = self._apply_bysetpos(period_results)
            for dt in period_results:
                yield dt
            year += self._interval

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of occurrences."""
        return sum(1 for _ in self)

    def __getitem__(self, key: Union[int, slice]) -> Union[datetime, List[datetime]]:
        if isinstance(key, slice):
            return list(itertools.islice(self, key.start, key.stop, key.step))
        if key < 0:
            # Need to materialise
            items = list(self)
            return items[key]
        return next(itertools.islice(self, key, key + 1))

    def __contains__(self, dt: object) -> bool:
        if not isinstance(dt, datetime):
            return False
        for item in self:
            if item == dt:
                return True
            if item > dt:
                return False
        return False

    def after(self, dt: datetime, inc: bool = False) -> Optional[datetime]:
        """Return the first recurrence after *dt*."""
        for item in self:
            if inc and item >= dt:
                return item
            if not inc and item > dt:
                return item
        return None

    def before(self, dt: datetime, inc: bool = False) -> Optional[datetime]:
        """Return the last recurrence before *dt*."""
        result: Optional[datetime] = None
        for item in self:
            if inc and item <= dt:
                result = item
            elif not inc and item < dt:
                result = item
            elif item > dt:
                break
        return result

    def between(
        self, after: datetime, before: datetime, inc: bool = False
    ) -> List[datetime]:
        """Return all recurrences between *after* and *before*."""
        results: List[datetime] = []
        for item in self:
            if inc:
                if item > before:
                    break
                if item >= after:
                    results.append(item)
            else:
                if item >= before:
                    break
                if item > after:
                    results.append(item)
        return results


# ---------------------------------------------------------------------------
# rruleset
# ---------------------------------------------------------------------------

class rruleset:
    """Combine multiple rrule objects, rdates, exrules and exdates.

    API-compatible with dateutil.rrule.rruleset.
    """

    def __init__(self, cache: bool = False) -> None:
        self._rrule: List[rrule] = []
        self._rdate: List[datetime] = []
        self._exrule: List[rrule] = []
        self._exdate: List[datetime] = []
        self._cache_enabled = cache
        self._cache_list: Optional[List[datetime]] = None

    def rrule(self, rule: rrule) -> None:
        """Add an inclusion rule."""
        self._rrule.append(rule)
        self._cache_list = None

    def rdate(self, dt: datetime) -> None:
        """Add an inclusion date."""
        self._rdate.append(_make_datetime(dt))
        self._cache_list = None

    def exrule(self, rule: rrule) -> None:
        """Add an exclusion rule."""
        self._exrule.append(rule)
        self._cache_list = None

    def exdate(self, dt: datetime) -> None:
        """Add an exclusion date."""
        self._exdate.append(_make_datetime(dt))
        self._cache_list = None

    def __iter__(self) -> Iterator[datetime]:
        if self._cache_enabled and self._cache_list is not None:
            yield from self._cache_list
            return

        # Build exclusion set
        exdates: Set[datetime] = set(self._exdate)
        exrule_iters = [iter(r) for r in self._exrule]
        # Materialise exclusion rules (they should be finite or we'll limit)
        for ex_iter in exrule_iters:
            for dt in ex_iter:
                exdates.add(dt)

        # Merge inclusion sources
        iterators: List[Iterator[datetime]] = [iter(r) for r in self._rrule]
        if self._rdate:
            iterators.append(iter(sorted(self._rdate)))

        seen: Set[datetime] = set()
        results: List[datetime] = [] if self._cache_enabled else []  # type: ignore

        for dt in heapq.merge(*iterators):
            if dt in exdates:
                continue
            if dt in seen:
                continue
            seen.add(dt)
            if self._cache_enabled:
                results.append(dt)
            yield dt

        if self._cache_enabled:
            self._cache_list = results

    def count(self) -> int:
        return sum(1 for _ in self)

    def after(self, dt: datetime, inc: bool = False) -> Optional[datetime]:
        for item in self:
            if inc and item >= dt:
                return item
            if not inc and item > dt:
                return item
        return None

    def before(self, dt: datetime, inc: bool = False) -> Optional[datetime]:
        result: Optional[datetime] = None
        for item in self:
            if inc and item <= dt:
                result = item
            elif not inc and item < dt:
                result = item
            elif item > dt:
                break
        return result

    def between(
        self, after: datetime, before: datetime, inc: bool = False
    ) -> List[datetime]:
        results: List[datetime] = []
        for item in self:
            if inc:
                if item > before:
                    break
                if item >= after:
                    results.append(item)
            else:
                if item >= before:
                    break
                if item > after:
                    results.append(item)
        return results


# ---------------------------------------------------------------------------
# rrulestr
# ---------------------------------------------------------------------------

def rrulestr(
    s: str,
    dtstart: Optional[datetime] = None,
    ignoretz: bool = False,
    unfold: bool = False,
    forceset: bool = False,
    compatible: bool = False,
    cache: bool = False,
) -> Union[rrule, rruleset]:
    """Parse an iCalendar RRULE string (or multi-line block) into an rrule or rruleset.

    Supports:
      - Single-line:  "FREQ=DAILY;COUNT=10"
      - With prefix:  "RRULE:FREQ=DAILY;COUNT=10"
      - Multi-line with DTSTART, RRULE, EXRULE, RDATE, EXDATE
    """
    lines = s.strip().splitlines()
    lines = [l.strip() for l in lines if l.strip()]

    parsed_dtstart = dtstart
    rrules: List[dict] = []
    exrules: List[dict] = []
    rdates: List[datetime] = []
    exdates: List[datetime] = []

    if len(lines) == 1 and not lines[0].upper().startswith(("DTSTART", "RRULE:", "EXRULE:", "RDATE:", "EXDATE:")):
        # Simple single-line RRULE (possibly with RRULE: prefix stripped)
        line = lines[0]
        if line.upper().startswith("RRULE:"):
            line = line[6:]
        params = _parse_rrule_params(line)
        return _build_rrule(params, parsed_dtstart, cache)

    for line in lines:
        upper = line.upper()
        if upper.startswith("DTSTART"):
            # DTSTART:20260101T000000 or DTSTART;TZID=...:20260101T000000
            val = line.split(":", 1)[-1]
            parsed_dtstart = _parse_dt_value(val)
        elif upper.startswith("RRULE:"):
            rrules.append(_parse_rrule_params(line[6:]))
        elif upper.startswith("EXRULE:"):
            exrules.append(_parse_rrule_params(line[7:]))
        elif upper.startswith("RDATE"):
            val = line.split(":", 1)[-1]
            for v in val.split(","):
                rdates.append(_parse_dt_value(v.strip()))
        elif upper.startswith("EXDATE"):
            val = line.split(":", 1)[-1]
            for v in val.split(","):
                exdates.append(_parse_dt_value(v.strip()))
        else:
            # Might be a bare RRULE line
            rrules.append(_parse_rrule_params(line))

    # If only one RRULE, no extras, and not forced set, return plain rrule
    if (
        len(rrules) == 1
        and not exrules
        and not rdates
        and not exdates
        and not forceset
    ):
        return _build_rrule(rrules[0], parsed_dtstart, cache)

    # Build rruleset
    rs = rruleset(cache=cache)
    for params in rrules:
        rs.rrule(_build_rrule(params, parsed_dtstart, cache=False))
    for params in exrules:
        rs.exrule(_build_rrule(params, parsed_dtstart, cache=False))
    for dt in rdates:
        rs.rdate(dt)
    for dt in exdates:
        rs.exdate(dt)

    return rs


def _parse_dt_value(s: str) -> datetime:
    """Parse a basic iCalendar datetime value like 20260311T143000 or 20260311."""
    s = s.strip()
    if "T" in s:
        # Remove trailing Z for UTC
        s = s.rstrip("Z")
        return datetime.strptime(s, "%Y%m%dT%H%M%S")
    else:
        d = datetime.strptime(s, "%Y%m%d")
        return d


def _parse_rrule_params(s: str) -> dict:
    """Parse RRULE parameters from a string like FREQ=DAILY;COUNT=10."""
    params: dict = {}
    for part in s.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.upper().strip()
        val = val.strip()
        params[key] = val
    return params


def _parse_weekday(s: str) -> weekday:
    """Parse a weekday string like 'MO', '+2FR', '-1SU', '2FR'."""
    s = s.strip()
    if len(s) == 2:
        return _WEEKDAY_MAP[s.upper()]
    # Has an occurrence prefix
    day_abbr = s[-2:].upper()
    n_str = s[:-2]
    n = int(n_str)
    return _WEEKDAY_MAP[day_abbr](n)


def _build_rrule(params: dict, dtstart: Optional[datetime], cache: bool) -> rrule:
    """Build an rrule from parsed parameters dict."""
    kwargs: dict = {}

    if "FREQ" in params:
        kwargs["freq"] = _FREQ_NAMES[params["FREQ"].upper()]
    else:
        raise ValueError("RRULE must have a FREQ parameter")

    if dtstart is not None:
        kwargs["dtstart"] = dtstart

    if "INTERVAL" in params:
        kwargs["interval"] = int(params["INTERVAL"])

    if "COUNT" in params:
        kwargs["count"] = int(params["COUNT"])

    if "UNTIL" in params:
        kwargs["until"] = _parse_dt_value(params["UNTIL"])

    if "WKST" in params:
        kwargs["wkst"] = _WEEKDAY_MAP[params["WKST"].upper()]

    if "BYSETPOS" in params:
        kwargs["bysetpos"] = [int(x) for x in params["BYSETPOS"].split(",")]

    if "BYMONTH" in params:
        kwargs["bymonth"] = [int(x) for x in params["BYMONTH"].split(",")]

    if "BYMONTHDAY" in params:
        kwargs["bymonthday"] = [int(x) for x in params["BYMONTHDAY"].split(",")]

    if "BYYEARDAY" in params:
        kwargs["byyearday"] = [int(x) for x in params["BYYEARDAY"].split(",")]

    if "BYWEEKNO" in params:
        kwargs["byweekno"] = [int(x) for x in params["BYWEEKNO"].split(",")]

    if "BYDAY" in params:
        kwargs["byweekday"] = [_parse_weekday(d) for d in params["BYDAY"].split(",")]

    if "BYHOUR" in params:
        kwargs["byhour"] = [int(x) for x in params["BYHOUR"].split(",")]

    if "BYMINUTE" in params:
        kwargs["byminute"] = [int(x) for x in params["BYMINUTE"].split(",")]

    if "BYSECOND" in params:
        kwargs["bysecond"] = [int(x) for x in params["BYSECOND"].split(",")]

    if "BYEASTER" in params:
        kwargs["byeaster"] = [int(x) for x in params["BYEASTER"].split(",")]

    kwargs["cache"] = cache

    return rrule(**kwargs)
