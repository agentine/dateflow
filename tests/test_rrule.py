"""Tests for dateflow.rrule — RFC 5545 recurrence rule engine."""

from datetime import datetime, date, timedelta
import pytest

from dateflow.rrule import (
    rrule,
    rruleset,
    rrulestr,
    YEARLY,
    MONTHLY,
    WEEKLY,
    DAILY,
    HOURLY,
    MINUTELY,
    SECONDLY,
    MO,
    TU,
    WE,
    TH,
    FR,
    SA,
    SU,
)


# ==========================================================================
# Frequency basics
# ==========================================================================


class TestDaily:
    def test_daily_count(self):
        r = rrule(DAILY, count=5, dtstart=datetime(2026, 3, 11))
        result = list(r)
        assert len(result) == 5
        assert result[0] == datetime(2026, 3, 11)
        assert result[-1] == datetime(2026, 3, 15)

    def test_daily_until(self):
        r = rrule(DAILY, dtstart=datetime(2026, 3, 1), until=datetime(2026, 3, 5))
        result = list(r)
        assert len(result) == 5
        assert result[-1] == datetime(2026, 3, 5)

    def test_daily_interval(self):
        r = rrule(DAILY, count=3, interval=2, dtstart=datetime(2026, 3, 1))
        result = list(r)
        assert result == [
            datetime(2026, 3, 1),
            datetime(2026, 3, 3),
            datetime(2026, 3, 5),
        ]


class TestWeekly:
    def test_weekly_count(self):
        r = rrule(WEEKLY, count=4, dtstart=datetime(2026, 3, 2))  # Monday
        result = list(r)
        assert len(result) == 4
        assert all((d - result[0]).days % 7 == 0 for d in result)

    def test_weekly_byweekday(self):
        r = rrule(
            WEEKLY,
            count=6,
            byweekday=(MO, WE, FR),
            dtstart=datetime(2026, 3, 2),  # Monday
        )
        result = list(r)
        assert len(result) == 6
        weekdays = {d.weekday() for d in result}
        assert weekdays == {0, 2, 4}  # Mon, Wed, Fri

    def test_weekly_interval(self):
        r = rrule(WEEKLY, count=3, interval=2, dtstart=datetime(2026, 3, 2))
        result = list(r)
        # Every two weeks
        assert (result[1] - result[0]).days == 14
        assert (result[2] - result[1]).days == 14


