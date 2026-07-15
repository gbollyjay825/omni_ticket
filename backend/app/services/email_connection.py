from __future__ import annotations

import imaplib
import smtplib
import ssl

from app.core.config import settings
from app.db.email_settings import RuntimeEmailProviderSettings
from app.models.domain import EmailConnectionCheck, EmailConnectionTestResult, utc_now


class EmailConnectionTester:
    def test(self, config: RuntimeEmailProviderSettings, *, market_id: str) -> EmailConnectionTestResult:
        return EmailConnectionTestResult(
            market_id=market_id,
            tested_at=utc_now(),
            inbound=self._test_inbound(config),
            outbound=self._test_outbound(config),
        )

    def _test_inbound(self, config: RuntimeEmailProviderSettings) -> EmailConnectionCheck:
        missing: list[str] = []
        if not config.inbound_enabled:
            missing.append("Inbound email is disabled")
        if not config.inbound_host:
            missing.append("IMAP host")
        if not config.inbound_username:
            missing.append("IMAP username")
        if not config.inbound_password:
            missing.append("IMAP app password")
        if missing:
            return EmailConnectionCheck(
                configured=False,
                connected=False,
                detail="Missing: " + ", ".join(missing) + ".",
            )

        connection: imaplib.IMAP4 | None = None
        try:
            imap_class = imaplib.IMAP4_SSL if config.inbound_use_ssl else imaplib.IMAP4
            connection = imap_class(
                config.inbound_host,
                config.inbound_port,
                timeout=settings.email_imap_timeout_seconds,
            )
            connection.login(config.inbound_username, config.inbound_password or "")
            status, _ = connection.select(config.inbound_mailbox, readonly=True)
            if status != "OK":
                return EmailConnectionCheck(
                    configured=True,
                    connected=False,
                    detail="IMAP authentication succeeded, but the configured mailbox could not be opened.",
                )
            return EmailConnectionCheck(
                configured=True,
                connected=True,
                detail="IMAP authentication and mailbox access succeeded.",
            )
        except imaplib.IMAP4.error as exc:
            message = str(exc).lower()
            if "application-specific password" in message or "app password" in message:
                detail = "Gmail requires an app password for this mailbox."
            else:
                detail = "IMAP authentication failed. Check the mailbox address and app password."
            return EmailConnectionCheck(configured=True, connected=False, detail=detail)
        except (OSError, TimeoutError):
            return EmailConnectionCheck(
                configured=True,
                connected=False,
                detail="Could not connect to the IMAP server. Check the host, port, SSL, and network access.",
            )
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass

    def _test_outbound(self, config: RuntimeEmailProviderSettings) -> EmailConnectionCheck:
        missing: list[str] = []
        if not config.outbound_enabled:
            missing.append("Outbound email is disabled")
        if not config.outbound_host:
            missing.append("SMTP host")
        if not config.outbound_from_email:
            missing.append("From address")
        if config.outbound_username and not config.outbound_password:
            missing.append("SMTP app password")
        if config.outbound_use_ssl and config.outbound_use_starttls:
            missing.append("Choose SSL or STARTTLS")
        if missing:
            return EmailConnectionCheck(
                configured=False,
                connected=False,
                detail="Missing: " + ", ".join(missing) + ".",
            )

        try:
            smtp_class = smtplib.SMTP_SSL if config.outbound_use_ssl else smtplib.SMTP
            with smtp_class(
                config.outbound_host,
                config.outbound_port,
                timeout=settings.email_smtp_timeout_seconds,
            ) as connection:
                connection.ehlo()
                if config.outbound_use_starttls:
                    connection.starttls(context=ssl.create_default_context())
                    connection.ehlo()
                if config.outbound_username:
                    connection.login(config.outbound_username, config.outbound_password or "")
                connection.noop()
            return EmailConnectionCheck(
                configured=True,
                connected=True,
                detail="SMTP authentication succeeded. No message was sent.",
            )
        except smtplib.SMTPAuthenticationError:
            return EmailConnectionCheck(
                configured=True,
                connected=False,
                detail="SMTP authentication failed. Check the mailbox address and app password.",
            )
        except smtplib.SMTPServerDisconnected:
            return EmailConnectionCheck(
                configured=True,
                connected=False,
                detail="The SMTP server closed the connection during authentication. Check the mailbox address and app password.",
            )
        except (smtplib.SMTPException, OSError, TimeoutError):
            return EmailConnectionCheck(
                configured=True,
                connected=False,
                detail="Could not complete the SMTP connection. Check the host, port, encryption, and credentials.",
            )


email_connection_tester = EmailConnectionTester()
