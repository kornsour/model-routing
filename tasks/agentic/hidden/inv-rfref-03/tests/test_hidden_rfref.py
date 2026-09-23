from invoicing.cli import main
from invoicing.models import Customer, Invoice
from invoicing.reference import payment_reference
from invoicing.remittance import Payment, match_payments

CUSTOMER = Customer(id="c1", name="Acme")


def _iso11649_valid(reference: str) -> bool:
    """Independent ISO 11649 check: move RFkk to the end, letters A=10..Z=35, mod 97 == 1."""
    compact = reference.replace(" ", "").upper()
    rearranged = compact[4:] + compact[:4]
    return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97 == 1


# brief: "references printed on invoices must be valid ISO 11649 creditor references" -
# the standard's own worked example (body 539007547034) is RF18 5390 0754 7034
def test_standard_example_reference():
    assert payment_reference("539007547034") == "RF18 5390 0754 7034"


# brief: "must be valid ISO 11649 creditor references ... for every invoice id, including ids
# with letters"
def test_references_with_letters_verify():
    for invoice_id in ["3fa85f64", "7e4d2b19", "0c9e1f7a", "INV000042"]:
        ref = payment_reference(invoice_id)
        assert _iso11649_valid(ref), ref
    assert payment_reference("3fa85f64") == "RF48 3FA8 5F64"


# brief: "valid ISO 11649 ... for every invoice id" - the check digits are always two digits,
# even when their value is below ten
def test_check_digits_below_ten_are_two_digits():
    assert payment_reference("a1b2c3d4") == "RF04 A1B2 C3D4"
    assert payment_reference("00000007") == "RF09 0000 0007"


# brief: "the bank import must match a payment quoting a valid reference, whether the bank
# sends it in print format or electronic format and in any letter case"
def test_remittance_accepts_print_electronic_and_lower_case():
    invoices = [
        Invoice(id="539007547034", customer=CUSTOMER),
        Invoice(id="3fa85f64", customer=CUSTOMER),
    ]
    payments = [
        Payment("2024-03-01", 10.0, "RF18 5390 0754 7034"),
        Payment("2024-03-02", 20.0, "RF18539007547034"),
        Payment("2024-03-03", 30.0, "rf48 3fa8 5f64"),
        Payment("2024-03-04", 40.0, "rf483fa85f64"),
    ]
    matched, unmatched = match_payments(invoices, payments)
    assert [invoice_id for invoice_id, _ in matched] == [
        "539007547034",
        "539007547034",
        "3fa85f64",
        "3fa85f64",
    ]
    assert unmatched == []


# brief: "a reference whose check digits do not verify must never be matched, even when the
# rest of it names one of our invoices"
def test_remittance_rejects_bad_check_digits():
    invoices = [Invoice(id="539007547034", customer=CUSTOMER)]
    bad = [
        Payment("2024-03-01", 10.0, "RF19 5390 0754 7034"),
        Payment("2024-03-01", 10.0, "RF81 5390 0754 7034"),
        Payment("2024-03-01", 10.0, "RF18 5390 0754 7035"),
    ]
    assert match_payments(invoices, bad) == ([], bad)


# brief: "a payment quoting the reference `create` printed must be matched by `remit`"
def test_cli_create_then_remit_matches(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "120"]) == 0
    out = capsys.readouterr().out
    invoice_id = out.split()[2]
    printed = out.split("payment reference:")[1].strip()
    assert _iso11649_valid(printed)
    remittance = tmp_path / "bank.csv"
    electronic = printed.replace(" ", "").lower()
    remittance.write_text(f"2024-03-01,120.00,{electronic}\n2024-03-01,5.00,RF00 NOPE\n")
    assert main(["--db", db, "remit", str(remittance)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].split("\t")[2] == invoice_id
    assert lines[-1] == "matched 1, unmatched 1"
