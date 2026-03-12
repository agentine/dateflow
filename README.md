# dateflow

A zero-dependency, modern Python replacement for python-dateutil.

## Why dateflow?

`python-dateutil` is downloaded 900M+ times per month but has a single active maintainer, no release in over two years, and a legacy dependency on `six` — a Python 2 compatibility shim — six years after Python 2 reached end-of-life.

`dateflow` replaces it entirely:

- **Zero dependencies.** No `six`, no `pytz`, nothing. Pure Python using only the standard library.
- **Python 3.9+ only.** Drops all Python 2 baggage. Uses `zoneinfo` (stdlib), improved `fromisoformat`, and full type annotations.
- **Drop-in replacement.** `s/dateutil/dateflow/g` works for 90%+ of use cases.
- **Actively maintained.** Exists precisely because the ecosystem needs a maintained alternative.
- **MIT licensed.** Same as python-dateutil.

## Installation

```
pip install dateflow
```

Requires Python 3.9 or later. No other dependencies.

## Quick Start

```python
from datetime import datetime
from dateflow import parse, isoparse, relativedelta, easter
from dateflow import rrule, DAILY, MO, FR

# Parse a date string
parse("March 11, 2026")
# datetime(2026, 3, 11, 0, 0)

# Month-aware date arithmetic
datetime(2026, 1, 31) + relativedelta(months=1)
# datetime(2026, 2, 28)

# Recurrence rules — first 5 weekdays of March 2026
list(rrule(DAILY, count=5, byweekday=[MO, FR], dtstart=datetime(2026, 3, 1)))

# Easter
easter(2026)
# date(2026, 4, 5)
```

## Usage

### Parser

The parser handles fuzzy natural-language dates, ambiguous formats, and strict ISO 8601.

```python
from dateflow import parse, isoparse
from dateflow.parser import ParserError
from datetime import datetime
```

**`parse()`** — fuzzy date string parsing:

```python
parse("March 11, 2026")
# datetime(2026, 3, 11, 0, 0)

parse("11/03/2026")
# datetime(2026, 11, 3, 0, 0)

parse("11/03/2026", dayfirst=True)
# datetime(2026, 3, 11, 0, 0)

parse("2026-03-11T14:30:00+05:00")
# datetime(2026, 3, 11, 14, 30, tzinfo=tzoffset(None, 18000))

# Fill missing fields from a default datetime
parse("March 2026", default=datetime(2026, 1, 1))
# datetime(2026, 3, 1, 0, 0)

# Ignore surrounding text with fuzzy=True
parse("The meeting is on March 11, 2026 at 3pm", fuzzy=True)
# datetime(2026, 3, 11, 15, 0)

# Get back the non-date tokens with fuzzy_with_tokens=True
parse("The meeting is on March 11, 2026 at 3pm", fuzzy_with_tokens=True)
# (datetime(2026, 3, 11, 15, 0), ("The meeting is on ", " at ", ""))
```

**`isoparse()`** — strict ISO 8601 / RFC 3339 parsing:

```python
isoparse("2026-03-11")
# date(2026, 3, 11)

isoparse("2026-03-11T14:30:00Z")
# datetime(2026, 3, 11, 14, 30, tzinfo=UTC)

isoparse("2026-03-11T14:30:00+05:00")
# datetime(2026, 3, 11, 14, 30, tzinfo=tzoffset(None, 18000))

isoparse("2026-W11")
# date(2026, 3, 9)  — ISO week date, Monday of week 11

isoparse("2026-070")
# date(2026, 3, 11)  — ISO ordinal date, day 70 of 2026
```

**`ParserError`** — raised when a string cannot be parsed:

```python
try:
    parse("not a date")
except ParserError as e:
    print(e)
```

---

### RelativeDelta

Month- and year-aware date arithmetic that handles edge cases like month-end clipping.

```python
from dateflow import relativedelta, MO, TU, WE, TH, FR, SA, SU
from datetime import datetime
```

**Month arithmetic:**

```python
dt = datetime(2026, 1, 31)

dt + relativedelta(months=1)
# datetime(2026, 2, 28) — clips to last day of February

dt + relativedelta(months=2)
# datetime(2026, 3, 31)

dt + relativedelta(years=1, months=2, days=3, hours=4)
# datetime(2027, 4, 3, 4, 0)

dt - relativedelta(months=3)
# datetime(2025, 10, 31)
```

