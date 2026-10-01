"""Money helpers for the billing exporter: exact allocation, currency minor
units, conversion and display.  Not implemented yet - see the ticket."""

from __future__ import annotations


def allocate(amount, ratios):
    raise NotImplementedError


def split(amount, n):
    raise NotImplementedError


def to_minor(amount, currency, rounding="half_even"):
    raise NotImplementedError


def convert(minor, from_currency, to_currency, rate, rounding="half_even"):
    raise NotImplementedError


def format_money(minor, currency, locale="en"):
    raise NotImplementedError
