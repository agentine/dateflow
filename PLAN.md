# dateflow

**A zero-dependency, modern Python replacement for python-dateutil.**

---

## Target

The `python-dateutil` package on PyPI — a date/time utility library downloaded **900M+ times per month**, maintained by a **single active developer** (Paul Ganssle), with **no release in 2 years**, **332 open issues**, **97 unreviewed PRs**, and a legacy dependency on `six` (Python 2 compatibility shim, 6 years after Python 2 EOL).

### Package Replaced

| Package | Monthly Downloads | Function |
|---------|------------------|----------|
| `python-dateutil` | ~900M | Date parsing, relative deltas, recurrence rules, timezone utilities |

### Why This Target

1. **Bus factor = 1.** Paul Ganssle is the sole active maintainer. No co-maintainers review or merge PRs. No succession plan exists.
2. **Stale releases.** Last PyPI release was March 2024 (v2.9.0.post0) — 2 years ago. Commits happen intermittently but never ship.
3. **Massive unaddressed backlog.** 332 open issues (77% stale since Jan 2024), 97 open PRs (62% stale). Community contributions go unreviewed for years.
4. **Legacy dependency on `six`.** Still depends on `six` for Python 2 compatibility, despite Python 2 being EOL since January 2020. This is the #1 community complaint and the reason projects actively seek alternatives.
5. **No funding.** No GitHub Sponsors, no OpenCollective, no corporate backing. Purely volunteer-maintained.
6. **Typosquatting target.** Already attacked twice — `python-dateutils` (cryptominer) and `python3-dateutil` (SSH/GPG key stealer). High profile makes it a persistent supply chain risk.
7. **No drop-in replacement exists.** Pendulum and Arrow have different APIs and their own dependency chains. stdlib covers some use cases (fromisoformat, zoneinfo) but not fuzzy parsing, relativedelta, or rrule.
8. **Used by everything.** Transitive dependency of pandas, botocore (AWS), matplotlib, Airflow, Django REST framework, and thousands more.

---

## Scope

### In Scope

- **Date/time parsing** — fuzzy, natural-language-aware date string parsing (`dateutil.parser.parse` replacement)
- **ISO 8601 parsing** — full ISO 8601 / RFC 3339 support (`dateutil.parser.isoparse` replacement)
- **Relative deltas** — month/year-aware date arithmetic (`dateutil.relativedelta` replacement)
- **Recurrence rules** — RFC 5545 (iCalendar) recurrence rule engine (`dateutil.rrule` replacement)
- **Easter computation** — Western, Orthodox, Julian Easter date calculation (`dateutil.easter` replacement)
- **Timezone utilities** — built on stdlib `zoneinfo` (Python 3.9+), no pytz dependency
- **dateutil-compatible API** — drop-in migration with minimal code changes
- **Zero dependencies** — pure Python, no runtime deps
- **Python 3.9+** — modern Python only, leverages zoneinfo, fromisoformat improvements
- **Type-annotated** — full type hints, py.typed marker
- **Comprehensive test suite** — >95% coverage, including dateutil compatibility tests

### Out of Scope

- Python 2 support (the whole point is to drop `six`)
- Python < 3.9 support (need `zoneinfo` in stdlib)
- Full calendar/scheduling system (this is a utility library, not a calendar app)
- Locale-specific date formatting (use `babel` or `datetime.strftime`)

---

## Architecture

### Single Package, Zero Dependencies

```
dateflow/
├── src/
│   └── dateflow/
│       ├── __init__.py       # Public API re-exports
│       ├── parser.py         # Date/time string parsing (fuzzy + ISO 8601)
│       ├── relativedelta.py  # Month/year-aware date arithmetic
│       ├── rrule.py          # RFC 5545 recurrence rules
│       ├── easter.py         # Easter date computation
│       ├── tz.py             # Timezone utilities (wraps zoneinfo)
│       └── _utils.py         # Internal helpers
├── tests/
│   ├── test_parser.py
│   ├── test_relativedelta.py
│   ├── test_rrule.py
│   ├── test_easter.py
│   ├── test_tz.py
│   └── test_compat.py       # python-dateutil API compatibility tests
├── pyproject.toml
├── PLAN.md
├── README.md
└── LICENSE                   # MIT
```

### Package Configuration

```toml
[project]
name = "dateflow"
requires-python = ">=3.9"
dependencies = []  # Zero dependencies
```

### API Design

#### Parser (dateutil.parser replacement)

```python
from dateflow import parse, isoparse

# Fuzzy date parsing — the killer feature
parse("March 11, 2026")              # datetime(2026, 3, 11, 0, 0)
parse("11/03/2026")                  # datetime(2026, 11, 3) or (2026, 3, 11) with dayfirst=True
parse("next Thursday")               # context-aware relative parsing
parse("2026-03-11T14:30:00+05:00")   # full ISO 8601 with timezone
parse("March 2026", default=datetime(2026, 1, 1))  # fill missing fields from default

# Fuzzy parsing with surrounding text
parse("The meeting is on March 11, 2026 at 3pm", fuzzy=True)
# datetime(2026, 3, 11, 15, 0)

parse("The meeting is on March 11, 2026 at 3pm", fuzzy_with_tokens=True)
# (datetime(2026, 3, 11, 15, 0), ("The meeting is on ", " at ", ""))

# ISO 8601 strict parsing
isoparse("2026-03-11T14:30:00Z")     # datetime with tzinfo=UTC
isoparse("2026-W11")                 # ISO week date
isoparse("2026-070")                 # ISO ordinal date
```