**Absolute field overrides** (lowercase = absolute, uppercase = relative):

```python
# Set the day to 15 after adding a month
datetime(2026, 1, 31) + relativedelta(months=1, day=15)
# datetime(2026, 2, 15)
```

**Weekday targeting:**

```python
dt = datetime(2026, 3, 11)  # Wednesday

dt + relativedelta(weekday=FR)
# datetime(2026, 3, 13) — next Friday

dt + relativedelta(weekday=FR(2))
# datetime(2026, 3, 20) — second Friday from now

dt + relativedelta(weekday=MO(-1))
# datetime(2026, 3, 9) — previous Monday
```

**Delta between two dates:**

```python
relativedelta(datetime(2026, 3, 11), datetime(2025, 1, 1))
# relativedelta(years=+1, months=+2, days=+10)
```

---

### Recurrence Rules

RFC 5545 (iCalendar) recurrence rule engine with full `BYXXX` support.

```python
from dateflow import rrule, rruleset, rrulestr
from dateflow import YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY
from dateflow import MO, TU, WE, TH, FR, SA, SU
from datetime import datetime
```

**`rrule()`** — generate recurring dates:

```python
# Every day for 5 days
list(rrule(DAILY, count=5, dtstart=datetime(2026, 3, 11)))
# [datetime(2026, 3, 11), datetime(2026, 3, 12), ..., datetime(2026, 3, 15)]

# Every weekday (Mon–Fri) for 4 occurrences
list(rrule(WEEKLY, count=4, byweekday=[MO, TU, WE, TH, FR], dtstart=datetime(2026, 3, 11)))

# Monthly on the last Friday
list(rrule(MONTHLY, count=3, byweekday=FR(-1), dtstart=datetime(2026, 1, 1)))
# Last Friday of January, February, and March 2026

# Every year on March 11 until end of 2030
list(rrule(YEARLY, until=datetime(2030, 12, 31), dtstart=datetime(2026, 3, 11)))

# Every hour, 6 times
list(rrule(HOURLY, count=6, dtstart=datetime(2026, 3, 11, 9, 0)))
```

**`rruleset()`** — combine rules with inclusions and exclusions:

```python
rs = rruleset()

# Base rule: every day in March 2026
rs.rrule(rrule(DAILY, count=31, dtstart=datetime(2026, 3, 1)))

# Exclude a specific date
rs.exdate(datetime(2026, 3, 15))

# Exclude all Saturdays
rs.exrule(rrule(WEEKLY, byweekday=SA, dtstart=datetime(2026, 3, 1)))

# Include a date that falls outside the base rule
rs.rdate(datetime(2026, 4, 1))

list(rs)[:5]
# [datetime(2026, 3, 1), datetime(2026, 3, 2), datetime(2026, 3, 3), ...]
```

**`rrulestr()`** — parse iCalendar RRULE strings:

```python
# Single rule
rule = rrulestr("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10",
                dtstart=datetime(2026, 3, 11))

# Full VEVENT block
rule = rrulestr("""
DTSTART:20260311T090000
RRULE:FREQ=MONTHLY;BYDAY=-1FR;COUNT=6
EXDATE:20260424T090000
""")
```

---

### Easter

Compute Easter Sunday for any year using Western (Gregorian), Orthodox, or Julian methods.

```python
from dateflow import easter
from dateflow.easter import EASTER_ORTHODOX, EASTER_JULIAN
```

```python
easter(2026)
# date(2026, 4, 5) — Western/Gregorian (default)

easter(2026, method=EASTER_ORTHODOX)
# date(2026, 4, 19) — Orthodox Easter (Gregorian calendar output)

easter(2026, method=EASTER_JULIAN)
# date(2026, 4, 6) — Julian calendar Easter (Julian calendar output)
```

---

### Timezone Utilities

Built on stdlib `zoneinfo`. No `pytz` required.

```python
from dateflow import tz
from datetime import datetime
```

**`gettz()`** — resolve a timezone by name:

```python
eastern = tz.gettz("America/New_York")
tokyo = tz.gettz("Asia/Tokyo")

dt = datetime(2026, 3, 11, 12, 0, tzinfo=eastern)
```

