"""Tela de administração do assistente de IA.

URL e modelo são decisão de dev (env var) — aqui o admin só controla criatividade,
máximo de consultas por resposta e o liga/desliga.
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_login import login_required

from models.models import db, AiConfig
from controllers.audit import admin_required, log_audit
from controllers.ai_service import ia_configurada, listar_modelos, IaIndisponivelError

ai_config_bp = Blueprint('ai_config', __name__, url_prefix='/config/ia')


def _get_or_create():
    c = AiConfig.query.first()
    if c is None:
        c = AiConfig(temperatura=0.3, max_iteracoes=5, ativo=True)
        db.session.add(c)
        db.session.commit()
    return c


@ai_config_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    config = _get_or_create()
    if request.method == 'POST':
        try:
            temperatura = float((request.form.get('temperatura') or '0.3').replace(',', '.'))
        except ValueError:
            temperatura = 0.3
        try:
            max_iteracoes = int(request.form.get('max_iteracoes') or 5)
        except ValueError:
            max_iteracoes = 5

        config.temperatura = max(0.0, min(temperatura, 1.0))
        config.max_iteracoes = max(1, min(max_iteracoes, 10))
        config.ativo = True  # salvar reativa
        db.session.commit()
        log_audit('UPDATE', entidade='ai_config', id_entidade=config.id, detalhes={
            'temperatura': config.temperatura,
            'max_iteracoes': config.max_iteracoes, 'ativo': True,
        })
        flash('Configuração da IA salva.', 'success')
        return redirect(url_for('ai_config.index'))

    return render_template('config/ia.html', config=config,
                           configurado=ia_configurada(),
                           modelo=current_app.config.get('OLLAMA_MODEL'),
                           base_url=current_app.config.get('OLLAMA_URL'))


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
        flash('Assistente de IA desativado — o chat foi ocultado para todos.', 'success')
    return redirect(url_for('ai_config.index'))
