"""Endpoints do widget de chat de IA (bolha flutuante).

O widget usa uma ÚNICA conversa "corrente" por usuário (privada). Respostas em
streaming via SSE.
"""

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from controllers import ai_service
from models.models import ChatConversa, db

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


def _conversa_corrente(criar=True):
    """A conversa ativa mais recente do usuário (cria uma se não houver)."""
    c = (
        ChatConversa.query.filter_by(id_usuario=current_user.id)
        .filter(ChatConversa.removido_em.is_(None))
        .order_by(ChatConversa.atualizado_em.desc())
        .first()
    )
    if c is None and criar:
        c = ChatConversa(id_usuario=current_user.id, titulo='Nova conversa')
        db.session.add(c)
        db.session.commit()
    return c


@chat_bp.route('/widget/historico')
@login_required
def historico():
    """Mensagens da conversa corrente (para popular o widget ao abrir)."""
    c = _conversa_corrente(criar=False)
    msgs = []
    if c:
        for m in c.mensagens:
            if m.papel in ('user', 'assistant') and (m.conteudo or '').strip():
                msgs.append({'papel': m.papel, 'conteudo': m.conteudo})
    return jsonify({'mensagens': msgs})


@chat_bp.route('/widget/nova', methods=['POST'])
@login_required
def nova():
    """Encerra a conversa corrente (soft delete) — a próxima mensagem cria outra."""
    from datetime import datetime

    c = _conversa_corrente(criar=False)
    if c:
        c.removido_em = datetime.utcnow()
        db.session.commit()
    return jsonify({'ok': True})


@chat_bp.route('/widget/mensagem', methods=['POST'])
@login_required
def mensagem():
    texto = (request.form.get('texto') or '').strip()
    if not texto:
        return jsonify({'erro': 'Mensagem vazia.'}), 400
    if not ai_service.ia_configurada():
        return jsonify({'erro': 'O assistente de IA está indisponível no momento.'}), 503

    conversa = _conversa_corrente(criar=True)
    # capturamos o usuário concreto: o generator roda fora do proxy de request
    usuario = current_user._get_current_object()

    @stream_with_context
    def gerar():
        try:
            for evento in ai_service.chat_stream(conversa, texto, usuario):
                yield f'data: {json.dumps(evento, ensure_ascii=False)}\n\n'
        except ai_service.IaNaoConfiguradaError:
            yield f'data: {json.dumps({"tipo": "erro", "texto": "Assistente desativado."})}\n\n'
        except ai_service.IaIndisponivelError:
            yield f'data: {json.dumps({"tipo": "erro", "texto": "O assistente está indisponível. Tente novamente em instantes."})}\n\n'

    return Response(
        gerar(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
