"""Tests for dateflow.parser — date string parsing."""

from datetime import datetime, timedelta, timezone

import pytest

from dateflow.parser import ParserError, parse
from dateflow.tz import tzoffset, tzutc


# Use a fixed default so tests are deterministic.
DEFAULT = datetime(2024, 1, 1, 0, 0, 0)


# ---------------------------------------------------------------------------
# ISO 8601
# ---------------------------------------------------------------------------


class TestISO8601:
    def test_date_only(self):
        assert parse("2024-01-15", default=DEFAULT) == datetime(2024, 1, 15)

    def test_date_and_time(self):
        assert parse("2024-01-15T10:30:00", default=DEFAULT) == datetime(2024, 1, 15, 10, 30, 0)

    def test_date_and_time_space_separator(self):
        assert parse("2024-01-15 10:30:00", default=DEFAULT) == datetime(2024, 1, 15, 10, 30, 0)

    def test_date_time_utc_z(self):
        result = parse("2024-01-15T10:30:00Z", default=DEFAULT)
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=tzutc())

    def test_date_time_positive_offset(self):
        result = parse("2024-01-15T10:30:00+05:30", default=DEFAULT)
        assert result.hour == 10
        assert result.minute == 30
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_date_time_negative_offset(self):
        result = parse("2024-01-15T10:30:00-04:00", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=-4)

    def test_date_time_fractional_seconds(self):
        result = parse("2024-01-15T10:30:00.123456", default=DEFAULT)
        assert result.microsecond == 123456

    def test_date_time_fractional_short(self):
        result = parse("2024-01-15T10:30:00.5", default=DEFAULT)
        assert result.microsecond == 500000

    def test_date_time_no_seconds(self):
        assert parse("2024-01-15T10:30", default=DEFAULT) == datetime(2024, 1, 15, 10, 30)

    def test_date_time_offset_no_colon(self):
        result = parse("2024-01-15T10:30:00+0530", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_compact_offset(self):
        result = parse("2024-06-15T08:00:00-05:00", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=-5)


# ---------------------------------------------------------------------------
# Common date formats
# ---------------------------------------------------------------------------


class TestCommonFormats:
    def test_month_day_year(self):
        # "Jan 15 2024"
        assert parse("Jan 15 2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_full_month_day_year(self):
        assert parse("January 15, 2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_day_month_year(self):
        assert parse("15 Jan 2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_day_full_month_year(self):
        assert parse("15 January 2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_month_day_comma_year(self):
        assert parse("January 15, 2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_us_slash_format(self):
        # MM/DD/YYYY
        assert parse("01/15/2024", default=DEFAULT) == datetime(2024, 1, 15)

    def test_us_slash_short_year(self):
        assert parse("01/15/24", default=DEFAULT) == datetime(2024, 1, 15)

    def test_european_slash_dayfirst(self):
        assert parse("15/01/2024", dayfirst=True, default=DEFAULT) == datetime(2024, 1, 15)

    def test_dot_separated(self):
        # DD.MM.YYYY — common in Europe
        assert parse("15.01.2024", dayfirst=True, default=DEFAULT) == datetime(2024, 1, 15)

    def test_month_year_only(self):
        result = parse("Jan 2024", default=DEFAULT)
        assert result.month == 1
        assert result.year == 2024

    def test_year_month_only(self):
        result = parse("2024 Jan", default=DEFAULT)
        assert result.month == 1
        assert result.year == 2024

    def test_month_name_with_ordinal(self):
        result = parse("January 15th, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_day_of_month_name(self):
        result = parse("15th of January, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_abbreviated_month_period(self):
        # "Jan." with trailing period
        result = parse("Jan. 15, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_sept_abbreviation(self):
        result = parse("Sept 15, 2024", default=DEFAULT)
        assert result.month == 9
        assert result.day == 15

    def test_weekday_prefix(self):
        # Weekday names should be silently ignored
        result = parse("Monday, January 15, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_weekday_abbr_prefix(self):
        result = parse("Mon, Jan 15 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------


class TestTime:
    def test_time_24h(self):
        result = parse("10:30:00", default=DEFAULT)
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0

    def test_time_am(self):
        result = parse("10:30 AM", default=DEFAULT)
        assert result.hour == 10
        assert result.minute == 30

    def test_time_pm(self):
        result = parse("10:30 PM", default=DEFAULT)
        assert result.hour == 22
        assert result.minute == 30

    def test_12_am_is_midnight(self):
        result = parse("12:00 AM", default=DEFAULT)
        assert result.hour == 0

    def test_12_pm_is_noon(self):
        result = parse("12:00 PM", default=DEFAULT)
        assert result.hour == 12

    def test_time_microseconds(self):
        result = parse("10:30:00.123456", default=DEFAULT)
        assert result.microsecond == 123456

    def test_time_milliseconds(self):
        result = parse("10:30:00.123", default=DEFAULT)
        assert result.microsecond == 123000

    def test_date_and_time_with_am(self):
        result = parse("Jan 15, 2024 10:30 AM", default=DEFAULT)
        assert result == datetime(2024, 1, 15, 10, 30)

    def test_date_and_time_with_pm(self):
        result = parse("Jan 15, 2024 3:30 PM", default=DEFAULT)
        assert result == datetime(2024, 1, 15, 15, 30)

    def test_hours_minutes_only(self):
        result = parse("10:30", default=DEFAULT)
        assert result.hour == 10
        assert result.minute == 30


# ---------------------------------------------------------------------------
# Timezone handling
# ---------------------------------------------------------------------------


class TestTimezones:
    def test_utc(self):
        result = parse("2024-01-15 10:30:00 UTC", default=DEFAULT)
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(0)

    def test_est(self):
        result = parse("Jan 15 2024 10:30:00 EST", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=-5)

    def test_pst(self):
        result = parse("Jan 15 2024 10:30:00 PST", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=-8)

    def test_z_suffix(self):
        result = parse("2024-01-15T10:30:00Z", default=DEFAULT)
        assert result.utcoffset() == timedelta(0)

    def test_positive_numeric_offset(self):
        result = parse("2024-01-15 10:30:00 +05:30", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_negative_numeric_offset(self):
        result = parse("2024-01-15 10:30:00 -08:00", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=-8)

    def test_gmt(self):
        result = parse("2024-01-15 10:30:00 GMT", default=DEFAULT)
        assert result.utcoffset() == timedelta(0)

    def test_jst(self):
        result = parse("2024-01-15 10:30:00 JST", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=9)


# ---------------------------------------------------------------------------
# Ambiguous date handling (dayfirst / yearfirst)
# ---------------------------------------------------------------------------


class TestAmbiguousDates:
    def test_default_mm_dd_yy(self):
        # Default: MM/DD/YYYY
        result = parse("03/05/2024", default=DEFAULT)
        assert result.month == 3
        assert result.day == 5

    def test_dayfirst_dd_mm_yy(self):
        result = parse("03/05/2024", dayfirst=True, default=DEFAULT)
        assert result.day == 3
        assert result.month == 5

    def test_yearfirst_yy_mm_dd(self):
        result = parse("24/01/15", yearfirst=True, default=DEFAULT)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_unambiguous_large_day(self):
        # 15 cannot be a month, so it must be the day
        result = parse("01/15/2024", default=DEFAULT)
        assert result.month == 1
        assert result.day == 15

    def test_dayfirst_with_large_day(self):
        result = parse("31/12/2024", dayfirst=True, default=DEFAULT)
        assert result.day == 31
        assert result.month == 12

    def test_two_digit_year(self):
        result = parse("01/15/68", default=DEFAULT)
        assert result.year == 2068

    def test_two_digit_year_old(self):
        result = parse("01/15/69", default=DEFAULT)
        assert result.year == 1969


# ---------------------------------------------------------------------------
# Partial dates (default filling)
# ---------------------------------------------------------------------------


class TestPartialDates:
    def test_month_name_only(self):
        result = parse("January", default=DEFAULT)
        assert result.month == 1
        assert result.year == DEFAULT.year
        assert result.day == DEFAULT.day

    def test_year_only(self):
        result = parse("2024", default=DEFAULT)
        assert result.year == 2024

    def test_day_and_month(self):
        result = parse("Jan 15", default=DEFAULT)
        assert result.month == 1
        assert result.day == 15
        assert result.year == DEFAULT.year

    def test_custom_default(self):
        custom = datetime(2023, 6, 15, 14, 30, 0)
        result = parse("10:00", default=custom)
        assert result.year == 2023
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 0


# ---------------------------------------------------------------------------
# Fuzzy mode
# ---------------------------------------------------------------------------


class TestFuzzy:
    def test_basic_fuzzy(self):
        result = parse(
            "The meeting is on January 15, 2024 at 3:00 PM",
            fuzzy=True,
            default=DEFAULT,
        )
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 15
        assert result.minute == 0

    def test_fuzzy_with_prefix_text(self):
        result = parse(
            "Created on 2024-01-15",
            fuzzy=True,
            default=DEFAULT,
        )
        assert result == datetime(2024, 1, 15)

    def test_fuzzy_with_tokens(self):
        result, tokens = parse(
            "The date is Jan 15, 2024 ok",
            fuzzy_with_tokens=True,
            default=DEFAULT,
        )
        assert result == datetime(2024, 1, 15)
        assert isinstance(tokens, tuple)
        # "The", "date", "is", "ok" should be in skipped tokens
        assert "The" in tokens or "ok" in tokens

    def test_fuzzy_extracts_time(self):
        result = parse(
            "Reminder at 3:30 PM tomorrow",
            fuzzy=True,
            default=DEFAULT,
        )
        assert result.hour == 15
        assert result.minute == 30

    def test_non_fuzzy_rejects_extra_text(self):
        with pytest.raises(ParserError):
            parse("The date is Jan 15, 2024 ok", default=DEFAULT)

    def test_fuzzy_with_tokens_returns_tuple(self):
        result = parse(
            "Hello 2024-01-15 world",
            fuzzy_with_tokens=True,
            default=DEFAULT,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        dt, tokens = result
        assert dt.year == 2024


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_string(self):
        with pytest.raises(ParserError):
            parse("")

    def test_whitespace_only(self):
        with pytest.raises(ParserError):
            parse("   ")

    def test_no_date_content(self):
        with pytest.raises(ParserError):
            parse("hello world")

    def test_non_string_input(self):
        with pytest.raises(TypeError):
            parse(12345)  # type: ignore[arg-type]

    def test_invalid_date_values(self):
        with pytest.raises(ParserError):
            parse("2024-13-45", default=DEFAULT)

    def test_parser_error_is_value_error(self):
        # ParserError should be a subclass of ValueError for compatibility
        assert issubclass(ParserError, ValueError)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_extra_whitespace(self):
        result = parse("  Jan  15  2024  ", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_midnight(self):
        result = parse("2024-01-15T00:00:00", default=DEFAULT)
        assert result.hour == 0

    def test_end_of_day(self):
        result = parse("2024-01-15T23:59:59", default=DEFAULT)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59

    def test_leap_year_date(self):
        result = parse("Feb 29, 2024", default=DEFAULT)
        assert result.month == 2
        assert result.day == 29

    def test_non_leap_year_feb_29_raises(self):
        with pytest.raises(ParserError):
            parse("Feb 29, 2023", default=DEFAULT)

    def test_year_2000(self):
        result = parse("Jan 1, 2000", default=DEFAULT)
        assert result.year == 2000

    def test_two_digit_year_00(self):
        result = parse("01/15/00", default=DEFAULT)
        assert result.year == 2000

    def test_date_with_weekday(self):
        result = parse("Friday, January 15, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_mixed_case(self):
        result = parse("jAnUaRy 15, 2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_day_month_year_no_separator(self):
        # "15 January 2024"
        result = parse("15 January 2024", default=DEFAULT)
        assert result.day == 15
        assert result.month == 1
        assert result.year == 2024


# ---------------------------------------------------------------------------
# Bug #115: Hyphenated month-name dates
# ---------------------------------------------------------------------------


class TestHyphenatedMonthDates:
    def test_day_month_year_hyphen(self):
        # 15-Jan-2024
        result = parse("15-Jan-2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_month_day_year_hyphen(self):
        # Jan-15-2024
        result = parse("Jan-15-2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_year_month_day_hyphen(self):
        # 2024-Jan-15
        result = parse("2024-Jan-15", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_full_month_hyphenated(self):
        # 15-January-2024
        result = parse("15-January-2024", default=DEFAULT)
        assert result == datetime(2024, 1, 15)

    def test_hyphen_month_no_year(self):
        result = parse("15-Jan", default=DEFAULT)
        assert result.month == 1
        assert result.day == 15


# ---------------------------------------------------------------------------
# Bug #116: Bare number + AM/PM
# ---------------------------------------------------------------------------


class TestBareNumberAmPm:
    def test_3pm(self):
        result = parse("3pm", default=DEFAULT)
        assert result.hour == 15

    def test_3_pm_with_space(self):
        result = parse("3 pm", default=DEFAULT)
        assert result.hour == 15

    def test_11am(self):
        result = parse("11am", default=DEFAULT)
        assert result.hour == 11

    def test_12pm_is_noon(self):
        result = parse("12pm", default=DEFAULT)
        assert result.hour == 12

    def test_12am_is_midnight(self):
        result = parse("12am", default=DEFAULT)
        assert result.hour == 0

    def test_bare_number_ampm_with_date(self):
        result = parse("Jan 15, 2024 3pm", default=DEFAULT)
        assert result == datetime(2024, 1, 15, 15, 0)


# ---------------------------------------------------------------------------
# Bug #117: Greedy timezone offset consumption
# ---------------------------------------------------------------------------


class TestTimezoneOffsetValidation:
    def test_plus_sign_does_not_swallow_year(self):
        # "Jan 15 + 2024" — the +2024 should NOT be treated as a tz offset
        result = parse("Jan 15 + 2024", fuzzy=True, default=DEFAULT)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_valid_offset_still_works(self):
        result = parse("2024-01-15 10:30 +05:30", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_valid_offset_no_colon(self):
        result = parse("2024-01-15 10:30 +0530", default=DEFAULT)
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_invalid_minutes_rejected(self):
        # +05:99 has invalid minutes — should not be consumed as tz
        result = parse("Jan 15 2024 10:30 +05:99", fuzzy=True, default=DEFAULT)
        assert result.tzinfo is None or result.utcoffset() != timedelta(hours=5, minutes=99)


# ---------------------------------------------------------------------------
# Top-level imports
# ---------------------------------------------------------------------------


class TestTopLevelImports:
    def test_import_parse_from_dateflow(self):
        from dateflow import parse as p
        assert callable(p)

    def test_import_parser_error_from_dateflow(self):
        from dateflow import ParserError as PE
        assert issubclass(PE, ValueError)
