# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-12

Initial release of **dateflow** — a zero-dependency, modern Python replacement for python-dateutil. Supports Python 3.9+ with full type annotations and no runtime dependencies.

### Added

- **`relativedelta.py`** — month/year-aware date arithmetic with weekday targeting, nth-weekday support, and delta-between-dates computation. Drop-in replacement for `dateutil.relativedelta`.
- **`easter.py`** — Western (Gregorian), Orthodox, and Julian Easter date computation. Replaces `dateutil.easter`.
- **`tz.py`** — timezone utilities built on stdlib `zoneinfo`: `gettz`, `UTC`, `tzoffset`, `tzlocal`, `tzutc`, fixed-offset zones, `resolve_imaginary`, `enfold`. Replaces `dateutil.tz` without pytz dependency.
- **`parser.py`** — fuzzy and strict date/time string parsing: `parse` (natural-language-aware, fuzzy, token-based) and `isoparse` (full ISO 8601 / RFC 3339). Replaces `dateutil.parser`.
- **`rrule.py`** — RFC 5545 (iCalendar) recurrence rule engine: `rrule`, `rruleset`, `rrulestr`. All 7 frequencies (YEARLY–SECONDLY), all BYXXX modifiers, byeaster, bysetpos, nth-weekday occurrences, negative monthday indexing. Replaces `dateutil.rrule`.
- **`__init__.py`** — unified public API re-exporting all modules for `from dateflow import parse, relativedelta, rrule, ...` usage.
- **Zero dependencies** — pure Python, no runtime requirements beyond stdlib.
- **Python 3.9+** — leverages `zoneinfo` (stdlib), no `six` or Python 2 compatibility shims.
- **Full type annotations** — complete type hints throughout, `py.typed` marker included.
- **364 tests** — covering all 5 modules with extensive edge case coverage.

### Fixed

- `relativedelta`: incorrect microsecond negation and leapdays logic in `_compute_delta`
- `relativedelta`: truncation toward zero in day decomposition
- `relativedelta`: clip day after absolute year change to prevent leap year `ValueError`
- `relativedelta`: date/datetime mixed delta and `__init__` export issues
- `tz`: `tzlocal` crash on extreme datetimes like `datetime.min` (#106)
- `tz`: optional `tz` parameter added to `datetime_exists` and `datetime_ambiguous` (#105)
- `tz`: `tzutc`/`tzoffset` `__hash__` correctness to satisfy Python hash invariant (#104)
- `parser`: greedy timezone offset consumption swallowing year numbers — range validation on `_parse_numeric_offset`
- `parser`: bare number + AM/PM not recognized as time (e.g., `3pm`, `11am`)
- `parser`: hyphenated month-name date formats (`15-Jan-2024`, `Jan-15-2024`, `2024-Jan-15`)
- `parser`: default datetime timezone not propagated to result when parsed string has none
- `parser`: dotted `a.m.`/`p.m.` variants not recognized — fixed by merging split tokens
- `rrule`: infinite loop on impossible BYXXX date combinations (e.g., Feb 30) — `max_iter` now counts loop iterations, not yields
- `rrule`: BYSETPOS not applied in daily, hourly, minutely, secondly, and byeaster iterators
- `rrule`: timezone offset validation tightened (max ±14h) to prevent year numbers being parsed as offsets
- `rrule`: ordinal day 366 incorrectly accepted on non-leap years in `isoparse`
