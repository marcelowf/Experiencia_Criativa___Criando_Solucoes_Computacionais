"""Tela de administracao para configurar o envio de e-mail (Gmail)."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from controllers.audit import admin_required, log_audit
from controllers.email_service import (
    EmailNaoConfiguradoError,
    SenhaAppInvalidaError,
    cifrar_senha,
    email_configurado,
    enviar_email,
    get_config,
)
from models.models import EmailConfig, db

email_config_bp = Blueprint('email_config', __name__, url_prefix='/config/email')


@email_config_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    config = get_config()
    if request.method == 'POST':
        remetente_email = (request.form.get('remetente_email') or '').strip()
        remetente_nome = (request.form.get('remetente_nome') or '').strip() or 'Triagem SXF'
        senha = (request.form.get('senha_app') or '').strip()

        if not remetente_email:
            flash('Informe o e-mail remetente.', 'danger')
            return render_template(
                'config/email.html',
                config=config,
                configurado=email_configurado(),
                form_data=request.form,
            )

        if config is None:
            if not senha:
                flash('Informe a senha de app na primeira configuração.', 'danger')
                return render_template(
                    'config/email.html',
                    config=config,
                    configurado=email_configurado(),
                    form_data=request.form,
                )
            config = EmailConfig(
                remetente_email=remetente_email,
                remetente_nome=remetente_nome,
                senha_app_cifrada=cifrar_senha(senha),
                ativo=True,
            )
            db.session.add(config)
            senha_alterada = True
        else:
            config.remetente_email = remetente_email
            config.remetente_nome = remetente_nome
            config.ativo = True
            senha_alterada = bool(senha)
            if senha:
                config.senha_app_cifrada = cifrar_senha(senha)

        db.session.commit()
        log_audit(
            'UPDATE',
            entidade='email_config',
            id_entidade=config.id,
            detalhes={
                'remetente': remetente_email,
                'senha_alterada': senha_alterada,
                'ativo': config.ativo,
            },
        )
        flash('Configuração de e-mail salva.', 'success')
        return redirect(url_for('email_config.index'))

    return render_template('config/email.html', config=config, configurado=email_configurado())


@email_config_bp.route('/testar', methods=['POST'])
@login_required
@admin_required
def testar():
    try:
        enviar_email(
            current_user.email,
            'Teste de e-mail — Triagem SXF',
            '<p>Este é um e-mail de teste. A configuração está funcionando.</p>',
        )
        flash(f'E-mail de teste enviado para {current_user.email}.', 'success')
    except EmailNaoConfiguradoError:
        flash('Configure o e-mail antes de testar.', 'danger')
    except SenhaAppInvalidaError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Falha ao enviar: {e}', 'danger')
    return redirect(url_for('email_config.index'))


@email_config_bp.route('/desativar', methods=['POST'])
@login_required
@admin_required
def desativar():
    config = get_config()
    if config and config.ativo:
        config.ativo = False
        db.session.commit()
        log_audit(
            'UPDATE',
            entidade='email_config',
            id_entidade=config.id,
            detalhes={'ativo': False},
        )
        flash('Envio de e-mail desativado.', 'success')
    return redirect(url_for('email_config.index'))
