"""Catálogo de ferramentas (tools) que a IA pode chamar para consultar o banco.

PRINCÍPIO DE SEGURANÇA: a IA nunca escreve SQL. Ela escolhe entre estas
funções pré-definidas. Cada função reaplica, em CÓDIGO, o mesmo controle de
acesso dos controllers:
  - admin: vê tudo
  - padrão: só o que tem id_usuario == current_user.id

O limite de permissão vive aqui, não no prompt. Prompt injection não vaza
dados porque a função simplesmente não retorna o que está fora do escopo.
Cada função também faz WHITELIST de campos (nunca devolve senha_hash,
senha_app_cifrada, token_reset, etc.).
"""

from datetime import date

from werkzeug.datastructures import MultiDict

from models.models import (db, Paciente, Avaliacao, Usuario, LogAuditoria,
                           DadosSocioeconomicos, FAIXAS_RENDA, BAIXA_RENDA_FAIXAS)
from controllers.audit import log_audit
from controllers.relatorio_stats import (montar_query, calcular_kpis,
                                         frequencia_sintomas, _calc_idade)


# ---------------- handlers ----------------

def _tool_buscar_pacientes(current_user, args):
    termo = (args.get('termo') or '').strip()
    q = Paciente.query.filter(Paciente.removido_em.is_(None))
    if not current_user.is_admin:
        q = q.filter(Paciente.id_usuario == current_user.id)
    if termo:
        q = q.filter(Paciente.nome.ilike(f'%{termo}%'))
    pacientes = q.order_by(Paciente.nome).limit(20).all()
    return {
        'total': len(pacientes),
        'pacientes': [
            {'id': p.id, 'nome': p.nome, 'sexo': p.sexo,
             'idade': _calc_idade(p.data_nascimento)}
            for p in pacientes
        ],
    }


def _carregar_paciente_scoped(current_user, paciente_id):
    """Retorna (paciente, None) ou (None, erro) aplicando ownership."""
    try:
        pid = int(paciente_id)
    except (ValueError, TypeError):
        return None, {'erro': 'paciente_id inválido.'}
    p = Paciente.query.filter_by(id=pid).filter(Paciente.removido_em.is_(None)).first()
    if p is None:
        return None, {'erro': 'Paciente não encontrado.'}
    if not current_user.is_admin and p.id_usuario != current_user.id:
        return None, {'erro': 'Sem permissão para acessar este paciente.'}
    return p, None


def _tool_detalhes_paciente(current_user, args):
    p, erro = _carregar_paciente_scoped(current_user, args.get('paciente_id'))
    if erro:
        return erro
    out = {
        'id': p.id, 'nome': p.nome, 'cpf': p.cpf, 'sexo': p.sexo,
        'idade': _calc_idade(p.data_nascimento),
        'email': p.email or None,
        'responsavel': (p.responsavel_obj.nome if p.responsavel_obj else None),
        'total_avaliacoes': len(p.avaliacoes),
    }
    an = p.anamnese
    if an:
        out['anamnese'] = {
            'ja_fez_exame_dna': an.ja_fez_exame_dna_label,
            'resultado_exame': an.resultado_exame_label,
            'interesse_exame_pcr': an.interesse_exame_pcr_label,
            'diagnostico_autismo': an.diagnostico_autismo_label,
            'tem_irmaos': an.tem_irmaos_label,
            'familia_neurodesenvolvimento': an.familia_neurodesenvolvimento_label,
            'familia_menopausa_precoce': an.familia_menopausa_precoce_label,
            'familia_ataxia_tremores': an.familia_ataxia_tremores_label,
            'sugestivo_pre_mutacao': an.sugestivo_pre_mutacao,
        }
    ult = max(p.avaliacoes, key=lambda a: a.data, default=None) if p.avaliacoes else None
    if ult:
        out['ultima_avaliacao'] = {
            'data': ult.data.isoformat(),
            'score': round(ult.score, 4),
            'recomendacao': ult.recomendacao,
        }
    return out


