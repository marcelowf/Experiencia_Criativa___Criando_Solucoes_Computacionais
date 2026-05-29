"""Testes das tools de IA — foco em SCOPING e WHITELIST (segurança)."""

import json
from datetime import date

from models.models import db, Avaliacao
from controllers import ai_tools


def _avaliacao(paciente, usuario, score=0.5, rec='ENCAMINHAR'):
    av = Avaliacao(id_paciente=paciente.id, data=date.today(),
                   score=score, recomendacao=rec, id_usuario=usuario.id)
    db.session.add(av)
    db.session.commit()
    return av


# ---------- scoping: buscar_pacientes ----------

def test_buscar_pacientes_padrao_so_ve_os_seus(db, admin, usuario_padrao, paciente_factory):
    paciente_factory(nome='Paciente Do Admin', id_usuario=admin.id)
    paciente_factory(nome='Paciente Do Padrao', id_usuario=usuario_padrao.id,
                     cpf='529.982.247-25')

    r = ai_tools._tool_buscar_pacientes(usuario_padrao, {})
    nomes = [p['nome'] for p in r['pacientes']]
    assert 'Paciente Do Padrao' in nomes
    assert 'Paciente Do Admin' not in nomes


def test_buscar_pacientes_admin_ve_todos(db, admin, usuario_padrao, paciente_factory):
    paciente_factory(nome='Paciente Do Admin', id_usuario=admin.id)
    paciente_factory(nome='Paciente Do Padrao', id_usuario=usuario_padrao.id,
                     cpf='529.982.247-25')

    r = ai_tools._tool_buscar_pacientes(admin, {})
    nomes = [p['nome'] for p in r['pacientes']]
    assert 'Paciente Do Admin' in nomes
    assert 'Paciente Do Padrao' in nomes


# ---------- scoping: detalhes_paciente (ownership) ----------

def test_detalhes_paciente_padrao_nao_ve_de_outro(db, admin, usuario_padrao, paciente_factory):
    p = paciente_factory(nome='Sigiloso', id_usuario=admin.id)
    r = ai_tools._tool_detalhes_paciente(usuario_padrao, {'paciente_id': p.id})
    assert 'erro' in r
    assert 'Sigiloso' not in json.dumps(r, default=str)


def test_detalhes_paciente_admin_ve(db, admin, paciente_factory):
    p = paciente_factory(nome='Visivel', id_usuario=admin.id)
    r = ai_tools._tool_detalhes_paciente(admin, {'paciente_id': p.id})
    assert r['nome'] == 'Visivel'


def test_detalhes_paciente_inexistente(db, admin):
    r = ai_tools._tool_detalhes_paciente(admin, {'paciente_id': 99999})
    assert 'erro' in r


# ---------- scoping: estatisticas via montar_query ----------

def test_estatisticas_respeita_escopo(db, admin, usuario_padrao, paciente_factory):
    p_admin = paciente_factory(nome='A', id_usuario=admin.id)
    p_padrao = paciente_factory(nome='B', id_usuario=usuario_padrao.id, cpf='529.982.247-25')
    _avaliacao(p_admin, admin)
    _avaliacao(p_padrao, usuario_padrao)

    r_padrao = ai_tools._tool_estatisticas(usuario_padrao, {})
    assert r_padrao['kpis']['total'] == 1
    assert r_padrao['escopo'] == 'apenas seus pacientes'

    r_admin = ai_tools._tool_estatisticas(admin, {})
    assert r_admin['kpis']['total'] == 2


# ---------- admin-only ----------

def test_specs_filtra_admin_only(db, admin, usuario_padrao):
    nomes_padrao = [s['function']['name'] for s in ai_tools.specs(usuario_padrao)]
    assert 'buscar_pacientes' in nomes_padrao
    assert 'logs_recentes' not in nomes_padrao
    assert 'resumo_socioeconomico' not in nomes_padrao
    assert 'listar_profissionais' not in nomes_padrao

    nomes_admin = [s['function']['name'] for s in ai_tools.specs(admin)]
    assert 'logs_recentes' in nomes_admin
    assert 'resumo_socioeconomico' in nomes_admin


def test_dispatch_admin_only_bloqueia_padrao(db, usuario_padrao):
    # admin_only retorna antes do log_audit -> não precisa de request context
    r = ai_tools.dispatch('logs_recentes', usuario_padrao, {})
    assert 'erro' in r
    assert 'permiss' in r['erro'].lower()


def test_dispatch_tool_desconhecida(db, admin):
    r = ai_tools.dispatch('tool_que_nao_existe', admin, {})
    assert 'erro' in r


# ---------- whitelist (sem dados sensíveis) ----------

def test_listar_profissionais_sem_senha_nem_email(db, admin, usuario_padrao):
    r = ai_tools._tool_listar_profissionais(admin, {})
    blob = json.dumps(r, default=str).lower()
    assert 'senha' not in blob
    assert '@' not in blob  # nenhum e-mail vazado
    assert any(p['nome'] for p in r['profissionais'])


def test_detalhes_paciente_nao_expoe_campos_internos(db, admin, paciente_factory):
    p = paciente_factory(nome='Z', id_usuario=admin.id)
    r = ai_tools._tool_detalhes_paciente(admin, {'paciente_id': p.id})
    assert 'senha_hash' not in r
    assert 'id_usuario' not in r  # não expõe FKs internas
