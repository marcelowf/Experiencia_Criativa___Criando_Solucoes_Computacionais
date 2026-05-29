"""Testes do helper de auditoria."""

import json

from models.models import LogAuditoria


def test_log_audit_grava_basico(auth_client, paciente_factory, app):
    paciente_factory(nome='Paciente Audit')
    auth_client.post(
        '/pacientes/novo',
        data={
            'nome': 'Outro',
            'cpf': '52998224725',
            'sexo': 'M',
            'data_nascimento': '2010-05-15',
            'responsavel': '',
            'consentimento': 'on',
        },
        follow_redirects=True,
    )
    with app.app_context():
        log = LogAuditoria.query.filter_by(acao='CREATE', entidade='paciente').first()
        assert log is not None
        assert log.id_usuario is not None
        detalhes = json.loads(log.detalhes)
        assert detalhes['nome'] == 'Outro'


def test_log_audit_login_falho_sem_usuario(client, app, db):
    client.post('/login', data={'email': 'inexistente@x.com', 'senha': 'x'})
    with app.app_context():
        log = LogAuditoria.query.filter_by(acao='LOGIN_FALHO').first()
        assert log is not None
        assert log.id_usuario is None  # falha de login nao tem usuario
