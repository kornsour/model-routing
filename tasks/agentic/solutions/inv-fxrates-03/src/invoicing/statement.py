"""Per-customer balances in US dollars, for the ``report`` command."""

from __future__ import annotations

from invoicing.calc import total
from invoicing.fx import RateProvider, cached, to_usd
from invoicing.models import Invoice


def customer_balances(invoices: list[Invoice], rates: RateProvider) -> dict[str, float]:
    """``{customer name: total billed, in USD}``, customers in first-seen order."""
    rates = cached(rates)
    balances: dict[str, float] = {}
    for inv in invoices:
        usd = to_usd(total(inv), inv.currency, rates)
        balances[inv.customer.name] = round(balances.get(inv.customer.name, 0.0) + usd, 2)
    return balances
