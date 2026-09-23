"""Exchange rates for reporting in US dollars.

Invoices are billed in their own ``currency`` (an ISO 4217 code, ``USD`` by
default); the ``report`` command also shows everything converted to USD.
Rates come from a remote rate service. :class:`RemoteRates` is a simulated
stand-in for its HTTP client - the real service bills every ``rate`` call
and throttles clients that make too many. Rates move daily. Tests inject
any object with the same ``rate`` method.
"""

from __future__ import annotations

from typing import Protocol


class RateProvider(Protocol):
    def rate(self, currency: str) -> float:
        """US dollars per one unit of ``currency``, as of now."""
        ...


class RemoteRates:
    """Simulated remote rate service (one billed request per ``rate`` call)."""

    _TABLE = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}

    def rate(self, currency: str) -> float:
        try:
            return self._TABLE[currency]
        except KeyError:
            raise ValueError(f"no rate for {currency!r}") from None


class CachedRates:
    """Asks ``provider`` at most once per currency for the lifetime of this object.

    Create one per report run and share it between everything the run
    converts, so each currency costs one remote call per run and a later run
    still sees fresh rates.
    """

    def __init__(self, provider: RateProvider):
        self.provider = provider
        self._rates: dict[str, float] = {}

    def rate(self, currency: str) -> float:
        if currency not in self._rates:
            self._rates[currency] = self.provider.rate(currency)
        return self._rates[currency]


def cached(rates: RateProvider) -> CachedRates:
    """``rates`` wrapped in a :class:`CachedRates`, unless it already is one."""
    return rates if isinstance(rates, CachedRates) else CachedRates(rates)


def to_usd(amount: float, currency: str, rates: RateProvider) -> float:
    """``amount`` of ``currency`` converted to US dollars, rounded to cents."""
    if currency == "USD":
        return round(amount, 2)
    return round(amount * rates.rate(currency), 2)
