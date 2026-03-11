"""Tests for dateflow.relativedelta — dateutil-compatible date arithmetic."""

from datetime import date, datetime

import pytest

from dateflow.relativedelta import (
    FR,
    MO,
    SA,
    SU,
    TH,
    TU,
    WE,
    relativedelta,
    weekday,
)


# ---------------------------------------------------------------------------
# weekday helper
# ---------------------------------------------------------------------------
class TestWeekday:
    def test_basic_weekday_values(self):
        assert MO.weekday == 0
        assert TU.weekday == 1
        assert WE.weekday == 2
        assert TH.weekday == 3
        assert FR.weekday == 4
        assert SA.weekday == 5
        assert SU.weekday == 6

    def test_weekday_n_is_none_by_default(self):
        assert MO.n is None

    def test_weekday_call_creates_nth(self):
        f2 = FR(2)
        assert f2.weekday == 4
        assert f2.n == 2

    def test_weekday_call_negative_n(self):
        f_neg1 = FR(-1)
        assert f_neg1.n == -1

    def test_weekday_call_zero_raises(self):
        with pytest.raises(ValueError):
            FR(0)

    def test_weekday_equality(self):
        assert FR == weekday(4)
        assert FR(2) == weekday(4, 2)
        assert FR != SA
        assert FR(1) != FR(2)

    def test_weekday_hash(self):
        assert hash(FR) == hash(weekday(4))
        s = {FR, FR(2), SA}
        assert len(s) == 3

    def test_weekday_repr(self):
        assert repr(MO) == "MO"
        assert repr(FR(2)) == "FR(+2)"
        assert repr(FR(-1)) == "FR(-1)"


# ---------------------------------------------------------------------------
# relativedelta construction
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_default_is_falsy(self):
        rd = relativedelta()
        assert not rd

    def test_relative_fields(self):
        rd = relativedelta(years=1, months=2, days=3, hours=4, minutes=5, seconds=6, microseconds=7)
        assert rd.years == 1
        assert rd.months == 2
        assert rd.days == 3
        assert rd.hours == 4
        assert rd.minutes == 5
        assert rd.seconds == 6
        assert rd.microseconds == 7

    def test_absolute_fields(self):
        rd = relativedelta(year=2026, month=3, day=11, hour=10, minute=30, second=0, microsecond=0)
        assert rd.year == 2026
        assert rd.month == 3
        assert rd.day == 11

    def test_weeks_converted_to_days(self):
        rd = relativedelta(weeks=2, days=3)
        assert rd.days == 17

    def test_month_normalization(self):
        rd = relativedelta(months=14)
        assert rd.years == 1
        assert rd.months == 2

    def test_negative_month_normalization(self):
        rd = relativedelta(months=-14)
        assert rd.years == -1
        assert rd.months == -2

    def test_weekday_int_conversion(self):
        rd = relativedelta(weekday=4)
        assert rd.weekday == FR

    def test_weekday_object(self):
        rd = relativedelta(weekday=FR(2))
        assert rd.weekday == FR(2)

    def test_single_dt_raises(self):
        with pytest.raises(TypeError):
            relativedelta(datetime(2026, 1, 1))