#### RelativeDelta (dateutil.relativedelta replacement)

```python
from dateflow import relativedelta
from datetime import datetime

dt = datetime(2026, 1, 31)

# Month arithmetic that handles month-end correctly
dt + relativedelta(months=1)          # datetime(2026, 2, 28) — clips to month end
dt + relativedelta(months=1, day=31)  # datetime(2026, 2, 28) — absolute day, clipped

# Complex relative deltas
dt + relativedelta(years=1, months=2, days=3, hours=4)
# datetime(2027, 4, 3, 4, 0)

# Weekday targeting
from dateflow import MO, TU, WE, TH, FR, SA, SU
dt + relativedelta(weekday=FR)        # Next Friday
dt + relativedelta(weekday=FR(2))     # Second Friday from now

# Delta between dates
relativedelta(datetime(2026, 3, 11), datetime(2025, 1, 1))
# relativedelta(years=1, months=2, days=10)
```

#### Recurrence Rules (dateutil.rrule replacement)

```python
from dateflow import rrule, rruleset, rrulestr
from dateflow import YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY

# Daily recurrence
list(rrule(DAILY, count=5, dtstart=datetime(2026, 3, 11)))
# [datetime(2026, 3, 11), ..., datetime(2026, 3, 15)]

# Monthly on the last Friday
list(rrule(MONTHLY, count=3, byweekday=FR(-1), dtstart=datetime(2026, 1, 1)))
# Last Friday of Jan, Feb, Mar 2026

# Parse iCalendar RRULE strings
rule = rrulestr("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10")

# Rule sets with exclusions
rs = rruleset()
rs.rrule(rrule(DAILY, count=30, dtstart=datetime(2026, 3, 1)))
rs.exdate(datetime(2026, 3, 15))  # Exclude March 15
rs.exrule(rrule(WEEKLY, byweekday=SA, dtstart=datetime(2026, 3, 1)))  # Exclude Saturdays
```

#### Easter (dateutil.easter replacement)

```python
from dateflow import easter

easter(2026)                          # date(2026, 4, 5) — Western/Gregorian
easter(2026, method=EASTER_ORTHODOX)  # Orthodox Easter
easter(2026, method=EASTER_JULIAN)    # Julian calendar Easter
```

#### Timezone Utilities (dateutil.tz replacement)

```python
from dateflow import tz

# Built on stdlib zoneinfo — no pytz needed
eastern = tz.gettz("America/New_York")
utc = tz.UTC

# Fixed offset
plus5 = tz.tzoffset("EST", -5 * 3600)

# Local timezone
local = tz.tzlocal()

# Resolve ambiguous/nonexistent times (DST transitions)
tz.resolve_imaginary(dt)              # Adjust non-existent times forward
tz.enfold(dt, fold=1)                 # Set fold for ambiguous times
```

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Zero dependencies | Eliminates transitive supply chain risk. python-dateutil's `six` dep is a community pain point. |
| Python 3.9+ only | Drops all Python 2 baggage. Leverages `zoneinfo` (stdlib), improved `fromisoformat`, `Annotated`, etc. |
| dateutil-compatible API | Migration must be trivial: `s/dateutil/dateflow/g` should work for 90%+ of use cases. |
| `zoneinfo`-based timezones | stdlib timezone support replaces both pytz and dateutil.tz internals. One less supply chain link. |
| Pure Python | No C extensions, no Rust, no build complexity. Maximizes portability and auditability. |
| `src/` layout | Modern Python packaging best practice. Prevents accidental imports from the source tree. |
| `pyproject.toml` only | No setup.py, no setup.cfg. Modern standards (PEP 517/518/621). |
| pytest for testing | Industry standard, great fixture support for date/time testing. |
| MIT license | Maximum adoption, same as python-dateutil. |

---

## Deliverables

1. **`dateflow` PyPI package** — fully functional, published, zero-dependency
2. **README.md** — usage docs, migration guide from python-dateutil, API reference
3. **Test suite** — >95% coverage, including python-dateutil compatibility tests
4. **Migration guide** — step-by-step guide for replacing python-dateutil with dateflow

---

## Implementation Phases

### Phase 1: RelativeDelta & Easter
- `relativedelta.py` — month/year-aware date arithmetic with weekday targeting
- `easter.py` — Western, Orthodox, Julian Easter computation
- Tests for both modules
- These are self-contained with no dependency on other dateflow modules

### Phase 2: Timezone Utilities
- `tz.py` — zoneinfo-based timezone resolution, fixed offsets, local timezone detection
- Compatibility layer mapping dateutil.tz API to zoneinfo
- Tests for timezone handling including DST edge cases

### Phase 3: Date Parser
- `parser.py` — fuzzy date string parsing, ISO 8601 parsing
- This is the most complex module and the primary reason people use dateutil
- Token-based parser that handles ambiguous, partial, and natural-language dates
- Tests covering dateutil's extensive parser test suite

### Phase 4: Recurrence Rules
- `rrule.py` — RFC 5545 recurrence rule engine
- rrule, rruleset, rrulestr
- Full frequency/interval/count/until/byXXX support
- Tests covering dateutil's rrule test suite

### Phase 5: Polish & Ship
- `__init__.py` — unified public API, convenience re-exports
- python-dateutil compatibility test suite (run dateutil's own tests against dateflow)
- README and migration guide
- PyPI publish setup (pyproject.toml, CI pipeline, provenance)
