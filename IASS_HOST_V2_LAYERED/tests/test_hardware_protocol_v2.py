import time
from iass.hardware_interface.protocol.contract import CommandEnvelope, CommandLifecycle, Lifecycle, Priority, ErrorCode
from iass.hardware_interface.services.transactions import CommandTransactionManager


def test_command_envelope_expiry_and_priority():
    c = CommandEnvelope("door_1", "LOCK", priority=Priority.EMERGENCY, expires_at=time.time()-1)
    assert c.priority == Priority.EMERGENCY
    assert c.expired()


def test_transaction_manager_records_lifecycle_without_fake_ack():
    m = CommandTransactionManager(dedup_window=10)
    c = CommandEnvelope("door_1", "LOCK")
    assert m.admit(c)[0]
    m.sent(c.command_id)
    tx = m.get(c.command_id)
    assert tx.state == Lifecycle.SENT.value
    m.confirm(c.command_id, "TELEMETRY_CONFIRMED")
    assert m.get(c.command_id).state == Lifecycle.CONFIRMED.value
