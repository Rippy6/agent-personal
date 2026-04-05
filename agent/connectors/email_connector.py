"""メール連携 — メール受信でゴール自動生成

IMAP でメールボックスを監視し、新着メールの件名をゴールに変換。
結果をSMTPで返信。stdlib の imaplib/smtplib のみ使用。

セットアップ:
1. IMAP/SMTP 対応メールアカウント（Gmail、Outlookなど）
2. Gmail の場合: アプリパスワードを生成
3. 環境変数: EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, SMTP_SERVER
"""

import email
import imaplib
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.header import decode_header


class EmailConnector:
    """メール受信でゴール自動生成、結果を返信"""

    def __init__(
        self,
        address: str,
        password: str,
        imap_server: str = "imap.gmail.com",
        smtp_server: str = "smtp.gmail.com",
        imap_port: int = 993,
        smtp_port: int = 587,
        allowed_senders: list[str] | None = None,
    ):
        self.address = address
        self.password = password
        self.imap_server = imap_server
        self.smtp_server = smtp_server
        self.imap_port = imap_port
        self.smtp_port = smtp_port
        self.allowed_senders = allowed_senders  # Noneなら全送信者を受信
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_message = None

    def set_message_handler(self, callback):
        """メール受信時のコールバック: (subject, body, sender) -> None"""
        self._on_message = callback

    def start(self):
        """バックグラウンドでメールボックス監視開始"""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send(self, to: str, subject: str, body: str) -> bool:
        """メール送信"""
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.address
            msg["To"] = to

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.address, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False

    def _poll_loop(self):
        """メールボックスを定期的にチェック"""
        while self._running:
            try:
                self._check_mail()
            except Exception:
                pass
            time.sleep(30)  # 30秒間隔

    def _check_mail(self):
        """未読メールを取得"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.address, self.password)
            mail.select("INBOX")

            _, msg_nums = mail.search(None, "UNSEEN")
            if not msg_nums[0]:
                mail.logout()
                return

            for num in msg_nums[0].split()[:5]:  # 最大5件
                _, data = mail.fetch(num, "(RFC822)")
                if not data or not data[0]:
                    continue

                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                sender = self._decode_header(msg.get("From", ""))
                subject = self._decode_header(msg.get("Subject", ""))
                body = self._get_body(msg)

                # 送信者制限
                if self.allowed_senders:
                    sender_addr = email.utils.parseaddr(sender)[1]
                    if sender_addr not in self.allowed_senders:
                        continue

                if self._on_message and subject:
                    self._on_message(subject, body, sender)

            mail.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    @staticmethod
    def _decode_header(value: str) -> str:
        """メールヘッダーをデコード"""
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    @staticmethod
    def _get_body(msg) -> str:
        """メール本文を取得"""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""
