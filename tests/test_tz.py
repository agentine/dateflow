"""Tests for dateflow.tz — timezone utilities."""

from datetime import datetime, timedelta, timezone

import pytest

from dateflow.tz import (
    UTC,
    gettz,
    tzoffset,
    tzutc,
    tzlocal,
    enfold,
    resolve_imaginary,
    datetime_exists,
    datetime_ambiguous,
)


# ---------------------------------------------------------------------------
# gettz
# ---------------------------------------------------------------------------

class TestGettz:
    def test_valid_iana_name(self):
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=tz)
        # January = EST = UTC-5
        assert dt.utcoffset() == timedelta(hours=-5)

    def test_utc(self):
        tz = gettz("UTC")
        assert tz is not None
        assert tz is UTC

    def test_gmt(self):
        tz = gettz("GMT")
        assert tz is not None
        assert tz is UTC

    def test_none_returns_local(self):
        tz = gettz(None)
        assert tz is not None
        assert isinstance(tz, tzlocal)

    def test_invalid_name_returns_none(self):
        result = gettz("Invalid/Timezone")
        assert result is None

    def test_dst_transition(self):
        tz = gettz("America/New_York")
        assert tz is not None
        # Summer (EDT) = UTC-4
        summer = datetime(2024, 7, 15, 12, 0, tzinfo=tz)
        assert summer.utcoffset() == timedelta(hours=-4)
        # Winter (EST) = UTC-5
        winter = datetime(2024, 1, 15, 12, 0, tzinfo=tz)
        assert winter.utcoffset() == timedelta(hours=-5)


# ---------------------------------------------------------------------------
# tzoffset
# ---------------------------------------------------------------------------

class TestTzoffset:
    def test_seconds_int(self):
        tz = tzoffset("EST", -18000)
        assert tz.utcoffset(None) == timedelta(hours=-5)
        assert tz.tzname(None) == "EST"

    def test_timedelta(self):
        tz = tzoffset("IST", timedelta(hours=5, minutes=30))
        assert tz.utcoffset(None) == timedelta(hours=5, minutes=30)

    def test_zero_offset(self):
        tz = tzoffset(None, 0)
        assert tz.utcoffset(None) == timedelta(0)

    def test_dst_always_zero(self):
        tz = tzoffset("FOO", 3600)
        assert tz.dst(None) == timedelta(0)

    def test_repr(self):
        tz = tzoffset("EST", -18000)
        assert repr(tz) == "tzoffset('EST', -18000)"

    def test_equality(self):
        a = tzoffset("A", 3600)
        b = tzoffset("B", 3600)
        assert a == b  # same offset, different names

    def test_hash(self):
        a = tzoffset("A", 3600)
        b = tzoffset("B", 3600)
        assert hash(a) == hash(b)

    def test_arithmetic(self):
        tz = tzoffset("CET", 3600)
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        utc_dt = dt.astimezone(timezone.utc)
        assert utc_dt.hour == 11


# ---------------------------------------------------------------------------
# UTC / tzutc
# ---------------------------------------------------------------------------

class TestUTC:
    def test_utc_offset(self):
        assert UTC.utcoffset(None) == timedelta(0)  # type: ignore[union-attr]

    def test_tzutc_singleton(self):
        a = tzutc()
        b = tzutc()
        assert a is b

    def test_tzutc_offset(self):
        u = tzutc()
        assert u.utcoffset(None) == timedelta(0)

    def test_tzutc_name(self):
        assert tzutc().tzname(None) == "UTC"

    def test_tzutc_dst(self):
        assert tzutc().dst(None) == timedelta(0)

    def test_tzutc_repr(self):
        assert repr(tzutc()) == "tzutc()"

    def test_tzutc_eq_tzoffset_zero(self):
        u = tzutc()
        z = tzoffset("Z", 0)
        assert u == z
        assert z == u

    def test_tzutc_hash_matches_timezone_utc(self):
        """Bug #104: hash(tzutc()) must equal hash(timezone.utc) since they are equal."""
        u = tzutc()
        assert u == timezone.utc
        assert hash(u) == hash(timezone.utc)

    def test_tzutc_hash_matches_tzoffset_zero(self):
        """Bug #104: hash(tzutc()) must equal hash(tzoffset(None, 0)) since they are equal."""
        u = tzutc()
        z = tzoffset(None, 0)
        assert u == z
        assert hash(u) == hash(z)

    def test_tzutc_usable_in_set_with_timezone_utc(self):
        """Bug #104: tzutc() and timezone.utc should deduplicate in a set."""
        s = {tzutc(), timezone.utc}
        # They are equal, so the set should contain only one element.
        assert len(s) == 1

    def test_tzutc_usable_as_dict_key_with_timezone_utc(self):
        """Bug #104: tzutc() and timezone.utc should map to the same dict key."""
        d = {tzutc(): "value"}
        assert d[timezone.utc] == "value"


# ---------------------------------------------------------------------------
# tzlocal
# ---------------------------------------------------------------------------

class TestTzlocal:
    def test_creates_without_error(self):
        tz = tzlocal()
        assert isinstance(tz, tzlocal)

    def test_is_valid_tzinfo(self):
        from datetime import tzinfo as base_tzinfo
        tz = tzlocal()
        assert isinstance(tz, base_tzinfo)

    def test_utcoffset_not_none(self):
        tz = tzlocal()
        offset = tz.utcoffset(None)
        assert offset is not None
        # Offset should be in a reasonable range (-14h to +14h)
        assert timedelta(hours=-14) <= offset <= timedelta(hours=14)

    def test_tzname_not_empty(self):
        tz = tzlocal()
        name = tz.tzname(None)
        assert name is not None
        assert len(name) > 0

    def test_repr(self):
        assert repr(tzlocal()) == "tzlocal()"


