"""Assistente de IA — chat com acesso ao banco respeitando permissões."""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, abort)
from flask_login import login_required, current_user

from models.models import db, ChatConversa
from controllers import ai_service

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


def _conversa_do_usuario(id):
    """Carrega conversa garantindo que pertence ao usuário atual (senão 403/404)."""
    conversa = db.get_or_404(ChatConversa, id)
    if conversa.id_usuario != current_user.id or conversa.removido_em is not None:
        abort(403)
    return conversa


def _minhas_conversas():
    return (ChatConversa.query
            .filter_by(id_usuario=current_user.id)
            .filter(ChatConversa.removido_em.is_(None))
            .order_by(ChatConversa.atualizado_em.desc())
            .all())


@chat_bp.route('/')
@login_required
def index():
    conversas = _minhas_conversas()
    ativa = conversas[0] if conversas else None
    return render_template('chat/index.html',
                           conversas=conversas, conversa=ativa,
                           ia_ok=ai_service.ia_configurada())


@chat_bp.route('/<int:id>')
@login_required
def conversa(id):
    conversa = _conversa_do_usuario(id)
    return render_template('chat/index.html',
                           conversas=_minhas_conversas(), conversa=conversa,
                           ia_ok=ai_service.ia_configurada())


@chat_bp.route('/nova', methods=['POST'])
@login_required
def nova():
    c = ChatConversa(id_usuario=current_user.id, titulo='Nova conversa')
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('chat.conversa', id=c.id))


@chat_bp.route('/<int:id>/mensagem', methods=['POST'])
@login_required
def mensagem(id):
    conversa = _conversa_do_usuario(id)
    texto = (request.form.get('texto') or '').strip()
    if not texto:
        return jsonify({'erro': 'Mensagem vazia.'}), 400
    try:
        resultado = ai_service.chat(conversa, texto, current_user)
        return jsonify({'resposta': resultado['resposta'], 'titulo': conversa.titulo})
    except ai_service.IaNaoConfiguradaError:
        return jsonify({'erro': 'O assistente de IA não está configurado. '
                                'Peça a um administrador para ativá-lo.'}), 503
    except ai_service.IaIndisponivelError:
        return jsonify({'erro': 'O assistente está indisponível no momento. '
                                'Tente novamente em instantes.'}), 503


@chat_bp.route('/<int:id>/remover', methods=['POST'])
@login_required
def remover(id):
    from datetime import datetime
    conversa = _conversa_do_usuario(id)
    conversa.removido_em = datetime.utcnow()
    db.session.commit()
    flash('Conversa removida.', 'success')
    return redirect(url_for('chat.index'))
