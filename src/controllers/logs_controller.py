import json

from flask import Blueprint, render_template, request
from flask_login import login_required

from controllers.audit import admin_required
from models.models import LogAuditoria, Usuario

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

ACOES = ['CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'LOGIN_FALHO']
ENTIDADES = ['paciente', 'avaliacao', 'sintoma', 'usuario']


@logs_bp.route('/')
@login_required
@admin_required
def index():
    query = LogAuditoria.query

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    id_usuario = request.args.get('id_usuario')
    acao = request.args.get('acao')
    entidade = request.args.get('entidade')

    if data_inicio:
        query = query.filter(LogAuditoria.data_hora >= data_inicio)
    if data_fim:
        query = query.filter(LogAuditoria.data_hora <= f'{data_fim} 23:59:59')
    if id_usuario:
        query = query.filter_by(id_usuario=int(id_usuario))
    if acao:
        query = query.filter_by(acao=acao)
    if entidade:
        query = query.filter_by(entidade=entidade)

    logs = query.order_by(LogAuditoria.data_hora.desc()).limit(500).all()
    usuarios = Usuario.query.order_by(Usuario.nome).all()

    def parse_detalhes(d):
        if not d:
            return None
        try:
            return json.loads(d)
        except Exception:
            return d

    return render_template(
        'logs/index.html',
        logs=logs,
        usuarios=usuarios,
        acoes=ACOES,
        entidades=ENTIDADES,
        parse_detalhes=parse_detalhes,
    )
