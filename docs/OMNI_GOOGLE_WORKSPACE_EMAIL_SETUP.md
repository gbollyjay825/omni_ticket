# Omni Email Setup - Google Workspace

Use these instructions to connect a Wakanow Gmail mailbox to Omni so customer emails create tickets and Omni replies are sent through Gmail.

**Omni:** `https://omni.wakanow.com`

**Market:** NG - Nigeria

**Mailbox:** `jimb@wakanow.com`, or the dedicated support mailbox approved by IT

## Before you start

You need:

- Google Workspace administrator access;
- Omni administrator access;
- IMAP enabled for the support mailbox;
- 2-Step Verification enabled on the mailbox; and
- a Google App Password approved by IT/InfoSec for the current Omni connector.

> Do not use the mailbox's normal Google password. If Wakanow does not allow App Passwords, stop and ask the Omni engineering team to complete the Google OAuth connection.

## 1. Enable Gmail IMAP

1. Sign in to [Google Admin](https://admin.google.com/).
2. Go to **Apps -> Google Workspace -> Gmail -> End User Access**.
3. Select the organizational unit containing the support mailbox.
4. Open **POP and IMAP access**.
5. Enable **IMAP access** and save.
6. Confirm that the mailbox can receive an external test email.

## 2. Create the Gmail App Password

1. Sign in as the support mailbox owner.
2. Confirm **2-Step Verification** is enabled.
3. Open [Google App Passwords](https://myaccount.google.com/apppasswords).
4. Create an App Password named **Omni Ticket**.
5. Store the generated 16-digit password in the approved password vault.

If App Passwords is unavailable, do not bypass the restriction. Contact Omni engineering for the OAuth setup.

## 3. Connect the mailbox in Omni

1. Sign in to `https://omni.wakanow.com` as an administrator.
2. Select **NG - Nigeria**.
3. Go to **Admin -> Connectors -> Email setup**.
4. Enter the following values.

### Incoming email - IMAP

| Field | Value |
|---|---|
| Enabled | On |
| Host | `imap.gmail.com` |
| Port | `993` |
| Username | `jimb@wakanow.com` or the approved mailbox |
| Mailbox | `INBOX` |
| Password | Google App Password |
| SSL | On |
| Mark seen | On |
| Clear password | Off |

### Outgoing replies - SMTP

| Field | Value |
|---|---|
| Enabled | On |
| Host | `smtp.gmail.com` |
| Port | `587` |
| Username | `jimb@wakanow.com` or the approved mailbox |
| From address | Approved mailbox or verified Gmail alias |
| Password | Same Google App Password |
| STARTTLS | On |
| SSL | Off |
| Clear password | Off |

5. Select **Save email setup**.
6. Confirm Omni shows:
   - **Inbound - IMAP live**;
   - **Outbound - SMTP live**; and
   - **Secrets - Stored write-only**.

## 4. Route email to an Omni team

1. Go to **Admin -> People -> Groups**.
2. Open the team that should receive the email.
3. Set **Team email** to the exact mailbox or Gmail alias used by customers.
4. Enable **Email** for the group's channels.
5. Save the group.

If an alias is used, confirm in Google Workspace that the alias delivers into the mailbox Omni polls.

## 5. Test the connection

1. From an external email address, send a message to the support address with a unique subject such as `OMNI EMAIL TEST 20260715-1200`.
2. Wait up to two minutes.
3. Confirm a ticket appears in Omni with the correct sender, subject, message, market, and team.
4. Reply from the Omni ticket and confirm the external sender receives it.
5. Reply again from the external mailbox and confirm the message is added to the same Omni ticket.

## Quick troubleshooting

| Problem | Check |
|---|---|
| Gmail login fails | IMAP enabled, correct mailbox, 2-Step Verification active, valid App Password, normal password not used |
| No ticket appears | Email reached Gmail `INBOX`, inbound enabled, `imap.gmail.com:993`, SSL on |
| Omni reply fails | `smtp.gmail.com:587`, STARTTLS on, SSL off, approved From address |
| Wrong team receives ticket | The group's **Team email** exactly matches the mailbox or alias used by the customer |

## Setup complete

Email setup is complete when an external email creates an Omni ticket, an Omni reply reaches the sender, and the customer's reply returns to the same ticket.
