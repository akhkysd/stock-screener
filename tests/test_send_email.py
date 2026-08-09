import email
from email.header import decode_header

from src.report.send_email import send_report_email


def _decode_subject(raw: str) -> str:
    parts = decode_header(raw)
    return "".join(
        text.decode(charset or "utf-8") if isinstance(text, bytes) else text
        for text, charset in parts
    )


class FakeSMTPServer:
    def __init__(self):
        self.login_calls = []
        self.sendmail_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, sender, password):
        self.login_calls.append((sender, password))

    def sendmail(self, sender, recipients, message_string):
        self.sendmail_calls.append((sender, recipients, message_string))


def test_send_report_email_logs_in_and_sends(tmp_path):
    report_path = tmp_path / "2026-08-09.md"
    report_path.write_text("# レポート\n\n本文です。", encoding="utf-8")
    server = FakeSMTPServer()

    send_report_email(
        report_path,
        subject="件名テスト",
        sender="sender@example.com",
        password="app-password",
        recipient="recipient@example.com",
        smtp_client_factory=lambda: server,
    )

    assert server.login_calls == [("sender@example.com", "app-password")]
    assert len(server.sendmail_calls) == 1
    sender, recipients, message_string = server.sendmail_calls[0]
    assert sender == "sender@example.com"
    assert recipients == ["recipient@example.com"]

    parsed = email.message_from_string(message_string)
    assert _decode_subject(parsed["Subject"]) == "件名テスト"
    assert parsed["To"] == "recipient@example.com"

    parts = {part.get_content_type(): part for part in parsed.walk()}
    assert "text/plain" in parts
    assert "text/html" in parts
    assert "レポート" in parts["text/html"].get_payload(decode=True).decode("utf-8")


def test_send_report_email_includes_plain_text_fallback(tmp_path):
    report_path = tmp_path / "2026-08-09.md"
    report_path.write_text("本文のみ", encoding="utf-8")
    server = FakeSMTPServer()

    send_report_email(
        report_path,
        subject="件名",
        sender="a@example.com",
        password="pw",
        recipient="b@example.com",
        smtp_client_factory=lambda: server,
    )

    message_string = server.sendmail_calls[0][2]
    parsed = email.message_from_string(message_string)
    parts = {part.get_content_type(): part for part in parsed.walk()}
    assert "本文のみ" in parts["text/plain"].get_payload(decode=True).decode("utf-8")
