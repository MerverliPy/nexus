"""Tests for recurrence engine — rrule parsing and next-occurrence generation.

Uses real dateutil.rrule for accurate edge-case coverage: end-of-month,
leap year, invalid RRULE strings.
"""

from datetime import UTC, datetime

import pytest
from dateutil.rrule import rrulestr

from nexus.utils.recurrence import generate_due_dates, next_occurrence, rrule_description


# ── next_occurrence ──────────────────────────────────────────────────────────


class TestNextOccurrence:
    def test_daily(self):
        after = datetime(2024, 1, 1, tzinfo=UTC)
        nxt = next_occurrence("FREQ=DAILY", after=after)
        assert nxt is not None
        assert nxt > after
        # Should be the next day (Jan 2)
        assert nxt.day == 2

    def test_daily_with_interval(self):
        after = datetime(2024, 1, 1, tzinfo=UTC)
        nxt = next_occurrence("FREQ=DAILY;INTERVAL=3", after=after)
        assert nxt is not None
        # Next occurrence after after is 2024-01-04
        assert nxt.date().day == 4

    def test_weekly(self):
        after = datetime(2024, 1, 1, tzinfo=UTC)
        nxt = next_occurrence("FREQ=WEEKLY;BYDAY=MO", after=after)
        assert nxt is not None
        # Jan 1, 2024 is a Monday, so next Monday is Jan 8
        assert nxt.weekday() == 0  # Monday

    def test_weekly_tuesday(self):
        after = datetime(2024, 1, 1, tzinfo=UTC)  # Monday
        nxt = next_occurrence("FREQ=WEEKLY;BYDAY=TU", after=after)
        assert nxt is not None
        # Next Tuesday is Jan 2
        assert nxt.date().day == 2

    def test_weekly_multiple_days(self):
        after = datetime(2024, 1, 3, tzinfo=UTC)  # Wednesday
        nxt = next_occurrence("FREQ=WEEKLY;BYDAY=MO,WE,FR", after=after)
        assert nxt is not None
        # After Wednesday, next is Friday Jan 5
        assert nxt.date().day == 5

    def test_monthly(self):
        after = datetime(2024, 1, 15, tzinfo=UTC)
        nxt = next_occurrence("FREQ=MONTHLY", after=after)
        assert nxt is not None
        assert nxt.month == 2
        assert nxt.day == 15

    def test_yearly(self):
        after = datetime(2024, 6, 15, tzinfo=UTC)
        nxt = next_occurrence("FREQ=YEARLY", after=after)
        assert nxt is not None
        assert nxt.year == 2025
        assert nxt.month == 6

    # ── Edge cases ───────────────────────────────────────────────────────

    def test_end_of_month_january(self):
        """Jan 31 monthly — Feb has no 31st, so dateutil rolls to Mar 31."""
        after = datetime(2024, 1, 31, tzinfo=UTC)
        nxt = next_occurrence("FREQ=MONTHLY", after=after)
        assert nxt is not None
        # dateutil rolls to March 31 (Feb has no 31st)
        assert nxt.month == 3
        assert nxt.day == 31

    def test_end_of_month_leap_year(self):
        """Feb 29 in a leap year, next monthly -> March 29."""
        after = datetime(2024, 2, 29, tzinfo=UTC)
        nxt = next_occurrence("FREQ=MONTHLY", after=after)
        assert nxt is not None
        assert nxt.month == 3
        assert nxt.day == 29

    def test_end_of_month_non_leap(self):
        """Feb 28 in a non-leap year, next monthly -> March 28."""
        after = datetime(2023, 2, 28, tzinfo=UTC)
        nxt = next_occurrence("FREQ=MONTHLY", after=after)
        assert nxt is not None
        assert nxt.month == 3
        assert nxt.day == 28

    def test_after_passed_as_none_uses_now(self):
        """When after is None, uses current time (just verify it doesn't crash)."""
        nxt = next_occurrence("FREQ=DAILY", after=None)
        assert nxt is not None
        assert nxt > datetime.now(UTC)  # not really, but should be > "after"

    def test_invalid_rrule_returns_none(self):
        assert next_occurrence("NOT AN RRULE") is None

    def test_empty_string_returns_none(self):
        assert next_occurrence("") is None

    def test_daily_count_limited(self):
        """COUNT=1 means only one occurrence exists, after returns None."""
        after = datetime(2024, 1, 1, tzinfo=UTC)
        nxt = next_occurrence("FREQ=DAILY;COUNT=1", after=after)
        # There IS one occurrence at Jan 1, but after(inc=False) means after Jan 1 -> None
        assert nxt is None

    def test_until_date(self):
        """UNTIL in the past means no future occurrences."""
        after = datetime(2024, 6, 1, tzinfo=UTC)
        nxt = next_occurrence("FREQ=DAILY;UNTIL=20240101T000000Z", after=after)
        assert nxt is None


