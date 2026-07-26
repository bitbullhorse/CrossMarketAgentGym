"""Native and composed market-calendar contract tests."""

from __future__ import annotations

from datetime import date

import pytest

from crossmarket_agentgym.data.calendars import (
    CompositeMarketCalendar,
    MarketCalendar,
    StaticMarketCalendar,
)


def _calendar(name: str, days: tuple[int, ...]) -> StaticMarketCalendar:
    return StaticMarketCalendar(
        name=name,
        all_sessions=tuple(date(2024, 1, day) for day in days),
    )


def test_static_calendar_interval_and_navigation_are_strict() -> None:
    """Navigation does not reuse the queried session or extrapolate boundaries."""
    calendar = _calendar("US", (2, 3, 5))

    assert isinstance(calendar, MarketCalendar)
    assert calendar.sessions(date(2024, 1, 3), date(2024, 1, 5)) == [
        date(2024, 1, 3),
        date(2024, 1, 5),
    ]
    assert calendar.next_session(date(2024, 1, 3)) == date(2024, 1, 5)
    assert calendar.previous_session(date(2024, 1, 5)) == date(2024, 1, 3)
    with pytest.raises(LookupError):
        calendar.next_session(date(2024, 1, 5))


def test_union_and_intersection_preserve_real_component_sessions() -> None:
    """Cross-market modes differ only by explicit set composition."""
    first = _calendar("US", (2, 3, 4))
    second = _calendar("JP", (2, 4, 5))

    union = CompositeMarketCalendar((first, second), mode="union")
    intersection = CompositeMarketCalendar((first, second), mode="intersection")

    assert union.all_sessions == tuple(date(2024, 1, day) for day in (2, 3, 4, 5))
    assert intersection.all_sessions == tuple(date(2024, 1, day) for day in (2, 4))


def test_native_composition_requires_exactly_one_market_calendar() -> None:
    """Native mode remains the exact component rather than a hidden union."""
    first = _calendar("US", (2, 3))
    second = _calendar("JP", (2, 4))

    native = CompositeMarketCalendar((first,), mode="native")

    assert native.all_sessions == first.all_sessions
    with pytest.raises(ValueError, match="exactly one"):
        CompositeMarketCalendar((first, second), mode="native")


def test_scheduled_rebalance_excludes_dates_when_all_markets_are_closed() -> None:
    """An explicit rebalance schedule cannot manufacture an execution session."""
    calendar = _calendar("US", (2, 3, 4))
    composite = CompositeMarketCalendar(
        (calendar,),
        mode="scheduled_rebalance",
        rebalance_sessions=(date(2024, 1, 3), date(2024, 1, 7)),
    )

    assert composite.all_sessions == (date(2024, 1, 3),)


def test_calendar_rejects_invalid_ranges_and_empty_schedule() -> None:
    """Invalid composition is rejected instead of silently returning no sessions."""
    calendar = _calendar("US", (2, 3))

    with pytest.raises(ValueError, match="start"):
        calendar.sessions(date(2024, 1, 3), date(2024, 1, 2))
    with pytest.raises(ValueError, match="explicit sessions"):
        CompositeMarketCalendar((calendar,), mode="scheduled_rebalance")
