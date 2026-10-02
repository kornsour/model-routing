from triage.audit import AuditLog


def test_chain_verifies():
    log = AuditLog()
    log.append({"type": "a"})
    log.append({"type": "b"})
    assert log.verify_chain()


def test_tampering_is_detected():
    log = AuditLog()
    log.append({"type": "a"})
    log.append({"type": "b"})
    log.entries[0]["event"]["type"] = "z"
    assert not log.verify_chain()
