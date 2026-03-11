"""Easter date computation — replaces dateutil.easter.

Algorithm ported from GM Arts / Claus Tondering / Ouding (1940),
as quoted in "Explanatory Supplement to the Astronomical Almanac".
"""

from __future__ import annotations

from datetime import date

# Method constants
EASTER_JULIAN = 1
EASTER_ORTHODOX = 2
EASTER_WESTERN = 3


def easter(year: int, method: int = EASTER_WESTERN) -> date:
    """Compute the date of Easter Sunday for a given year.

    Args:
        year: The year (1-9999).
        method: One of EASTER_WESTERN (default, Gregorian calendar),
                EASTER_ORTHODOX (Julian algorithm, Gregorian date),
                or EASTER_JULIAN (Julian calendar date).

    Returns:
        A datetime.date for Easter Sunday.
    """
    if not 1 <= year <= 9999:
        raise ValueError(f"year must be between 1 and 9999, got {year}")

    if method not in (EASTER_JULIAN, EASTER_ORTHODOX, EASTER_WESTERN):
        raise ValueError(f"invalid method: {method}")

    y = year
    g = y % 19
    e = 0

    if method < 3:
        # Julian-based methods (EASTER_JULIAN and EASTER_ORTHODOX)
        i = (19 * g + 15) % 30
        j = (y + y // 4 + i) % 7
        if method == 2:
            # Convert Julian date to Gregorian by adding offset
            e = 10
            if y > 1600:
                e = e + y // 100 - 16 - (y // 100 - 16) // 4
    else:
        # Western/Gregorian method
        c = y // 100
        h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
        i = h - (h // 28) * (1 - (h // 28) * (29 // (h + 1)) * ((21 - g) // 11))
        j = (y + y // 4 + i + 2 - c + c // 4) % 7

    # p can be from -6 to 56 corresponding to dates 22 March to 23 May
    p = i - j + e
    d = 1 + (p + 27 + (p + 6) // 40) % 31
    m = 3 + (p + 26) // 30

    return date(y, m, d)
