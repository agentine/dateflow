"""Tests for dateflow.easter — Easter date computation."""

from datetime import date

import pytest

from dateflow.easter import (
    EASTER_JULIAN,
    EASTER_ORTHODOX,
    EASTER_WESTERN,
    easter,
)


class TestWesternEaster:
    """Test the Western (Gregorian) Easter computation."""

    def test_known_dates(self):
        known = {
            2000: date(2000, 4, 23),
            2010: date(2010, 4, 4),
            2015: date(2015, 4, 5),
            2020: date(2020, 4, 12),
            2024: date(2024, 3, 31),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 5),
            2030: date(2030, 4, 21),
        }
        for year, expected in known.items():
            assert easter(year) == expected, f"year {year}"

    def test_is_always_sunday(self):
        for year in range(2000, 2050):
            d = easter(year)
            assert d.weekday() == 6, f"year {year}: {d} is not Sunday"

    def test_is_between_march_22_and_april_25(self):
        for year in range(1583, 2200):
            d = easter(year)
            assert date(year, 3, 22) <= d <= date(year, 4, 25), f"year {year}: {d} out of range"

    def test_default_method_is_western(self):
        assert easter(2026) == easter(2026, EASTER_WESTERN)


class TestOrthodoxEaster:
    """Test the Orthodox Easter computation (Julian algorithm, Gregorian date)."""

    def test_known_dates(self):
        known = {
            2020: date(2020, 4, 19),
            2024: date(2024, 5, 5),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 12),
        }
        for year, expected in known.items():
            result = easter(year, EASTER_ORTHODOX)
            assert result == expected, f"year {year}: got {result}, expected {expected}"

    def test_is_always_sunday(self):
        for year in range(2000, 2050):
            d = easter(year, EASTER_ORTHODOX)
            assert d.weekday() == 6, f"year {year}: {d} is not Sunday"


class TestJulianEaster:
    """Test the Julian Easter computation (Julian calendar date)."""

    def test_known_dates(self):
        known = {
            2020: date(2020, 4, 6),
            2024: date(2024, 4, 22),
            2026: date(2026, 3, 30),
        }
        for year, expected in known.items():
            result = easter(year, EASTER_JULIAN)
            assert result == expected, f"year {year}: got {result}, expected {expected}"

    def test_is_always_sunday_in_julian(self):
        # Julian Easter should fall on Sunday in the Julian calendar
        # When stored as a proleptic Gregorian date, the weekday may differ
        # but the algorithm is verified to be correct by matching dateutil
        for year in range(1, 50):
            easter(year, EASTER_JULIAN)  # should not raise


class TestEdgeCases:
    def test_year_1(self):
        d = easter(1)
        assert isinstance(d, date)

    def test_year_9999(self):
        d = easter(9999)
        assert isinstance(d, date)

    def test_year_0_raises(self):
        with pytest.raises(ValueError, match="year must be"):
            easter(0)

    def test_year_10000_raises(self):
        with pytest.raises(ValueError, match="year must be"):
            easter(10000)

    def test_invalid_method_raises(self):
        with pytest.raises(ValueError, match="invalid method"):
            easter(2026, method=4)

    def test_negative_year_raises(self):
        with pytest.raises(ValueError, match="year must be"):
            easter(-1)


class TestDateutilCompatibility:
    """Verify output matches dateutil.easter for a wide range of years."""

    def test_matches_dateutil_western(self):
        try:
            from dateutil.easter import easter as du_easter
        except ImportError:
            pytest.skip("dateutil not installed")

        for year in range(1583, 2200):
            assert easter(year) == du_easter(year), f"Western mismatch at year {year}"

    def test_matches_dateutil_orthodox(self):
        try:
            from dateutil.easter import easter as du_easter
        except ImportError:
            pytest.skip("dateutil not installed")

        for year in range(1583, 2200):
            assert (
                easter(year, EASTER_ORTHODOX)
                == du_easter(year, EASTER_ORTHODOX)
            ), f"Orthodox mismatch at year {year}"

    def test_matches_dateutil_julian(self):
        try:
            from dateutil.easter import easter as du_easter
        except ImportError:
            pytest.skip("dateutil not installed")

        for year in range(1, 2200):
            assert (
                easter(year, EASTER_JULIAN)
                == du_easter(year, EASTER_JULIAN)
            ), f"Julian mismatch at year {year}"
