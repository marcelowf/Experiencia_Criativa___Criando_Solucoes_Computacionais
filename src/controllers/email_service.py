"""Servico de envio de e-mail via SMTP do Gmail (senha de app).

A configuracao (remetente + senha de app cifrada) vive no banco (EmailConfig).
A senha e cifrada com Fernet, usando uma chave derivada do SECRET_KEY.
"""

import base64
import hashlib
import smtplib
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from models.models import EmailConfig

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587


class EmailNaoConfiguradoError(RuntimeError):
    """Envio solicitado sem configuracao de e-mail ativa."""


class SenhaAppInvalidaError(RuntimeError):
    """Senha cifrada nao pode ser decifrada (provavelmente SECRET_KEY mudou)."""


def _fernet():
    chave = base64.urlsafe_b64encode(
        hashlib.sha256(current_app.config['SECRET_KEY'].encode()).digest()
    )
    return Fernet(chave)


def cifrar_senha(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decifrar_senha(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise SenhaAppInvalidaError(
            'A senha de app não pôde ser decifrada. Reconfigure o e-mail.'
        ) from e


def email_destino(paciente) -> str:
    """Cascata: paciente.email -> responsavel.email -> '' (digitar manual)."""
    if paciente is None:
        return ''
    if paciente.email:
        return paciente.email
    resp = getattr(paciente, 'responsavel_obj', None)
    if resp and resp.email:
        return resp.email
    return ''


def get_config():
    return EmailConfig.query.first()


def email_configurado() -> bool:
    c = get_config()
    return bool(c and c.ativo and c.remetente_email and c.senha_app_cifrada)


def enviar_email(destinatario, assunto, corpo_html, anexos=None):
    """Envia um e-mail HTML. `anexos`: lista de (nome, bytes, mimetype)."""
    c = get_config()
    if not (c and c.ativo and c.remetente_email and c.senha_app_cifrada):
        raise EmailNaoConfiguradoError('Envio de e-mail não está configurado.')

    senha = decifrar_senha(c.senha_app_cifrada)

    msg = EmailMessage()
    remetente = (
        f'{c.remetente_nome} <{c.remetente_email}>' if c.remetente_nome else c.remetente_email
    )
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.set_content('Seu cliente de e-mail não suporta HTML.')
    msg.add_alternative(corpo_html, subtype='html')

    for nome, conteudo, mimetype in anexos or []:
        maintype, _, subtype = mimetype.partition('/')
        msg.add_attachment(conteudo, maintype=maintype, subtype=subtype, filename=nome)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(c.remetente_email, senha)
        s.send_message(msg)