# ---------------------------------------------------------------------------
# enfold
# ---------------------------------------------------------------------------

class TestEnfold:
    def test_sets_fold(self):
        dt = datetime(2024, 11, 3, 1, 30)
        folded = enfold(dt, fold=1)
        assert folded.fold == 1

    def test_fold_zero(self):
        dt = datetime(2024, 11, 3, 1, 30)
        dt_fold1 = dt.replace(fold=1)
        unfolded = enfold(dt_fold1, fold=0)
        assert unfolded.fold == 0


# ---------------------------------------------------------------------------
# datetime_exists / datetime_ambiguous
# ---------------------------------------------------------------------------

class TestDatetimeExists:
    def test_normal_time_exists(self):
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        assert datetime_exists(dt) is True

    def test_spring_forward_gap(self):
        """2024-03-10 02:30 doesn't exist in America/New_York (spring forward)."""
        tz = gettz("America/New_York")
        assert tz is not None
        # 2:30 AM doesn't exist — clocks jump from 2:00 to 3:00
        dt = datetime(2024, 3, 10, 2, 30, tzinfo=tz)
        assert datetime_exists(dt) is False

    def test_naive_always_exists(self):
        dt = datetime(2024, 3, 10, 2, 30)
        assert datetime_exists(dt) is True

    def test_naive_with_tz_param_gap(self):
        """Bug #105: datetime_exists(naive_dt, tz=tz) should attach tz and check."""
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 3, 10, 2, 30)
        assert dt.tzinfo is None
        assert datetime_exists(dt, tz=tz) is False

    def test_naive_with_tz_param_normal(self):
        """Bug #105: datetime_exists(naive_dt, tz=tz) should return True for normal times."""
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 6, 15, 12, 0)
        assert datetime_exists(dt, tz=tz) is True

    def test_aware_ignores_tz_param(self):
        """Bug #105: If dt already has tzinfo, the tz param should be ignored."""
        tz_ny = gettz("America/New_York")
        tz_utc = gettz("UTC")
        assert tz_ny is not None and tz_utc is not None
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz_utc)
        assert datetime_exists(dt, tz=tz_ny) is True


class TestDatetimeAmbiguous:
    def test_normal_time_not_ambiguous(self):
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        assert datetime_ambiguous(dt) is False

    def test_fall_back_overlap(self):
        """2024-11-03 01:30 is ambiguous in America/New_York (fall back)."""
        tz = gettz("America/New_York")
        assert tz is not None
        # 1:30 AM occurs twice — clocks fall back from 2:00 to 1:00
        dt = datetime(2024, 11, 3, 1, 30, tzinfo=tz)
        assert datetime_ambiguous(dt) is True

    def test_naive_never_ambiguous(self):
        dt = datetime(2024, 11, 3, 1, 30)
        assert datetime_ambiguous(dt) is False

    def test_naive_with_tz_param_overlap(self):
        """Bug #105: datetime_ambiguous(naive_dt, tz=tz) should attach tz and check."""
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 11, 3, 1, 30)
        assert dt.tzinfo is None
        assert datetime_ambiguous(dt, tz=tz) is True

    def test_naive_with_tz_param_normal(self):
        """Bug #105: datetime_ambiguous(naive_dt, tz=tz) returns False for normal times."""
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 6, 15, 12, 0)
        assert datetime_ambiguous(dt, tz=tz) is False

    def test_aware_ignores_tz_param(self):
        """Bug #105: If dt already has tzinfo, the tz param should be ignored."""
        tz_ny = gettz("America/New_York")
        tz_utc = gettz("UTC")
        assert tz_ny is not None and tz_utc is not None
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz_utc)
        assert datetime_ambiguous(dt, tz=tz_ny) is False


# ---------------------------------------------------------------------------
# resolve_imaginary
# ---------------------------------------------------------------------------

class TestResolveImaginary:
    def test_non_imaginary_unchanged(self):
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        assert resolve_imaginary(dt) == dt

    def test_spring_forward_resolves(self):
        """2:30 AM during spring-forward should resolve to 3:30 AM."""
        tz = gettz("America/New_York")
        assert tz is not None
        dt = datetime(2024, 3, 10, 2, 30, tzinfo=tz)
        resolved = resolve_imaginary(dt)
        # Should have moved forward by the gap (1 hour)
        assert resolved.hour == 3
        assert resolved.minute == 30

    def test_naive_unchanged(self):
        dt = datetime(2024, 3, 10, 2, 30)
        assert resolve_imaginary(dt) == dt


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------

class TestRoundtrip:
    def test_utc_to_local_and_back(self):
        ny = gettz("America/New_York")
        assert ny is not None

        utc_now = datetime(2024, 6, 15, 18, 0, tzinfo=UTC)
        ny_time = utc_now.astimezone(ny)
        back_to_utc = ny_time.astimezone(timezone.utc)

        # Should round-trip exactly.
        assert back_to_utc.hour == utc_now.hour
        assert back_to_utc.minute == utc_now.minute


# ---------------------------------------------------------------------------
# Top-level imports
# ---------------------------------------------------------------------------

class TestTopLevelImports:
    def test_imports_from_dateflow(self):
        from dateflow import (
            UTC,
            gettz,
            tzoffset,
            tzutc,
            tzlocal,
            enfold,
            resolve_imaginary,
            datetime_exists,
            datetime_ambiguous,
        )
        assert UTC is not None
        assert callable(gettz)
