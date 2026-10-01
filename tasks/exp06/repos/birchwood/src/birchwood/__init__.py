"""Booking calendar for the studio sites."""

HOLD_MINUTES = 15


def hold_expired(age_minutes: float) -> bool:
    return age_minutes >= HOLD_MINUTES
