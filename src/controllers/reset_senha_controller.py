"""Fluxo de reset de senha (sem envio de email — link e exibido em flash)."""

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.models import db, Usuario, SenhaFracaError
from controllers.audit import log_audit

reset_bp = Blueprint('reset', __name__)

TOKEN_VALIDADE_HORAS = 1


@reset_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()

        # Mensagem sempre igual (nao revela se o email existe)
        msg_padrao = ('Se o e-mail estiver cadastrado, um link de reset foi gerado. '
                      'Em produção este link seria enviado por e-mail.')
        if usuario:
            token = secrets.token_urlsafe(32)
            usuario.token_reset = token
            usuario.token_reset_expira_em = datetime.utcnow() + timedelta(hours=TOKEN_VALIDADE_HORAS)
            db.session.commit()
            link = url_for('reset.reset_senha', token=token, _external=True)
            flash(f'{msg_padrao} Para fins de desenvolvimento, o link é: {link}', 'info')
        else:
            flash(msg_padrao, 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/esqueci_senha.html')


@reset_bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset_senha(token):
    usuario = Usuario.query.filter_by(token_reset=token).first()
    if (not usuario
            or not usuario.token_reset_expira_em
            or usuario.token_reset_expira_em < datetime.utcnow()):
        flash('Link de reset inválido ou expirado.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nova = request.form.get('senha', '')
        confirmar = request.form.get('confirmar', '')
        if nova != confirmar:
            flash('A confirmação não confere com a nova senha.', 'danger')
            return render_template('auth/reset_senha.html', token=token)
        try:
            usuario.set_senha(nova)
        except SenhaFracaError as e:
            flash(str(e), 'danger')
            return render_template('auth/reset_senha.html', token=token)
        usuario.token_reset = None
        usuario.token_reset_expira_em = None
        db.session.commit()
        log_audit('RESET_SENHA', entidade='usuario', id_entidade=usuario.id,
                  id_usuario=usuario.id)
        flash('Senha redefinida com sucesso. Faça login com a nova senha.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_senha.html', token=token)
