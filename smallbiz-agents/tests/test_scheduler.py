from backend import imap_client, scheduler


def test_poll_mailbox_records_success(monkeypatch):
    monkeypatch.setattr(imap_client, "poll_inbox", lambda: 3)
    count = scheduler.poll_mailbox()
    assert count == 3
    status = scheduler.last_poll_status()
    assert status["success"] is True
    assert status["processed"] == 3
    assert status["error"] is None
    assert status["at"] is not None


def test_poll_mailbox_records_failure_instead_of_raising(monkeypatch):
    def boom():
        raise ConnectionError("mailbox unreachable")

    monkeypatch.setattr(imap_client, "poll_inbox", boom)
    count = scheduler.poll_mailbox()
    assert count == 0
    status = scheduler.last_poll_status()
    assert status["success"] is False
    assert "mailbox unreachable" in status["error"]
