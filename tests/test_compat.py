"""
Compatibility tests — verifies that dateflow is a drop-in replacement for
python-dateutil by exercising the same API patterns users rely on.

Each test uses dateflow the way a user would use dateutil after running:
    s/from dateutil/from dateflow/g
"""

from datetime import date, datetime, timedelta, timezone
import pytest

# ---------- Import compatibility ----------
# These imports must work as drop-in replacements for:
#   from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
#   from dateutil.parser import parse, isoparse, ParserError
#   from dateutil.rrule import rrule, rruleset, rrulestr, YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY
#   from dateutil.easter import easter, EASTER_WESTERN, EASTER_ORTHODOX, EASTER_JULIAN
#   from dateutil.tz import tzutc, tzoffset, tzlocal, gettz, UTC

from dateflow.relativedelta import relativedelta, weekday, MO, TU, WE, TH, FR, SA, SU
from dateflow.parser import parse, isoparse, ParserError
from dateflow.rrule import (
    rrule, rruleset, rrulestr,
    YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY,
)
from dateflow.easter import easter, EASTER_WESTERN, EASTER_ORTHODOX, EASTER_JULIAN
from dateflow.tz import tzutc, tzoffset, tzlocal, gettz, UTC, enfold, resolve_imaginary

# Also verify top-level package imports work
import dateflow


class TestImportCompat:
    """Verify that the public API surface matches dateutil."""

    def test_version_exists(self):
        assert hasattr(dateflow, "__version__")

    def test_top_level_exports(self):
        """All key symbols should be importable from the top-level package."""
        for name in [
            "relativedelta", "weekday", "MO", "TU", "WE", "TH", "FR", "SA", "SU",
            "parse", "isoparse", "ParserError",
            "easter",
            "rrule", "rruleset", "rrulestr",
            "YEARLY", "MONTHLY", "WEEKLY", "DAILY", "HOURLY", "MINUTELY", "SECONDLY",
            "UTC", "gettz", "tzutc", "tzoffset", "tzlocal",
            "enfold", "resolve_imaginary", "datetime_exists", "datetime_ambiguous",
        ]:
            assert hasattr(dateflow, name), f"dateflow missing export: {name}"

    def test_weekday_constants_are_weekday_instances(self):
        for wd in (MO, TU, WE, TH, FR, SA, SU):
            assert isinstance(wd, weekday)


class TestRelativeDeltaCompat:
    """dateutil.relativedelta compatibility."""

    def test_add_months(self):
        dt = datetime(2023, 1, 31)
        result = dt + relativedelta(months=1)
        assert result == datetime(2023, 2, 28)  # month-end clipping

    def test_subtract_years(self):
        dt = datetime(2024, 2, 29)  # leap day
        result = dt - relativedelta(years=1)
        assert result == datetime(2023, 2, 28)  # clipped

    def test_absolute_fields(self):
        dt = datetime(2023, 6, 15, 10, 30)
        result = dt + relativedelta(hour=0, minute=0, second=0)
        assert result == datetime(2023, 6, 15, 0, 0, 0)

    def test_weekday_targeting(self):
        # Next Friday from a Monday
        dt = datetime(2023, 10, 2)  # Monday
        result = dt + relativedelta(weekday=FR)
        assert result.weekday() == 4  # Friday
        assert result == datetime(2023, 10, 6)

    def test_nth_weekday(self):
        # Second Tuesday of the month
        dt = datetime(2023, 10, 1)
        result = dt + relativedelta(day=1, weekday=TU(2))
        assert result == datetime(2023, 10, 10)

    def test_delta_between_dates(self):
        dt1 = datetime(2023, 3, 15)
        dt2 = datetime(2025, 7, 20)
        rd = relativedelta(dt1=dt2, dt2=dt1)
        assert rd.years == 2
        assert rd.months == 4
        assert rd.days == 5

    def test_relativedelta_arithmetic(self):
        rd1 = relativedelta(months=1, days=5)
        rd2 = relativedelta(months=2, days=3)
        combined = rd1 + rd2
        assert combined.months == 3
        assert combined.days == 8

    def test_negation(self):
        rd = relativedelta(years=1, months=2, days=3)
        neg = -rd
        assert neg.years == -1
        assert neg.months == -2
        assert neg.days == -3

    def test_multiplication(self):
        rd = relativedelta(months=3, days=10)
        result = rd * 2
        assert result.months == 6
        assert result.days == 20