**`UTC`** — the UTC timezone constant:

```python
dt = datetime(2026, 3, 11, 12, 0, tzinfo=tz.UTC)
```

**`tzoffset()`** — fixed UTC offset:

```python
plus5 = tz.tzoffset("IST", 5.5 * 3600)
minus5 = tz.tzoffset("EST", -5 * 3600)
```

**`tzlocal()`** — local system timezone:

```python
local = tz.tzlocal()
dt = datetime.now(tz=local)
```

**`tzutc()`** — UTC timezone instance (equivalent to `tz.UTC`):

```python
utc = tz.tzutc()
```

**DST transition helpers:**

```python
# enfold — set the fold flag on an ambiguous datetime (fall-back transition)
# fold=1 means the second occurrence (post-DST)
dt_ambiguous = tz.enfold(datetime(2026, 11, 1, 1, 30, tzinfo=eastern), fold=1)

# resolve_imaginary — shift a non-existent time forward past a spring-forward gap
dt_nonexistent = datetime(2026, 3, 8, 2, 30, tzinfo=eastern)  # doesn't exist
resolved = tz.resolve_imaginary(dt_nonexistent)
# datetime(2026, 3, 8, 3, 30, tzinfo=eastern)

# datetime_exists — check whether a local time actually exists
tz.datetime_exists(datetime(2026, 3, 8, 2, 30, tzinfo=eastern))
# False (skipped by DST spring-forward)

# datetime_ambiguous — check whether a local time occurs twice
tz.datetime_ambiguous(datetime(2026, 11, 1, 1, 30, tzinfo=eastern))
# True (occurs in both EDT and EST)
```

---

## Migration from python-dateutil

For most projects, migration is a one-liner:

```
s/dateutil/dateflow/g
```

This works for 90%+ of use cases. Here is the full mapping:

### Import changes

| python-dateutil | dateflow |
|---|---|
| `from dateutil.parser import parse` | `from dateflow import parse` |
| `from dateutil.parser import isoparse` | `from dateflow import isoparse` |
| `from dateutil.parser import ParserError` | `from dateflow.parser import ParserError` |
| `from dateutil.relativedelta import relativedelta` | `from dateflow import relativedelta` |
| `from dateutil.relativedelta import MO, FR, ...` | `from dateflow import MO, FR, ...` |
| `from dateutil.rrule import rrule, rruleset, rrulestr` | `from dateflow import rrule, rruleset, rrulestr` |
| `from dateutil.rrule import DAILY, WEEKLY, ...` | `from dateflow import DAILY, WEEKLY, ...` |
| `from dateutil.easter import easter` | `from dateflow import easter` |
| `from dateutil.easter import EASTER_ORTHODOX` | `from dateflow.easter import EASTER_ORTHODOX` |
| `from dateutil import tz` | `from dateflow import tz` |
| `from dateutil.tz import gettz` | `from dateflow.tz import gettz` |
| `from dateutil.tz import UTC, tzutc, tzlocal, tzoffset` | `from dateflow.tz import UTC, tzutc, tzlocal, tzoffset` |

### No pytz needed

`dateflow` uses Python's built-in `zoneinfo` module (available since Python 3.9). If you were using `pytz` only because `dateutil` led you there, you can remove it:

```python
# Before
import pytz
eastern = pytz.timezone("America/New_York")

# After
from dateflow import tz
eastern = tz.gettz("America/New_York")
```

### Drop `six` from your dependencies

If your project listed `six` because `python-dateutil` required it transitively, remove it. `dateflow` has zero dependencies and does not use `six`.

### Behavioral notes

- `parse()`, `isoparse()`, `relativedelta`, `rrule`, `rruleset`, `rrulestr`, and `easter()` are API-compatible with their `dateutil` counterparts.
- `tz.gettz()` returns a `zoneinfo.ZoneInfo` instance (or a `dateflow` shim for fixed offsets and local time) rather than a `dateutil.tz` object. These are fully compatible with `datetime` operations.
- `tzinfo` objects returned by `dateflow.tz` implement the standard `datetime.tzinfo` interface. Any code that calls `.utcoffset()`, `.dst()`, or `.tzname()` will work unchanged.

## License

MIT