# ---------------------------------------------------------------------------
# Date arithmetic
# ---------------------------------------------------------------------------
class TestArithmetic:
    def test_add_months_basic(self):
        dt = datetime(2026, 1, 15)
        result = dt + relativedelta(months=1)
        assert result == datetime(2026, 2, 15)

    def test_month_end_clipping(self):
        # Jan 31 + 1 month = Feb 28 (not Feb 31)
        dt = datetime(2026, 1, 31)
        result = dt + relativedelta(months=1)
        assert result == datetime(2026, 2, 28)

    def test_month_end_clipping_leap_year(self):
        dt = datetime(2024, 1, 31)
        result = dt + relativedelta(months=1)
        assert result == datetime(2024, 2, 29)

    def test_add_years(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(years=1)
        assert result == datetime(2027, 3, 11)

    def test_leap_year_feb29_plus_year(self):
        dt = datetime(2024, 2, 29)
        result = dt + relativedelta(years=1)
        assert result == datetime(2025, 2, 28)

    def test_add_days(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(days=5)
        assert result == datetime(2026, 3, 16)

    def test_add_complex(self):
        dt = datetime(2026, 1, 31)
        result = dt + relativedelta(years=1, months=2, days=3)
        # Jan 31 + 1y = 2027-01-31, + 2m = 2027-03-31, + 3d = 2027-04-03
        assert result == datetime(2027, 4, 3)

    def test_subtract_months(self):
        dt = datetime(2026, 3, 31)
        result = dt + relativedelta(months=-1)
        assert result == datetime(2026, 2, 28)

    def test_radd(self):
        # datetime + relativedelta (via __radd__)
        dt = datetime(2026, 1, 1)
        result = dt + relativedelta(days=10)
        assert result == datetime(2026, 1, 11)

    def test_rsub(self):
        dt = datetime(2026, 3, 11)
        result = dt - relativedelta(months=1)
        assert result == datetime(2026, 2, 11)

    def test_absolute_day(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(day=1)
        assert result == datetime(2026, 3, 1)

    def test_absolute_month_and_day(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(month=1, day=1)
        assert result == datetime(2026, 1, 1)

    def test_absolute_year(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(year=2030)
        assert result == datetime(2030, 3, 11)

    def test_date_support(self):
        d = date(2026, 1, 31)
        result = d + relativedelta(months=1)
        assert result == date(2026, 2, 28)
        assert type(result) is date

    def test_datetime_preserves_time(self):
        dt = datetime(2026, 3, 11, 14, 30, 0)
        result = dt + relativedelta(months=1)
        assert result == datetime(2026, 4, 11, 14, 30, 0)

    def test_add_hours(self):
        dt = datetime(2026, 3, 11, 10, 0)
        result = dt + relativedelta(hours=5)
        assert result == datetime(2026, 3, 11, 15, 0)

    def test_cross_month_with_days(self):
        dt = datetime(2026, 1, 31)
        result = dt + relativedelta(days=1)
        assert result == datetime(2026, 2, 1)

    def test_absolute_year_leap_to_nonleap(self):
        """Absolute year on Feb 29 of leap year to non-leap year clips day."""
        dt = datetime(2024, 2, 29, 12, 0)
        result = dt + relativedelta(year=2025)
        assert result == datetime(2025, 2, 28, 12, 0)

    def test_absolute_year_nonleap_to_leap(self):
        """Absolute year on Feb 28 of non-leap year to leap year keeps day."""
        dt = datetime(2025, 2, 28, 12, 0)
        result = dt + relativedelta(year=2024)
        assert result == datetime(2024, 2, 28, 12, 0)

    def test_absolute_year_leap_to_nonleap_date(self):
        """Same leap-year clip bug with date (not datetime)."""
        d = date(2024, 2, 29)
        result = d + relativedelta(year=2023)
        assert result == date(2023, 2, 28)

    def test_absolute_and_relative_year(self):
        """Absolute year=2020 plus relative years=5 should yield 2025."""
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(year=2020, years=5)
        assert result.year == 2025

    def test_absolute_and_relative_month(self):
        """Absolute month=1 plus relative months=2 should yield month 3."""
        dt = datetime(2026, 6, 15)
        result = dt + relativedelta(month=1, months=2)
        assert result.month == 3

    def test_absolute_and_relative_hour(self):
        """Absolute hour=10 plus relative hours=3 should yield hour 13."""
        dt = datetime(2026, 3, 11, 8, 0, 0)
        result = dt + relativedelta(hour=10, hours=3)
        assert result.hour == 13

    def test_absolute_and_relative_minute(self):
        """Absolute minute=15 plus relative minutes=10 should yield minute 25."""
        dt = datetime(2026, 3, 11, 8, 0, 0)
        result = dt + relativedelta(minute=15, minutes=10)
        assert result.minute == 25

    def test_absolute_and_relative_second(self):
        """Absolute second=30 plus relative seconds=15 should yield second 45."""
        dt = datetime(2026, 3, 11, 8, 0, 0)
        result = dt + relativedelta(second=30, seconds=15)
        assert result.second == 45

    def test_absolute_and_relative_microsecond(self):
        """Absolute microsecond=100 plus relative microseconds=200 should yield 300."""
        dt = datetime(2026, 3, 11, 8, 0, 0, 0)
        result = dt + relativedelta(microsecond=100, microseconds=200)
        assert result.microsecond == 300


# ---------------------------------------------------------------------------
# Weekday targeting
# ---------------------------------------------------------------------------
class TestWeekdayTargeting:
    def test_next_friday_from_wednesday(self):
        # 2026-03-11 is Wednesday
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(weekday=FR)
        assert result == datetime(2026, 3, 13)

    def test_same_weekday_stays(self):
        # 2026-03-11 is Wednesday
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(weekday=WE)
        assert result == datetime(2026, 3, 11)

    def test_next_monday(self):
        dt = datetime(2026, 3, 11)  # Wednesday
        result = dt + relativedelta(weekday=MO)
        assert result == datetime(2026, 3, 16)

    def test_nth_weekday_positive(self):
        dt = datetime(2026, 3, 11)  # Wednesday
        result = dt + relativedelta(weekday=FR(2))
        # 1st Friday = Mar 13, 2nd Friday = Mar 20
        assert result == datetime(2026, 3, 20)

    def test_nth_weekday_negative(self):
        dt = datetime(2026, 3, 20)  # Friday
        result = dt + relativedelta(weekday=FR(-1))
        # Already on Friday, -1 means this Friday
        assert result == datetime(2026, 3, 20)

    def test_nth_weekday_negative_different_day(self):
        dt = datetime(2026, 3, 18)  # Wednesday
        result = dt + relativedelta(weekday=FR(-1))
        # Previous Friday = Mar 13
        assert result == datetime(2026, 3, 13)

    def test_weekday_with_month_offset(self):
        dt = datetime(2026, 3, 11)
        result = dt + relativedelta(months=1, weekday=FR)
        # April 11 is Saturday, next Friday = April 17
        assert result.weekday() == 4  # Friday


# ---------------------------------------------------------------------------
# Delta between dates
# ---------------------------------------------------------------------------
class TestDeltaBetweenDates:
    def test_simple_delta(self):
        rd = relativedelta(datetime(2026, 3, 11), datetime(2025, 1, 1))
        assert rd.years == 1
        assert rd.months == 2
        assert rd.days == 10

    def test_delta_same_date(self):
        rd = relativedelta(datetime(2026, 1, 1), datetime(2026, 1, 1))
        assert not rd  # should be falsy

    def test_delta_one_month(self):
        rd = relativedelta(datetime(2026, 2, 1), datetime(2026, 1, 1))
        assert rd.years == 0
        assert rd.months == 1
        assert rd.days == 0

    def test_delta_negative(self):
        rd = relativedelta(datetime(2025, 1, 1), datetime(2026, 3, 11))
        assert rd.years == -1
        assert rd.months == -2

    def test_delta_with_time(self):
        rd = relativedelta(
            datetime(2026, 3, 11, 15, 30),
            datetime(2026, 3, 11, 10, 0),
        )
        assert rd.hours == 5
        assert rd.minutes == 30

    def test_delta_negative_one_second(self):
        """Negative sub-day delta should not produce spurious days=-1."""
        rd = relativedelta(
            datetime(2026, 3, 11, 9, 59, 59),
            datetime(2026, 3, 11, 10, 0, 0),
        )
        assert rd.days == 0
        assert rd.hours == 0
        assert rd.minutes == 0
        assert rd.seconds == -1

    def test_delta_negative_hours(self):
        """Negative hour delta should decompose correctly."""
        rd = relativedelta(
            datetime(2026, 3, 11, 8, 0, 0),
            datetime(2026, 3, 11, 10, 0, 0),
        )
        assert rd.days == 0
        assert rd.hours == -2
        assert rd.minutes == 0
        assert rd.seconds == 0

    def test_delta_negative_microseconds(self):
        """Negative delta with microseconds should not double-count."""
        dt1 = datetime(2026, 3, 11, 10, 0, 0, 0)
        dt2 = datetime(2026, 3, 11, 10, 0, 0, 500000)
        rd = relativedelta(dt1, dt2)
        # -0.5 seconds: seconds should borrow, microseconds positive
        assert rd.seconds == -1
        assert rd.microseconds == 500000
        # Roundtrip: dt2 + rd should equal dt1
        assert dt2 + rd == dt1

    def test_delta_negative_microseconds_roundtrip(self):
        """Microsecond roundtrip for various negative deltas."""
        pairs = [
            (datetime(2026, 1, 1, 0, 0, 0, 0), datetime(2026, 1, 1, 0, 0, 0, 1)),
            (datetime(2026, 1, 1, 0, 0, 0, 0), datetime(2026, 1, 1, 0, 0, 1, 750000)),
            (datetime(2026, 6, 15, 12, 0, 0, 0), datetime(2026, 6, 15, 12, 0, 0, 999999)),
        ]
        for dt1, dt2 in pairs:
            rd = relativedelta(dt1, dt2)
            assert dt2 + rd == dt1, f"Roundtrip failed for {dt1} - {dt2}: {rd}"


# ---------------------------------------------------------------------------
# Leapdays
# ---------------------------------------------------------------------------
class TestLeapdays:
    def test_leapdays_on_leap_year(self):
        """leapdays should add extra days on leap years after Feb."""
        dt = datetime(2024, 3, 1)  # 2024 is a leap year
        rd = relativedelta(leapdays=1)
        result = dt + rd
        assert result == datetime(2024, 3, 2)

    def test_leapdays_on_non_leap_year(self):
        """leapdays should have no effect on non-leap years."""
        dt = datetime(2025, 3, 1)  # 2025 is not a leap year
        rd = relativedelta(leapdays=1)
        result = dt + rd
        assert result == datetime(2025, 3, 1)  # unchanged

    def test_leapdays_before_march(self):
        """leapdays should have no effect when month <= 2."""
        dt = datetime(2024, 2, 15)  # leap year but month <= 2
        rd = relativedelta(leapdays=1)
        result = dt + rd
        assert result == datetime(2024, 2, 15)  # unchanged

    def test_leapdays_with_date(self):
        """leapdays should work with date objects too."""
        dt = date(2024, 4, 10)
        rd = relativedelta(leapdays=1)
        result = dt + rd
        assert result == date(2024, 4, 11)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------
class TestOperators:
    def test_negation(self):
        rd = -relativedelta(years=1, months=2, days=3)
        assert rd.years == -1
        assert rd.months == -2
        assert rd.days == -3

    def test_abs(self):
        rd = abs(relativedelta(years=-1, months=-2, days=-3))
        assert rd.years == 1
        assert rd.months == 2
        assert rd.days == 3

    def test_add_relativedeltas(self):
        r1 = relativedelta(years=1, months=3)
        r2 = relativedelta(months=9, days=5)
        result = r1 + r2
        assert result.years == 2
        assert result.months == 0
        assert result.days == 5

    def test_sub_relativedeltas(self):
        r1 = relativedelta(years=2, months=3)
        r2 = relativedelta(years=1, months=1)
        result = r1 - r2
        assert result.years == 1
        assert result.months == 2

    def test_multiply(self):
        rd = relativedelta(years=1, months=3) * 2
        assert rd.years == 2
        assert rd.months == 6

    def test_rmultiply(self):
        rd = 3 * relativedelta(days=10)
        assert rd.days == 30


# ---------------------------------------------------------------------------
# Equality, hash, repr, bool
# ---------------------------------------------------------------------------
class TestEqualityAndRepr:
    def test_equality(self):
        r1 = relativedelta(years=1, months=2)
        r2 = relativedelta(years=1, months=2)
        assert r1 == r2

    def test_inequality(self):
        r1 = relativedelta(years=1)
        r2 = relativedelta(years=2)
        assert r1 != r2

    def test_hash_equal(self):
        r1 = relativedelta(years=1, months=2)
        r2 = relativedelta(years=1, months=2)
        assert hash(r1) == hash(r2)

    def test_hash_usable_in_set(self):
        s = {relativedelta(years=1), relativedelta(years=1), relativedelta(years=2)}
        assert len(s) == 2

    def test_bool_false(self):
        assert not relativedelta()

    def test_bool_true_relative(self):
        assert relativedelta(days=1)

    def test_bool_true_absolute(self):
        assert relativedelta(day=1)

    def test_bool_true_weekday(self):
        assert relativedelta(weekday=FR)

    def test_repr_relative(self):
        rd = relativedelta(years=1, months=-2)
        r = repr(rd)
        assert "years=+1" in r
        assert "months=-2" in r

    def test_repr_absolute(self):
        rd = relativedelta(day=15, month=3)
        r = repr(rd)
        assert "day=15" in r
        assert "month=3" in r

    def test_repr_weekday(self):
        rd = relativedelta(weekday=FR(2))
        assert "FR(+2)" in repr(rd)

    def test_not_equal_to_other_types(self):
        rd = relativedelta(years=1)
        assert rd != "not a relativedelta"
        assert rd != 42


class TestDateTimeUpgrade:
    """date objects should be upgraded to datetime when time fields are present."""

    def test_date_plus_hours(self):
        result = date(2026, 3, 11) + relativedelta(hours=5)
        assert isinstance(result, datetime)
        assert result == datetime(2026, 3, 11, 5, 0)

    def test_date_plus_minutes_seconds(self):
        result = date(2026, 3, 11) + relativedelta(minutes=30, seconds=15)
        assert isinstance(result, datetime)
        assert result == datetime(2026, 3, 11, 0, 30, 15)

    def test_date_plus_absolute_hour(self):
        result = date(2026, 3, 11) + relativedelta(hour=14, minute=30)
        assert isinstance(result, datetime)
        assert result == datetime(2026, 3, 11, 14, 30)

    def test_date_without_time_fields_stays_date(self):
        result = date(2026, 3, 11) + relativedelta(days=5)
        assert type(result) is date
        assert result == date(2026, 3, 16)


class TestMixedDateDatetimeDelta:
    """_compute_delta with mixed date/datetime inputs."""

    def test_datetime_minus_date(self):
        delta = relativedelta(datetime(2026, 3, 11, 15, 0, 0), date(2026, 3, 11))
        assert delta.hours == 15

    def test_date_minus_datetime(self):
        delta = relativedelta(date(2026, 3, 11), datetime(2026, 3, 11, 3, 0))
        assert delta.hours == -3


class TestTopLevelImports:
    """__init__.py exports public API symbols."""

    def test_imports(self):
        from dateflow import relativedelta, weekday, MO, TU, WE, TH, FR, SA, SU, easter
        assert relativedelta is not None
        assert weekday is not None
        assert MO.weekday == 0
        assert easter is not None
