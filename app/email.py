import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from threading import Thread
from config import Config


def _send_smtp(msg: MIMEMultipart) -> None:
    context = ssl.create_default_context() if Config.MAIL_USE_TLS else None
    try:
        if Config.MAIL_USE_TLS:
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                if Config.MAIL_USERNAME:
                    server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                if Config.MAIL_USERNAME:
                    server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
    except Exception:
        pass


def send_email(subject: str, sender: str, recipients: list, text_body: str,
               html_body: str, attachments=None, sync: bool = False) -> None:
    if not Config.MAIL_SERVER:
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    if attachments:
        msg_mixed = MIMEMultipart('mixed')
        msg_mixed['Subject'] = subject
        msg_mixed['From'] = sender
        msg_mixed['To'] = ', '.join(recipients)
        msg_mixed.attach(msg)
        for filename, mimetype, data in attachments:
            maintype, subtype = mimetype.split('/', 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(data if isinstance(data, bytes) else data.encode())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg_mixed.attach(part)
        msg = msg_mixed

    if sync:
        _send_smtp(msg)
    else:
        Thread(target=_send_smtp, args=(msg,)).start()
