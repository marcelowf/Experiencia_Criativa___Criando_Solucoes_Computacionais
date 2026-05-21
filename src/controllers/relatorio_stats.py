"""Helpers de filtragem e agregação para os relatórios."""

from collections import Counter, defaultdict
from datetime import date
from statistics import median

from sqlalchemy.orm import joinedload
from models.models import Avaliacao, Paciente, Sintoma, SintomaAvaliacao


FAIXAS_ETARIAS = [
    ('0-5',   0,   5),
    ('6-10',  6,  10),
    ('11-17', 11, 17),
    ('18+',   18, 200),
]


def _calc_idade(data_nasc, hoje=None):
    hoje = hoje or date.today()
    anos = hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))
    return anos


def _faixa_de(idade):
    for nome, mn, mx in FAIXAS_ETARIAS:
        if mn <= idade <= mx:
            return nome
    return '18+'


def montar_query(args, current_user):
    """Aplica filtros da query-string. Retorna query SQLAlchemy."""
    query = (Avaliacao.query
             .join(Paciente, Avaliacao.id_paciente == Paciente.id)
             .options(joinedload(Avaliacao.paciente),
                      joinedload(Avaliacao.usuario))
             .filter(Avaliacao.removido_em.is_(None),
                     Paciente.removido_em.is_(None)))

    if not current_user.is_admin:
        query = query.filter(Avaliacao.id_usuario == current_user.id)

    data_inicio = args.get('data_inicio')
    data_fim = args.get('data_fim')
    id_usuario = args.get('id_usuario')
    id_paciente = args.get('id_paciente')
    sexo = args.get('sexo')
    recomendacao = args.get('recomendacao')
    score_min = args.get('score_min')
    score_max = args.get('score_max')
    faixa = args.get('faixa_etaria')
    sintomas_ids = args.getlist('sintomas_presentes') if hasattr(args, 'getlist') else []

    if data_inicio:
        query = query.filter(Avaliacao.data >= data_inicio)
    if data_fim:
        query = query.filter(Avaliacao.data <= data_fim)
    if id_usuario and current_user.is_admin:
        query = query.filter(Avaliacao.id_usuario == int(id_usuario))
    if id_paciente:
        query = query.filter(Avaliacao.id_paciente == int(id_paciente))
    if sexo in ('M', 'F'):
        query = query.filter(Paciente.sexo == sexo)
    if recomendacao in ('ENCAMINHAR', 'NÃO ENCAMINHAR'):
        query = query.filter(Avaliacao.recomendacao == recomendacao)
    if score_min:
        try:
            query = query.filter(Avaliacao.score >= float(score_min))
        except ValueError:
            pass
    if score_max:
        try:
            query = query.filter(Avaliacao.score <= float(score_max))
        except ValueError:
            pass
    if faixa:
        for nome, mn, mx in FAIXAS_ETARIAS:
            if nome == faixa:
                hoje = date.today()
                limite_velho = date(hoje.year - mx - 1, hoje.month, hoje.day) if mx < 200 else date(1900, 1, 1)
                limite_novo = date(hoje.year - mn, hoje.month, hoje.day)
                query = query.filter(Paciente.data_nascimento > limite_velho,
                                     Paciente.data_nascimento <= limite_novo)
                break
    if sintomas_ids:
        try:
            ids = [int(x) for x in sintomas_ids if x]
            sub = (SintomaAvaliacao.query
                   .filter(SintomaAvaliacao.id_sintoma.in_(ids), SintomaAvaliacao.presente.is_(True))
                   .with_entities(SintomaAvaliacao.id_avaliacao)
                   .subquery())
            query = query.filter(Avaliacao.id.in_(sub))
        except ValueError:
            pass

    return query


def calcular_kpis(avaliacoes):
    total = len(avaliacoes)
    encaminhar = sum(1 for a in avaliacoes if a.recomendacao == 'ENCAMINHAR')
    nao_encaminhar = total - encaminhar
    scores = [a.score for a in avaliacoes]
    return {
        'total': total,
        'encaminhar': encaminhar,
        'nao_encaminhar': nao_encaminhar,
        'pct_encaminhar': round(encaminhar / total * 100, 1) if total else 0.0,
        'score_medio': round(sum(scores) / total, 4) if total else 0.0,
        'score_mediano': round(median(scores), 4) if scores else 0.0,
    }