# ── generate_due_dates ───────────────────────────────────────────────────────


class TestGenerateDueDates:
    def test_generates_correct_count(self):
        from_date = datetime(2024, 1, 1, tzinfo=UTC)
        dates = generate_due_dates("FREQ=DAILY", from_date, count=3)
        assert len(dates) == 3

    def test_generates_sequential_days(self):
        from_date = datetime(2024, 1, 1, tzinfo=UTC)
        dates = generate_due_dates("FREQ=DAILY", from_date, count=3)
        assert dates[0].day == 1
        assert dates[1].day == 2
        assert dates[2].day == 3

    def test_default_count(self):
        from_date = datetime(2024, 1, 1, tzinfo=UTC)
        dates = generate_due_dates("FREQ=DAILY", from_date)
        assert len(dates) == 5

    def test_weekly(self):
        from_date = datetime(2024, 1, 1, tzinfo=UTC)  # Monday
        dates = generate_due_dates("FREQ=WEEKLY;BYDAY=MO", from_date, count=2)
        assert len(dates) == 2
        assert dates[0].day == 1  # Jan 1
        assert dates[1].day == 8  # Jan 8

    def test_invalid_rrule_returns_from_date(self):
        from_date = datetime(2024, 6, 15, tzinfo=UTC)
        dates = generate_due_dates("BAD RRULE", from_date, count=3)
        assert dates == [from_date]


# ── rrule_description ────────────────────────────────────────────────────────


class TestRruleDescription:
    def test_daily(self):
        desc = rrule_description("FREQ=DAILY")
        assert "Repeats daily" in desc

    def test_daily_with_interval(self):
        desc = rrule_description("FREQ=DAILY;INTERVAL=3")
        assert "every 3 days" in desc

    def test_weekly(self):
        desc = rrule_description("FREQ=WEEKLY;BYDAY=MO")
        assert "Weekly" in desc or "weekly" in desc

    def test_weekly_multiple_days(self):
        desc = rrule_description("FREQ=WEEKLY;BYDAY=MO,WE,FR")
        assert "mon" in desc and "wed" in desc and "fri" in desc

    def test_monthly(self):
        desc = rrule_description("FREQ=MONTHLY")
        assert "monthly" in desc.lower()

    def test_yearly(self):
        desc = rrule_description("FREQ=YEARLY")
        assert "yearly" in desc.lower()

    def test_invalid_rrule(self):
        desc = rrule_description("NOT AN RRULE")
        assert "Repeats" in desc
        assert "NOT AN RRULE" in desc

    def test_empty_string(self):
        desc = rrule_description("")
        assert "Repeats" in desc

    def test_weekly_interval(self):
        desc = rrule_description("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO")
        assert "every 2 weeks" in desc

    def test_weekly_case_insensitivity(self):
        desc = rrule_description("freq=weekly;byday=mo")
        assert "mon" in desc
