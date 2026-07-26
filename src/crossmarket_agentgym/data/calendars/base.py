"""Deterministic exchange-session calendars and cross-market composition."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol, runtime_checkable

CalendarMode = Literal["native", "union", "intersection", "scheduled_rebalance"]


@runtime_checkable
class MarketCalendar(Protocol):
    """Read-only calendar contract used by data and environment layers."""

    @property
    def all_sessions(self) -> tuple[date, ...]:
        """Return every known session in ascending order."""
        ...

    def is_trading_day(self, value: date) -> bool:
        """Return whether the date is an eligible session."""
        ...

    def sessions(self, start: date, end: date) -> list[date]:
        """Return inclusive sessions in a closed date interval."""
        ...

    def next_session(self, value: date) -> date:
        """Return the first session strictly after the supplied date."""
        ...

    def previous_session(self, value: date) -> date:
        """Return the last session strictly before the supplied date."""
        ...


@dataclass(frozen=True, slots=True)
class StaticMarketCalendar:
    """Immutable calendar backed by an explicit, auditable session list."""

    name: str
    all_sessions: tuple[date, ...]

    def __post_init__(self) -> None:
        """Canonicalize and validate the supplied sessions."""
        if not self.name.strip():
            raise ValueError("calendar name cannot be empty")
        canonical = tuple(sorted(set(self.all_sessions)))
        if not canonical:
            raise ValueError("calendar requires at least one session")
        object.__setattr__(self, "all_sessions", canonical)

    def is_trading_day(self, value: date) -> bool:
        """Return whether a session exists on the supplied date."""
        index = bisect_left(self.all_sessions, value)
        return index < len(self.all_sessions) and self.all_sessions[index] == value

    def sessions(self, start: date, end: date) -> list[date]:
        """Return inclusive sessions without manufacturing missing dates."""
        if start > end:
            raise ValueError("calendar interval start must not exceed end")
        left = bisect_left(self.all_sessions, start)
        right = bisect_right(self.all_sessions, end)
        return list(self.all_sessions[left:right])

    def next_session(self, value: date) -> date:
        """Return the next known session or fail at the calendar boundary."""
        index = bisect_right(self.all_sessions, value)
        if index >= len(self.all_sessions):
            raise LookupError(f"{self.name} has no session after {value.isoformat()}")
        return self.all_sessions[index]

    def previous_session(self, value: date) -> date:
        """Return the previous known session or fail at the calendar boundary."""
        index = bisect_left(self.all_sessions, value) - 1
        if index < 0:
            raise LookupError(f"{self.name} has no session before {value.isoformat()}")
        return self.all_sessions[index]


class CompositeMarketCalendar(StaticMarketCalendar):
    """Union, intersection, or explicit rebalance composition of market calendars."""

    mode: CalendarMode
    component_names: tuple[str, ...]

    def __init__(
        self,
        calendars: tuple[MarketCalendar, ...],
        *,
        mode: CalendarMode,
        rebalance_sessions: tuple[date, ...] = (),
        name: str | None = None,
    ) -> None:
        """Materialize a deterministic composite from immutable components."""
        if not calendars:
            raise ValueError("composite calendar requires at least one component")
        session_sets = [set(calendar.all_sessions) for calendar in calendars]
        union_sessions: set[date] = set()
        for session_set in session_sets:
            union_sessions.update(session_set)
        if mode == "native":
            if len(calendars) != 1:
                raise ValueError("native mode requires exactly one component")
            combined = session_sets[0]
        elif mode == "union":
            combined = union_sessions
        elif mode == "intersection":
            combined = session_sets[0].copy()
            for session_set in session_sets[1:]:
                combined.intersection_update(session_set)
        elif mode == "scheduled_rebalance":
            if not rebalance_sessions:
                raise ValueError("scheduled_rebalance requires explicit sessions")
            combined = set(rebalance_sessions) & union_sessions
        else:
            raise ValueError(f"unsupported calendar mode: {mode}")
        if not combined:
            raise ValueError("calendar composition produced no sessions")
        StaticMarketCalendar.__init__(
            self,
            name=name or f"composite:{mode}",
            all_sessions=tuple(combined),
        )
        object.__setattr__(self, "mode", mode)
        object.__setattr__(
            self,
            "component_names",
            tuple(
                getattr(calendar, "name", calendar.__class__.__name__)
                for calendar in calendars
            ),
        )