def dados_por_mes(avaliacoes):
    """Lista [{mes: 'YYYY-MM', encaminhar: N, nao_encaminhar: N}]"""
    grupos = defaultdict(lambda: {'encaminhar': 0, 'nao_encaminhar': 0})
    for a in avaliacoes:
        chave = a.data.strftime('%Y-%m')
        if a.recomendacao == 'ENCAMINHAR':
            grupos[chave]['encaminhar'] += 1
        else:
            grupos[chave]['nao_encaminhar'] += 1
    return [{'mes': k, **v} for k, v in sorted(grupos.items())]


def dados_por_recomendacao(avaliacoes):
    encaminhar = sum(1 for a in avaliacoes if a.recomendacao == 'ENCAMINHAR')
    return {
        'labels': ['ENCAMINHAR', 'NÃO ENCAMINHAR'],
        'values': [encaminhar, len(avaliacoes) - encaminhar],
    }


def dados_por_sexo(avaliacoes):
    grupos = {'M': {'encaminhar': 0, 'nao_encaminhar': 0},
              'F': {'encaminhar': 0, 'nao_encaminhar': 0}}
    for a in avaliacoes:
        sexo = a.paciente.sexo
        key = 'encaminhar' if a.recomendacao == 'ENCAMINHAR' else 'nao_encaminhar'
        if sexo in grupos:
            grupos[sexo][key] += 1
    return grupos


def histograma_scores(avaliacoes, bucket=0.05):
    buckets = defaultdict(int)
    for a in avaliacoes:
        b = round((a.score // bucket) * bucket, 2)
        buckets[b] += 1
    if not buckets:
        return {'labels': [], 'values': []}
    chaves = sorted(buckets.keys())
    return {
        'labels': [f'{k:.2f}' for k in chaves],
        'values': [buckets[k] for k in chaves],
    }


def frequencia_sintomas(avaliacoes, top_n=None):
    """Frequencia absoluta de cada sintoma marcado como presente."""
    ids = [a.id for a in avaliacoes]
    if not ids:
        return []
    rows = (SintomaAvaliacao.query
            .join(Sintoma, SintomaAvaliacao.id_sintoma == Sintoma.id)
            .filter(SintomaAvaliacao.id_avaliacao.in_(ids),
                    SintomaAvaliacao.presente.is_(True))
            .with_entities(Sintoma.label, Sintoma.id)
            .all())
    cont = Counter(r.label for r in rows)
    items = sorted(cont.items(), key=lambda x: x[1], reverse=True)
    if top_n:
        items = items[:top_n]
    return items


def por_profissional(avaliacoes):
    """Para admin: agrupa por nome do usuario."""
    cont = Counter(a.usuario.nome for a in avaliacoes if a.usuario)
    return sorted(cont.items(), key=lambda x: x[1], reverse=True)


def _mascarar_nome(nome: str) -> str:
    """Joao da Silva -> J.S."""
    if not nome:
        return '—'
    partes = [p for p in nome.split() if p]
    iniciais = ''.join(p[0].upper() + '.' for p in partes[:3]) or '—'
    return iniciais


def _mascarar_cpf(cpf: str) -> str:
    """000.000.000-12 -> ***.***.***-12"""
    if not cpf or len(cpf) < 4:
        return '—'
    return f'***.***.***-{cpf[-2:]}'


def montar_tabela(avaliacoes, anonimizar=False):
    """Estrutura simples para exibir/exportar em tabela.

    anonimizar=True mascara nome/cpf/responsavel para conformidade LGPD.
    """
    hoje = date.today()
    linhas = []
    for a in avaliacoes:
        p = a.paciente
        idade = _calc_idade(p.data_nascimento, hoje)
        linhas.append({
            'id': a.id,
            'data': a.data,
            'paciente': _mascarar_nome(p.nome) if anonimizar else p.nome,
            'cpf': _mascarar_cpf(p.cpf) if anonimizar else p.cpf,
            'sexo': p.sexo,
            'idade': idade,
            'faixa': _faixa_de(idade),
            'score': a.score,
            'recomendacao': a.recomendacao,
            'profissional': a.usuario.nome if a.usuario else '—',
        })
    return linhas