def _tool_historico_avaliacoes(current_user, args):
    p, erro = _carregar_paciente_scoped(current_user, args.get('paciente_id'))
    if erro:
        return erro
    avals = sorted([a for a in p.avaliacoes if a.removido_em is None],
                   key=lambda a: a.data, reverse=True)
    return {
        'paciente': p.nome,
        'avaliacoes': [
            {'data': a.data.isoformat(), 'score': round(a.score, 4),
             'recomendacao': a.recomendacao,
             'versao': (a.versao_pesos.nome if a.versao_pesos else None)}
            for a in avals
        ],
    }


def _tool_estatisticas(current_user, args):
    filtros = MultiDict()
    for chave in ('data_inicio', 'data_fim', 'sexo', 'recomendacao'):
        valor = (args.get(chave) or '').strip()
        if valor:
            filtros[chave] = valor
    # montar_query aplica o scoping admin/padrão automaticamente
    avaliacoes = montar_query(filtros, current_user).all()
    kpis = calcular_kpis(avaliacoes)
    top = frequencia_sintomas(avaliacoes, top_n=5)
    return {
        'kpis': kpis,
        'top_sintomas': [{'sintoma': label, 'frequencia': n} for label, n in top],
        'escopo': 'todos' if current_user.is_admin else 'apenas seus pacientes',
    }


# --- admin-only ---

def _tool_resumo_socioeconomico(current_user, args):
    total_pac = Paciente.query.filter(Paciente.removido_em.is_(None)).count()
    com_dados = (DadosSocioeconomicos.query
                 .join(Paciente, DadosSocioeconomicos.id_paciente == Paciente.id)
                 .filter(Paciente.removido_em.is_(None)).count())
    rows = (DadosSocioeconomicos.query
            .join(Paciente, DadosSocioeconomicos.id_paciente == Paciente.id)
            .filter(Paciente.removido_em.is_(None),
                    DadosSocioeconomicos.renda_faixa.isnot(None))
            .with_entities(DadosSocioeconomicos.renda_faixa, db.func.count())
            .group_by(DadosSocioeconomicos.renda_faixa).all())
    mapa = {faixa: n for faixa, n in rows}
    baixa = sum(mapa.get(f, 0) for f in BAIXA_RENDA_FAIXAS)
    return {
        'total_pacientes': total_pac,
        'com_dados_socioeconomicos': com_dados,
        'cobertura_pct': round(com_dados / total_pac * 100, 1) if total_pac else 0.0,
        'distribuicao_renda': [
            {'faixa': label, 'pacientes': mapa.get(chave, 0)}
            for chave, label in FAIXAS_RENDA
        ],
        'perfil_baixa_renda': baixa,
    }


def _tool_logs_recentes(current_user, args):
    try:
        limite = min(int(args.get('limite', 20)), 50)
    except (ValueError, TypeError):
        limite = 20
    q = LogAuditoria.query
    acao = (args.get('acao') or '').strip()
    if acao:
        q = q.filter(LogAuditoria.acao == acao)
    logs = q.order_by(LogAuditoria.data_hora.desc()).limit(limite).all()
    return {
        'logs': [
            {'quando': l.data_hora.strftime('%d/%m/%Y %H:%M'),
             'usuario': (l.usuario.nome if l.usuario else None),
             'acao': l.acao, 'entidade': l.entidade}
            for l in logs
        ],
    }


def _tool_listar_profissionais(current_user, args):
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return {
        'profissionais': [
            {'nome': u.nome, 'perfil': u.perfil,
             'qtd_pacientes': Paciente.query.filter(
                 Paciente.id_usuario == u.id, Paciente.removido_em.is_(None)).count()}
            for u in usuarios
        ],
    }


# ---------------- registry ----------------

def _spec(nome, descricao, propriedades=None, obrigatorios=None):
    return {
        'type': 'function',
        'function': {
            'name': nome,
            'description': descricao,
            'parameters': {
                'type': 'object',
                'properties': propriedades or {},
                'required': obrigatorios or [],
            },
        },
    }


