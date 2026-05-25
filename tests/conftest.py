"""Fixtures pytest para a suite de testes."""

import os
import sys
from datetime import date

import pytest

# Garantir que `src/` esteja no sys.path:
# - local: tests/ fica ao lado de src/        -> ../src
# - container: /app/tests/ com src em /app    -> ..
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, '..')))

from controllers.app_controller import create_app
from models.models import db as _db, Usuario, UserPreference, Paciente, Sintoma, Responsavel


@pytest.fixture(scope='session')
def app():
    app = create_app(config_overrides={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'BABEL_DEFAULT_LOCALE': 'pt_BR',
    })
    return app


@pytest.fixture(scope='session')
def _db_session(app):
    """Garante schema criado uma vez por sessao."""
    with app.app_context():
        _db.create_all()
        yield _db


@pytest.fixture
def db(app, _db_session):
    """Limpa o conteudo entre testes mantendo o schema."""
    with app.app_context():
        # Apagar tudo respeitando FKs (em ordem reversa)
        from models.models import (LogAuditoria, SintomaAvaliacao, Avaliacao,
                                   SintomaPesoVersao, VersaoPesos,
                                   UserPreference, Paciente, Responsavel,
                                   QrCadastroToken, Usuario, Sintoma)
        for model in [LogAuditoria, SintomaAvaliacao, Avaliacao,
                      SintomaPesoVersao, VersaoPesos,
                      UserPreference, Paciente, Responsavel,
                      QrCadastroToken, Usuario, Sintoma]:
            _db.session.query(model).delete()
        _db.session.commit()

        # Reseed sintomas, admin, prefs e V1 inicial
        from controllers.app_controller import (_seed_sintomas, _seed_admin,
                                                _seed_user_preferences,
                                                _seed_versao_pesos_inicial)
        _seed_sintomas()
        _seed_admin()
        _seed_user_preferences()
        _seed_versao_pesos_inicial()
        yield _db


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def admin(db):
    return Usuario.query.filter_by(email='admin@admin.com').first()


@pytest.fixture
def usuario_padrao(db):
    u = Usuario(nome='Dr. Teste', email='teste@teste.com', perfil='padrao')
    u.set_senha('senha123')
    _db.session.add(u)
    _db.session.flush()
    _db.session.add(UserPreference(id_usuario=u.id))
    _db.session.commit()
    return u


@pytest.fixture
def paciente_factory(db, admin):
    """Cria um paciente vinculado ao admin (default) ou ao usuario passado."""
    contador = {'n': 0}

    def _criar(nome='Paciente Teste', sexo='M',
               data_nascimento=date(2015, 1, 1), cpf=None,
               id_usuario=None, responsavel='Responsavel'):
        contador['n'] += 1
        if cpf is None:
            # CPF valido gerado deterministicamente
            cpfs_validos = ['111.444.777-35', '529.982.247-25', '390.533.447-05',
                            '824.345.288-19', '063.158.510-29']
            cpf = cpfs_validos[(contador['n'] - 1) % len(cpfs_validos)]
        p = Paciente(nome=nome, cpf=cpf, sexo=sexo, data_nascimento=data_nascimento,
                     responsavel=responsavel,
                     id_usuario=(id_usuario or admin.id))
        _db.session.add(p)
        _db.session.commit()
        return p

    return _criar


@pytest.fixture
def auth_client(client, admin):
    """Cliente ja autenticado como admin."""
    client.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    return client


@pytest.fixture
def auth_client_padrao(client, usuario_padrao):
    client.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    return client
