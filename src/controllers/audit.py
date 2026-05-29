import json
from functools import wraps

from flask import abort, request
from flask_login import current_user

from models.models import LogAuditoria, db


def log_audit(acao, entidade=None, id_entidade=None, detalhes=None, id_usuario=None):
    """
    Registra uma entrada na tabela de auditoria.

    acao: 'CREATE' | 'UPDATE' | 'DELETE' | 'LOGIN' | 'LOGOUT' | 'LOGIN_FALHO'
    entidade: 'paciente' | 'avaliacao' | 'sintoma' | 'usuario' | None
    id_entidade: id do registro afetado (None para login/logout)
    detalhes: dict serializado como JSON (diff antes/depois, email tentado, etc.)
    id_usuario: forçar usuario logado (None usa current_user; LOGIN_FALHO pode passar None explicito)
    """
    if id_usuario is None and current_user.is_authenticated:
        id_usuario = current_user.id

    detalhes_json = json.dumps(detalhes, ensure_ascii=False, default=str) if detalhes else None
    ip = request.remote_addr if request else None

    entry = LogAuditoria(
        id_usuario=id_usuario,
        acao=acao,
        entidade=entidade,
        id_entidade=id_entidade,
        detalhes=detalhes_json,
        ip=ip,
    )
    db.session.add(entry)
    db.session.commit()


def admin_required(f):
    """Decorator: bloqueia rotas que so admin pode acessar."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapper
