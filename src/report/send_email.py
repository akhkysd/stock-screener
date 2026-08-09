import argparse
import os
import smtplib
from collections.abc import Callable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Protocol, cast

from src.report.email_formatter import markdown_to_email_html

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class SMTPClient(Protocol):
    def __enter__(self) -> "SMTPClient": ...
    def __exit__(self, *exc: object) -> bool | None: ...
    def login(self, user: str, password: str) -> object: ...
    def sendmail(self, from_addr: str, to_addrs: list[str], msg: str) -> object: ...


def _default_smtp_client() -> SMTPClient:
    return cast(SMTPClient, smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT))


def send_report_email(
    report_path: Path,
    subject: str,
    sender: str,
    password: str,
    recipient: str,
    smtp_client_factory: Callable[[], SMTPClient] = _default_smtp_client,
) -> None:
    markdown_text = report_path.read_text(encoding="utf-8")
    html = markdown_to_email_html(markdown_text, title=subject)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.attach(MIMEText(markdown_text, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    with smtp_client_factory() as server:
        server.login(sender, password)
        server.sendmail(sender, [recipient], message.as_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="日次レポートをメール送信")
    parser.add_argument("report_path", type=Path)
    args = parser.parse_args()

    sender = os.environ["GMAIL_USERNAME"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("REPORT_EMAIL", sender)
    date = args.report_path.stem
    subject = f"国内割安・底値株レポート {date}"

    send_report_email(args.report_path, subject, sender, password, recipient)
    print(f"メール送信完了: {recipient}")


if __name__ == "__main__":
    main()