TOOLS = {
    'buscar_pacientes': {
        'handler': _tool_buscar_pacientes,
        'admin_only': False,
        'spec': _spec('buscar_pacientes',
                      'Busca pacientes por nome (ou lista os primeiros). '
                      'Retorna id, nome, sexo e idade.',
                      {'termo': {'type': 'string',
                                 'description': 'Parte do nome do paciente (opcional).'}}),
    },
    'detalhes_paciente': {
        'handler': _tool_detalhes_paciente,
        'admin_only': False,
        'spec': _spec('detalhes_paciente',
                      'Detalhes de um paciente: dados básicos, anamnese (histórico '
                      'clínico/familiar) e última avaliação. Use o id de buscar_pacientes.',
                      {'paciente_id': {'type': 'integer', 'description': 'ID do paciente.'}},
                      ['paciente_id']),
    },
    'historico_avaliacoes': {
        'handler': _tool_historico_avaliacoes,
        'admin_only': False,
        'spec': _spec('historico_avaliacoes',
                      'Lista todas as avaliações (triagens) de um paciente com data, '
                      'score e recomendação.',
                      {'paciente_id': {'type': 'integer', 'description': 'ID do paciente.'}},
                      ['paciente_id']),
    },
    'estatisticas': {
        'handler': _tool_estatisticas,
        'admin_only': False,
        'spec': _spec('estatisticas',
                      'KPIs das avaliações (total, % encaminhamento, score médio) e top '
                      'sintomas. Filtros opcionais. Respeita o escopo do usuário.',
                      {'data_inicio': {'type': 'string', 'description': 'YYYY-MM-DD (opcional).'},
                       'data_fim': {'type': 'string', 'description': 'YYYY-MM-DD (opcional).'},
                       'sexo': {'type': 'string', 'description': "'M' ou 'F' (opcional)."},
                       'recomendacao': {'type': 'string',
                                        'description': "'ENCAMINHAR' ou 'NÃO ENCAMINHAR' (opcional)."}}),
    },
    'resumo_socioeconomico': {
        'handler': _tool_resumo_socioeconomico,
        'admin_only': True,
        'spec': _spec('resumo_socioeconomico',
                      'Resumo socioeconômico AGREGADO de todos os pacientes: distribuição '
                      'de renda, cobertura e contagem de baixa renda. Apenas admin.'),
    },
    'logs_recentes': {
        'handler': _tool_logs_recentes,
        'admin_only': True,
        'spec': _spec('logs_recentes',
                      'Eventos recentes da auditoria do sistema. Apenas admin.',
                      {'acao': {'type': 'string',
                                'description': "Filtrar por ação, ex 'LOGIN', 'CREATE' (opcional)."},
                       'limite': {'type': 'integer', 'description': 'Máx de registros (até 50).'}}),
    },
    'listar_profissionais': {
        'handler': _tool_listar_profissionais,
        'admin_only': True,
        'spec': _spec('listar_profissionais',
                      'Lista os profissionais/usuários do sistema e quantos pacientes cada '
                      'um tem. Nunca expõe e-mail ou senha. Apenas admin.'),
    },
}


def specs(current_user):
    """Specs das tools disponíveis para o papel do usuário (admin vê todas)."""
    return [t['spec'] for t in TOOLS.values()
            if current_user.is_admin or not t['admin_only']]


def dispatch(nome, current_user, args):
    """Executa uma tool com validação de permissão + auditoria. Sempre retorna dict."""
    tool = TOOLS.get(nome)
    if tool is None:
        return {'erro': f'Ferramenta desconhecida: {nome}.'}
    if tool['admin_only'] and not current_user.is_admin:
        return {'erro': 'Sem permissão: esta consulta é restrita a administradores.'}

    args = args or {}
    try:
        resultado = tool['handler'](current_user, args)
    except Exception as e:  # nunca derruba o chat
        resultado = {'erro': f'Falha ao executar a consulta: {e}'}

    log_audit('CHAT_CONSULTA', entidade='chat',
              detalhes={'tool': nome, 'args': args})
    return resultado
