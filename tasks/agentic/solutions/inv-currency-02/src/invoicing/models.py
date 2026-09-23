"""Core data model: customers, line items, invoices."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CURRENCY = "USD"


@dataclass
class Customer:
    id: str
    name: str
    email: str = ""


@dataclass
class LineItem:
    description: str
    quantity: int
    unit_price: float

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass
class Invoice:
    id: str
    customer: Customer
    items: list[LineItem] = field(default_factory=list)
    tax_rate: float = 0.0
    discount_pct: float = 0.0
    status: str = "draft"
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self) -> None:
        self.currency = (self.currency or DEFAULT_CURRENCY).strip().upper()

    @property
    def subtotal(self) -> float:
        return round(sum(item.amount for item in self.items), 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer": {
                "id": self.customer.id,
                "name": self.customer.name,
                "email": self.customer.email,
            },
            "items": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in self.items
            ],
            "tax_rate": self.tax_rate,
            "discount_pct": self.discount_pct,
            "status": self.status,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Invoice:
        customer = Customer(**raw["customer"])
        items = [LineItem(**item) for item in raw["items"]]
        return cls(
            id=raw["id"],
            customer=customer,
            items=items,
            tax_rate=raw.get("tax_rate", 0.0),
            discount_pct=raw.get("discount_pct", 0.0),
            status=raw.get("status", "draft"),
            currency=raw.get("currency", DEFAULT_CURRENCY),
        )
