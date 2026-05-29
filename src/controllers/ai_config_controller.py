"""Tela de administração para configurar o assistente de IA (Ollama)."""

import os

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from models.models import db, AiConfig
from controllers.audit import admin_required, log_audit
from controllers.ai_service import (ia_configurada, listar_modelos,
                                    IaNaoConfiguradaError, IaIndisponivelError)

ai_config_bp = Blueprint('ai_config', __name__, url_prefix='/config/ia')


@ai_config_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    config = AiConfig.query.first()
    if request.method == 'POST':
        base_url = (request.form.get('base_url') or '').strip()
        modelo = (request.form.get('modelo') or '').strip()
        if not base_url or not modelo:
            flash('Informe a URL do servidor e o modelo.', 'danger')
            return render_template('config/ia.html', config=config,
                                   configurado=ia_configurada(), form_data=request.form,
                                   default_base_url=os.environ.get('OLLAMA_URL', 'http://ollama:11434'))
        try:
            temperatura = float((request.form.get('temperatura') or '0.3').replace(',', '.'))
        except ValueError:
            temperatura = 0.3
        try:
            max_iteracoes = int(request.form.get('max_iteracoes') or 5)
        except ValueError:
            max_iteracoes = 5

        if config is None:
            config = AiConfig()
            db.session.add(config)
        config.base_url = base_url
        config.modelo = modelo
        config.temperatura = max(0.0, min(temperatura, 1.0))
        config.max_iteracoes = max(1, min(max_iteracoes, 10))
        config.ativo = True
        db.session.commit()
        log_audit('UPDATE', entidade='ai_config', id_entidade=config.id, detalhes={
            'base_url': base_url, 'modelo': modelo,
            'temperatura': config.temperatura, 'ativo': config.ativo,
        })
        flash('Configuração da IA salva.', 'success')
        return redirect(url_for('ai_config.index'))

    return render_template('config/ia.html', config=config,
                           configurado=ia_configurada(), form_data=None,
                           default_base_url=os.environ.get('OLLAMA_URL', 'http://ollama:11434'))


@ai_config_bp.route('/testar', methods=['POST'])
@login_required
@admin_required
def testar():
    try:
        modelos = listar_modelos()
        if modelos:
            flash('Conexão OK. Modelos disponíveis: ' + ', '.join(modelos), 'success')
        else:
            flash('Conectado, mas nenhum modelo instalado. Rode: ollama pull <modelo>.', 'warning')
    except IaNaoConfiguradaError as e:
        flash(str(e), 'danger')
    except IaIndisponivelError as e:
        flash(str(e), 'danger')
    return redirect(url_for('ai_config.index'))


@ai_config_bp.route('/desativar', methods=['POST'])
@login_required
@admin_required
def desativar():
    config = AiConfig.query.first()
    if config and config.ativo:
        config.ativo = False
        db.session.commit()
        log_audit('UPDATE', entidade='ai_config', id_entidade=config.id,
                  detalhes={'ativo': False})
        flash('Assistente de IA desativado.', 'success')
    return redirect(url_for('ai_config.index'))