class TestMonthly:
    def test_monthly_count(self):
        r = rrule(MONTHLY, count=4, dtstart=datetime(2026, 1, 15))
        result = list(r)
        assert len(result) == 4
        assert [d.month for d in result] == [1, 2, 3, 4]
        assert all(d.day == 15 for d in result)

    def test_monthly_bymonthday(self):
        r = rrule(MONTHLY, count=4, bymonthday=1, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert all(d.day == 1 for d in result)
        assert [d.month for d in result] == [1, 2, 3, 4]

    def test_monthly_byweekday_nth(self):
        """Second Tuesday of each month."""
        r = rrule(MONTHLY, count=3, byweekday=TU(2), dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.weekday() == 1  # Tuesday
            assert 8 <= d.day <= 14  # Second week

    def test_monthly_last_friday(self):
        r = rrule(MONTHLY, count=3, byweekday=FR(-1), dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.weekday() == 4  # Friday
            # Last Friday: no Friday later in the month
            next_week = d + timedelta(days=7)
            assert next_week.month != d.month

    def test_monthly_negative_monthday(self):
        """Last day of the month."""
        r = rrule(MONTHLY, count=3, bymonthday=-1, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert result[0] == datetime(2026, 1, 31)
        assert result[1] == datetime(2026, 2, 28)
        assert result[2] == datetime(2026, 3, 31)

    def test_monthly_interval(self):
        r = rrule(MONTHLY, count=3, interval=3, dtstart=datetime(2026, 1, 15))
        result = list(r)
        assert [d.month for d in result] == [1, 4, 7]


class TestYearly:
    def test_yearly_count(self):
        r = rrule(YEARLY, count=3, dtstart=datetime(2026, 3, 11))
        result = list(r)
        assert len(result) == 3
        assert [d.year for d in result] == [2026, 2027, 2028]
        assert all(d.month == 3 and d.day == 11 for d in result)

    def test_yearly_bymonth(self):
        r = rrule(YEARLY, count=4, bymonth=(1, 7), bymonthday=1, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert len(result) == 4
        assert [(d.year, d.month) for d in result] == [
            (2026, 1),
            (2026, 7),
            (2027, 1),
            (2027, 7),
        ]

    def test_yearly_byyearday(self):
        r = rrule(YEARLY, count=3, byyearday=1, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert all(d.month == 1 and d.day == 1 for d in result)

    def test_yearly_byweekno(self):
        r = rrule(
            YEARLY,
            count=3,
            byweekno=1,
            byweekday=MO,
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.isocalendar()[1] == 1
            assert d.weekday() == 0  # Monday


class TestHourly:
    def test_hourly_count(self):
        r = rrule(HOURLY, count=5, dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert len(result) == 5
        assert result[0] == datetime(2026, 3, 11, 10, 0, 0)
        assert result[-1] == datetime(2026, 3, 11, 14, 0, 0)

    def test_hourly_byhour(self):
        r = rrule(
            HOURLY,
            count=6,
            byhour=(9, 12, 17),
            dtstart=datetime(2026, 3, 11, 0, 0, 0),
        )
        result = list(r)
        assert len(result) == 6
        hours = [d.hour for d in result]
        assert hours == [9, 12, 17, 9, 12, 17]


class TestMinutely:
    def test_minutely_count(self):
        r = rrule(MINUTELY, count=5, dtstart=datetime(2026, 3, 11, 10, 30, 0))
        result = list(r)
        assert len(result) == 5
        assert result[0] == datetime(2026, 3, 11, 10, 30, 0)
        assert result[1] == datetime(2026, 3, 11, 10, 31, 0)

    def test_minutely_interval(self):
        r = rrule(MINUTELY, count=3, interval=15, dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert result == [
            datetime(2026, 3, 11, 10, 0, 0),
            datetime(2026, 3, 11, 10, 15, 0),
            datetime(2026, 3, 11, 10, 30, 0),
        ]


class TestSecondly:
    def test_secondly_count(self):
        r = rrule(SECONDLY, count=5, dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert len(result) == 5
        assert result[-1] == datetime(2026, 3, 11, 10, 0, 4)

    def test_secondly_interval(self):
        r = rrule(SECONDLY, count=3, interval=30, dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert result == [
            datetime(2026, 3, 11, 10, 0, 0),
            datetime(2026, 3, 11, 10, 0, 30),
            datetime(2026, 3, 11, 10, 1, 0),
        ]


# ==========================================================================
# BYXXX modifiers
# ==========================================================================


class TestByMonth:
    def test_daily_bymonth(self):
        """Daily, but only in March and June."""
        r = rrule(DAILY, count=5, bymonth=(3, 6), dtstart=datetime(2026, 3, 1))
        result = list(r)
        assert len(result) == 5
        assert all(d.month == 3 for d in result)

    def test_monthly_bymonth(self):
        r = rrule(MONTHLY, count=4, bymonth=(1, 4, 7, 10), bymonthday=15, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert [d.month for d in result] == [1, 4, 7, 10]


class TestByMonthDay:
    def test_daily_bymonthday(self):
        r = rrule(DAILY, count=3, bymonthday=(1, 15), dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert result[0] == datetime(2026, 1, 1)
        assert result[1] == datetime(2026, 1, 15)
        assert result[2] == datetime(2026, 2, 1)


class TestByWeekday:
    def test_daily_byweekday(self):
        """Daily, only on weekdays (Mon-Fri)."""
        r = rrule(
            DAILY,
            count=5,
            byweekday=(MO, TU, WE, TH, FR),
            dtstart=datetime(2026, 3, 9),  # Monday
        )
        result = list(r)
        assert len(result) == 5
        assert all(d.weekday() < 5 for d in result)

    def test_monthly_byweekday_all_mondays(self):
        """All Mondays in a month."""
        r = rrule(MONTHLY, count=4, byweekday=MO, dtstart=datetime(2026, 3, 1))
        result = list(r)
        assert len(result) == 4
        assert all(d.weekday() == 0 for d in result)
        assert all(d.month == 3 for d in result)


class TestByHour:
    def test_daily_byhour(self):
        r = rrule(DAILY, count=6, byhour=(9, 17), dtstart=datetime(2026, 3, 11))
        result = list(r)
        assert len(result) == 6
        hours = [d.hour for d in result]
        assert hours == [9, 17, 9, 17, 9, 17]


class TestByMinute:
    def test_hourly_byminute(self):
        r = rrule(HOURLY, count=6, byminute=(0, 30), dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert len(result) == 6
        minutes = [d.minute for d in result]
        assert minutes == [0, 30, 0, 30, 0, 30]


class TestBySecond:
    def test_minutely_bysecond(self):
        r = rrule(MINUTELY, count=6, bysecond=(0, 30), dtstart=datetime(2026, 3, 11, 10, 0, 0))
        result = list(r)
        assert len(result) == 6
        seconds = [d.second for d in result]
        assert seconds == [0, 30, 0, 30, 0, 30]


class TestBySetPos:
    def test_monthly_bysetpos_last(self):
        """Last weekday of the month."""
        r = rrule(
            MONTHLY,
            count=3,
            byweekday=(MO, TU, WE, TH, FR),
            bysetpos=-1,
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 3
        # Each should be a weekday and the last weekday of its month
        for d in result:
            assert d.weekday() < 5
            # Next weekday would be in the next month
            next_day = d + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            assert next_day.month != d.month

    def test_monthly_bysetpos_first(self):
        """First weekday of the month."""
        r = rrule(
            MONTHLY,
            count=3,
            byweekday=(MO, TU, WE, TH, FR),
            bysetpos=1,
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.weekday() < 5
            assert d.day <= 3  # First weekday is within first 3 days


class TestByEaster:
    def test_byeaster_zero(self):
        """Easter Sunday."""
        r = rrule(YEARLY, count=3, byeaster=0, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert len(result) == 3
        from dateflow.easter import easter
        for d in result:
            assert d.date() == easter(d.year)

    def test_byeaster_offset(self):
        """Good Friday = Easter - 2."""
        r = rrule(YEARLY, count=2, byeaster=-2, dtstart=datetime(2026, 1, 1))
        result = list(r)
        from dateflow.easter import easter
        for d in result:
            assert d.date() == easter(d.year) - timedelta(days=2)


# ==========================================================================
# count and until limits
# ==========================================================================


class TestLimits:
    def test_count_zero(self):
        r = rrule(DAILY, count=0, dtstart=datetime(2026, 3, 11))
        assert list(r) == []

    def test_count_and_until_exclusive(self):
        with pytest.raises(ValueError):
            rrule(DAILY, count=5, until=datetime(2026, 3, 15))

    def test_until_inclusive(self):
        r = rrule(DAILY, dtstart=datetime(2026, 3, 1), until=datetime(2026, 3, 3))
        result = list(r)
        assert result[-1] == datetime(2026, 3, 3)

    def test_until_exclusive_boundary(self):
        r = rrule(DAILY, dtstart=datetime(2026, 3, 1), until=datetime(2026, 3, 3, 12, 0))
        result = list(r)
        # Should include March 3 (at 0:00) since it's <= until
        assert datetime(2026, 3, 3) in result
        assert datetime(2026, 3, 4) not in result


# ==========================================================================
# Query methods
# ==========================================================================


class TestQueryMethods:
    def setup_method(self):
        self.r = rrule(DAILY, count=10, dtstart=datetime(2026, 3, 1))

    def test_after(self):
        result = self.r.after(datetime(2026, 3, 5))
        assert result == datetime(2026, 3, 6)

    def test_after_inc(self):
        result = self.r.after(datetime(2026, 3, 5), inc=True)
        assert result == datetime(2026, 3, 5)

    def test_before(self):
        result = self.r.before(datetime(2026, 3, 5))
        assert result == datetime(2026, 3, 4)

    def test_before_inc(self):
        result = self.r.before(datetime(2026, 3, 5), inc=True)
        assert result == datetime(2026, 3, 5)

    def test_between(self):
        result = self.r.between(datetime(2026, 3, 3), datetime(2026, 3, 7))
        assert result == [
            datetime(2026, 3, 4),
            datetime(2026, 3, 5),
            datetime(2026, 3, 6),
        ]

    def test_between_inc(self):
        result = self.r.between(
            datetime(2026, 3, 3), datetime(2026, 3, 7), inc=True
        )
        assert result == [
            datetime(2026, 3, 3),
            datetime(2026, 3, 4),
            datetime(2026, 3, 5),
            datetime(2026, 3, 6),
            datetime(2026, 3, 7),
        ]

    def test_count_method(self):
        assert self.r.count() == 10

    def test_getitem(self):
        assert self.r[0] == datetime(2026, 3, 1)
        assert self.r[4] == datetime(2026, 3, 5)

    def test_getitem_negative(self):
        assert self.r[-1] == datetime(2026, 3, 10)

    def test_getitem_slice(self):
        result = self.r[2:5]
        assert result == [
            datetime(2026, 3, 3),
            datetime(2026, 3, 4),
            datetime(2026, 3, 5),
        ]

    def test_contains(self):
        assert datetime(2026, 3, 5) in self.r
        assert datetime(2026, 3, 15) not in self.r


# ==========================================================================
# rruleset
# ==========================================================================


class TestRRuleSet:
    def test_basic_rruleset(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=5, dtstart=datetime(2026, 3, 1)))
        result = list(rs)
        assert len(result) == 5

    def test_rruleset_with_rdate(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=3, dtstart=datetime(2026, 3, 1)))
        rs.rdate(datetime(2026, 3, 15))
        result = list(rs)
        assert len(result) == 4
        assert datetime(2026, 3, 15) in result

    def test_rruleset_with_exdate(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=5, dtstart=datetime(2026, 3, 1)))
        rs.exdate(datetime(2026, 3, 3))
        result = list(rs)
        assert len(result) == 4
        assert datetime(2026, 3, 3) not in result

    def test_rruleset_with_exrule(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=14, dtstart=datetime(2026, 3, 1)))
        # Exclude weekends
        rs.exrule(rrule(WEEKLY, count=4, byweekday=(SA, SU), dtstart=datetime(2026, 3, 1)))
        result = list(rs)
        assert all(d.weekday() < 5 for d in result)

    def test_rruleset_merge_sorted(self):
        rs = rruleset()
        rs.rrule(rrule(WEEKLY, count=3, byweekday=MO, dtstart=datetime(2026, 3, 2)))
        rs.rrule(rrule(WEEKLY, count=3, byweekday=WE, dtstart=datetime(2026, 3, 4)))
        result = list(rs)
        assert len(result) == 6
        assert result == sorted(result)

    def test_rruleset_dedup(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=5, dtstart=datetime(2026, 3, 1)))
        rs.rdate(datetime(2026, 3, 3))  # Duplicate of a rule result
        result = list(rs)
        assert len(result) == 5  # No duplicate

    def test_rruleset_after(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=10, dtstart=datetime(2026, 3, 1)))
        assert rs.after(datetime(2026, 3, 5)) == datetime(2026, 3, 6)

    def test_rruleset_before(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=10, dtstart=datetime(2026, 3, 1)))
        assert rs.before(datetime(2026, 3, 5)) == datetime(2026, 3, 4)

    def test_rruleset_between(self):
        rs = rruleset()
        rs.rrule(rrule(DAILY, count=10, dtstart=datetime(2026, 3, 1)))
        result = rs.between(datetime(2026, 3, 3), datetime(2026, 3, 7))
        assert len(result) == 3


# ==========================================================================
# rrulestr parsing
# ==========================================================================


class TestRRuleStr:
    def test_simple_freq_count(self):
        r = rrulestr("FREQ=DAILY;COUNT=5", dtstart=datetime(2026, 3, 1))
        result = list(r)
        assert len(result) == 5

    def test_with_rrule_prefix(self):
        r = rrulestr("RRULE:FREQ=DAILY;COUNT=5", dtstart=datetime(2026, 3, 1))
        result = list(r)
        assert len(result) == 5

    def test_weekly_byday(self):
        r = rrulestr(
            "FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=6",
            dtstart=datetime(2026, 3, 2),
        )
        result = list(r)
        assert len(result) == 6
        weekdays = {d.weekday() for d in result}
        assert weekdays == {0, 2, 4}

    def test_monthly_byday_nth(self):
        r = rrulestr(
            "FREQ=MONTHLY;BYDAY=2TU;COUNT=3",
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.weekday() == 1  # Tuesday
            assert 8 <= d.day <= 14

    def test_monthly_byday_negative(self):
        r = rrulestr(
            "FREQ=MONTHLY;BYDAY=-1FR;COUNT=3",
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 3
        for d in result:
            assert d.weekday() == 4  # Friday

    def test_with_until(self):
        r = rrulestr(
            "FREQ=DAILY;UNTIL=20260310T000000",
            dtstart=datetime(2026, 3, 1),
        )
        result = list(r)
        assert result[-1] == datetime(2026, 3, 10)

    def test_with_interval(self):
        r = rrulestr(
            "FREQ=DAILY;INTERVAL=3;COUNT=3",
            dtstart=datetime(2026, 3, 1),
        )
        result = list(r)
        assert result == [
            datetime(2026, 3, 1),
            datetime(2026, 3, 4),
            datetime(2026, 3, 7),
        ]

    def test_multiline_with_dtstart(self):
        s = """\
DTSTART:20260301T000000
RRULE:FREQ=DAILY;COUNT=3
"""
        r = rrulestr(s)
        result = list(r)
        assert len(result) == 3
        assert result[0] == datetime(2026, 3, 1)

    def test_multiline_with_exdate(self):
        s = """\
DTSTART:20260301T000000
RRULE:FREQ=DAILY;COUNT=5
EXDATE:20260303T000000
"""
        r = rrulestr(s)
        result = list(r)
        assert len(result) == 4
        assert datetime(2026, 3, 3) not in result

    def test_multiline_with_rdate(self):
        s = """\
DTSTART:20260301T000000
RRULE:FREQ=DAILY;COUNT=3
RDATE:20260315T000000
"""
        r = rrulestr(s)
        result = list(r)
        assert len(result) == 4
        assert datetime(2026, 3, 15) in result

    def test_forceset(self):
        r = rrulestr(
            "RRULE:FREQ=DAILY;COUNT=3",
            dtstart=datetime(2026, 3, 1),
            forceset=True,
        )
        assert isinstance(r, rruleset)

    def test_bymonth(self):
        r = rrulestr(
            "FREQ=MONTHLY;BYMONTH=1,7;BYMONTHDAY=1;COUNT=4",
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 4
        assert [d.month for d in result] == [1, 7, 1, 7]

    def test_byhour(self):
        r = rrulestr(
            "FREQ=DAILY;BYHOUR=9,17;COUNT=4",
            dtstart=datetime(2026, 3, 1),
        )
        result = list(r)
        assert len(result) == 4
        assert [d.hour for d in result] == [9, 17, 9, 17]


# ==========================================================================
# Edge cases
# ==========================================================================


class TestEdgeCases:
    def test_leap_year_feb29(self):
        """Yearly on Feb 29 - only hits leap years."""
        r = rrule(YEARLY, count=2, bymonth=2, bymonthday=29, dtstart=datetime(2024, 2, 29))
        result = list(r)
        assert result[0] == datetime(2024, 2, 29)
        assert result[1] == datetime(2028, 2, 29)

    def test_month_boundary_31st(self):
        """Monthly on the 31st - skips months without 31 days."""
        r = rrule(MONTHLY, count=4, bymonthday=31, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert [d.month for d in result] == [1, 3, 5, 7]
        assert all(d.day == 31 for d in result)

    def test_empty_result(self):
        """Rule that produces no matches before count limit."""
        r = rrule(DAILY, count=0, dtstart=datetime(2026, 1, 1))
        assert list(r) == []

    def test_cache_consistency(self):
        """Cached rule returns same results on second iteration."""
        r = rrule(DAILY, count=5, dtstart=datetime(2026, 3, 1), cache=True)
        first = list(r)
        second = list(r)
        assert first == second

    def test_dtstart_preserved(self):
        """dtstart is always the first occurrence if it matches."""
        r = rrule(WEEKLY, count=3, dtstart=datetime(2026, 3, 11, 14, 30))
        result = list(r)
        assert result[0] == datetime(2026, 3, 11, 14, 30)

    def test_time_preserved(self):
        """Time component from dtstart is preserved."""
        r = rrule(DAILY, count=3, dtstart=datetime(2026, 3, 11, 9, 30, 45))
        result = list(r)
        for d in result:
            assert d.hour == 9
            assert d.minute == 30
            assert d.second == 45

    def test_yearly_negative_yearday(self):
        """Last day of the year via negative byyearday."""
        r = rrule(YEARLY, count=2, byyearday=-1, dtstart=datetime(2026, 1, 1))
        result = list(r)
        assert result[0] == datetime(2026, 12, 31)
        assert result[1] == datetime(2027, 12, 31)

    def test_after_returns_none(self):
        r = rrule(DAILY, count=3, dtstart=datetime(2026, 3, 1))
        assert r.after(datetime(2026, 3, 10)) is None

    def test_before_returns_none(self):
        r = rrule(DAILY, count=3, dtstart=datetime(2026, 3, 1))
        assert r.before(datetime(2026, 2, 28)) is None

    def test_wkst_parameter(self):
        """wkst changes the week start day for WEEKLY rules."""
        r = rrule(
            WEEKLY,
            count=3,
            byweekday=(MO, FR),
            wkst=SU,
            dtstart=datetime(2026, 3, 2),  # Monday
        )
        result = list(r)
        assert len(result) == 3

    def test_multiple_bymonthday(self):
        """Multiple monthdays."""
        r = rrule(
            MONTHLY,
            count=6,
            bymonthday=(1, 15),
            dtstart=datetime(2026, 1, 1),
        )
        result = list(r)
        assert len(result) == 6
        assert [d.day for d in result] == [1, 15, 1, 15, 1, 15]