class TestParserCompat:
    """dateutil.parser compatibility."""

    def test_parse_iso(self):
        result = parse("2023-10-15T14:30:00")
        assert result == datetime(2023, 10, 15, 14, 30, 0)

    def test_parse_natural(self):
        result = parse("October 15, 2023")
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_parse_with_timezone(self):
        result = parse("2023-10-15T14:30:00+05:30")
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_parse_dayfirst(self):
        result = parse("15/10/2023", dayfirst=True)
        assert result.day == 15
        assert result.month == 10

    def test_parse_yearfirst(self):
        result = parse("2023/10/15", yearfirst=True)
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_parse_fuzzy(self):
        result = parse("The meeting is on Oct 15, 2023 at 2pm", fuzzy=True)
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_parse_fuzzy_with_tokens(self):
        result, tokens = parse(
            "The meeting is on Oct 15, 2023 at 2pm",
            fuzzy_with_tokens=True,
        )
        assert result.year == 2023
        assert isinstance(tokens, tuple)

    def test_isoparse(self):
        result = isoparse("2023-10-15T14:30:00Z")
        assert result == datetime(2023, 10, 15, 14, 30, 0, tzinfo=timezone.utc)

    def test_isoparse_date_only(self):
        result = isoparse("2023-10-15")
        assert result == datetime(2023, 10, 15)

    def test_parser_error(self):
        with pytest.raises(ParserError):
            parse("not a date at all")


class TestRRuleCompat:
    """dateutil.rrule compatibility."""

    def test_daily_count(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=5)
        dates = list(r)
        assert len(dates) == 5
        assert dates[0] == datetime(2023, 10, 1)
        assert dates[-1] == datetime(2023, 10, 5)

    def test_weekly_until(self):
        r = rrule(
            WEEKLY,
            dtstart=datetime(2023, 10, 1),
            until=datetime(2023, 10, 31),
        )
        dates = list(r)
        assert all(d.weekday() == 6 for d in dates)  # All Sundays (Oct 1 is Sunday)
        assert dates[-1] <= datetime(2023, 10, 31)

    def test_monthly_bymonthday(self):
        r = rrule(
            MONTHLY,
            dtstart=datetime(2023, 1, 1),
            count=3,
            bymonthday=15,
        )
        dates = list(r)
        assert dates == [
            datetime(2023, 1, 15),
            datetime(2023, 2, 15),
            datetime(2023, 3, 15),
        ]

    def test_yearly_bymonth(self):
        r = rrule(
            YEARLY,
            dtstart=datetime(2020, 1, 1),
            count=3,
            bymonth=(3, 6, 9),
        )
        dates = list(r)
        assert len(dates) == 3
        assert all(d.month in (3, 6, 9) for d in dates)

    def test_rrule_indexing(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=10)
        assert r[0] == datetime(2023, 10, 1)
        assert r[4] == datetime(2023, 10, 5)
        assert r[-1] == datetime(2023, 10, 10)

    def test_rrule_after_before(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=10)
        after = r.after(datetime(2023, 10, 5))
        assert after == datetime(2023, 10, 6)
        before = r.before(datetime(2023, 10, 5))
        assert before == datetime(2023, 10, 4)

    def test_rrule_between(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=10)
        between = r.between(datetime(2023, 10, 3), datetime(2023, 10, 7))
        assert len(between) == 3  # 4, 5, 6

    def test_rrule_contains(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=5)
        assert datetime(2023, 10, 3) in r
        assert datetime(2023, 10, 10) not in r

    def test_rrule_count_method(self):
        r = rrule(DAILY, dtstart=datetime(2023, 10, 1), count=5)
        assert r.count() == 5

    def test_rruleset(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, dtstart=datetime(2023, 10, 1), count=5))
        rs.exdate(datetime(2023, 10, 3))
        dates = list(rs)
        assert datetime(2023, 10, 3) not in dates
        assert len(dates) == 4

    def test_rrulestr(self):
        r = rrulestr("RRULE:FREQ=DAILY;COUNT=3", dtstart=datetime(2023, 10, 1))
        dates = list(r)
        assert len(dates) == 3

    def test_frequency_constants(self):
        assert YEARLY == 0
        assert MONTHLY == 1
        assert WEEKLY == 2
        assert DAILY == 3
        assert HOURLY == 4
        assert MINUTELY == 5
        assert SECONDLY == 6


class TestEasterCompat:
    """dateutil.easter compatibility."""

    def test_western_easter_2023(self):
        assert easter(2023) == date(2023, 4, 9)

    def test_western_easter_2024(self):
        assert easter(2024) == date(2024, 3, 31)

    def test_orthodox_easter_2023(self):
        assert easter(2023, EASTER_ORTHODOX) == date(2023, 4, 16)

    def test_julian_easter_2023(self):
        result = easter(2023, EASTER_JULIAN)
        assert isinstance(result, date)

    def test_easter_method_constants(self):
        assert EASTER_JULIAN == 1
        assert EASTER_ORTHODOX == 2
        assert EASTER_WESTERN == 3


class TestTzCompat:
    """dateutil.tz compatibility."""

    def test_utc_singleton(self):
        assert UTC is not None
        dt = datetime(2023, 10, 15, tzinfo=UTC)
        assert dt.utcoffset() == timedelta(0)

    def test_tzutc(self):
        tz = tzutc()
        dt = datetime(2023, 10, 15, tzinfo=tz)
        assert dt.utcoffset() == timedelta(0)
        assert str(tz) == "tzutc()"

    def test_tzoffset(self):
        tz = tzoffset("EST", -18000)
        dt = datetime(2023, 10, 15, tzinfo=tz)
        assert dt.utcoffset() == timedelta(hours=-5)

    def test_gettz_utc(self):
        tz = gettz("UTC")
        assert tz is not None
        dt = datetime(2023, 10, 15, tzinfo=tz)
        assert dt.utcoffset() == timedelta(0)

    def test_gettz_iana(self):
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2023, 7, 15, 12, 0, tzinfo=tz)
        assert dt.utcoffset() == timedelta(hours=-4)  # EDT

    def test_tzlocal_instance(self):
        tz = tzlocal()
        assert tz is not None
        dt = datetime(2023, 10, 15, 12, 0, tzinfo=tz)
        assert dt.utcoffset() is not None

    def test_enfold(self):
        dt = datetime(2023, 11, 5, 1, 30)
        folded = enfold(dt, fold=1)
        assert folded.fold == 1

    def test_resolve_imaginary(self):
        tz = gettz("America/New_York")
        # 2:30 AM on spring-forward day doesn't exist
        dt = datetime(2023, 3, 12, 2, 30, tzinfo=tz)
        resolved = resolve_imaginary(dt)
        assert resolved is not None


class TestEndToEndCompat:
    """End-to-end workflows that dateutil users commonly perform."""

    def test_parse_and_add_relative(self):
        """Parse a date string and add a relative delta."""
        dt = parse("2023-01-31")
        result = dt + relativedelta(months=1)
        assert result == datetime(2023, 2, 28)

    def test_next_business_day(self):
        """Find the next weekday (Monday)."""
        dt = parse("2023-10-14")  # Saturday
        next_monday = dt + relativedelta(weekday=MO)
        assert next_monday.weekday() == 0  # Monday
        assert next_monday == datetime(2023, 10, 16)

    def test_last_day_of_month(self):
        """Get the last day of the current month."""
        dt = datetime(2023, 2, 15)
        last = dt + relativedelta(day=31)
        assert last == datetime(2023, 2, 28)

    def test_recurring_meeting(self):
        """Weekly meeting every Monday for 4 weeks."""
        meetings = list(rrule(
            WEEKLY,
            dtstart=datetime(2023, 10, 2),  # Monday
            count=4,
        ))
        assert len(meetings) == 4
        assert all(m.weekday() == 0 for m in meetings)

    def test_third_friday_of_each_month(self):
        """Options expiration — third Friday of each month."""
        expiries = list(rrule(
            MONTHLY,
            dtstart=datetime(2023, 1, 1),
            count=3,
            byweekday=FR(3),
        ))
        assert len(expiries) == 3
        assert all(d.weekday() == 4 for d in expiries)  # All Fridays
        assert expiries[0] == datetime(2023, 1, 20)

    def test_age_calculation(self):
        """Calculate someone's age."""
        birth = date(1990, 5, 15)
        today = date(2023, 10, 15)
        age = relativedelta(dt1=today, dt2=birth)
        assert age.years == 33
        assert age.months == 5
        assert age.days == 0

    def test_parse_with_timezone_and_convert(self):
        """Parse a timezone-aware datetime."""
        dt = parse("2023-10-15T14:30:00-04:00")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=-4)
