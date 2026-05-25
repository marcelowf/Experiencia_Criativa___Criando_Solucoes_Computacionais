"""Testes do CRUD de pacientes (com foco em CPF e ownership)."""

import json

from controllers.paciente_controller import _cpf_digitos_validos, _normalizar_cpf
from models.models import Paciente, Responsavel


def test_cpf_valido():
    assert _cpf_digitos_validos('11144477735')
    assert _cpf_digitos_validos('52998224725')


def test_cpf_invalido_digitos_iguais():
    assert not _cpf_digitos_validos('11111111111')
    assert not _cpf_digitos_validos('00000000000')


def test_cpf_invalido_dv_errado():
    assert not _cpf_digitos_validos('11144477736')  # ultimo digito errado


def test_cpf_invalido_curto():
    assert not _cpf_digitos_validos('123')


def test_normalizar_cpf_formata():
    assert _normalizar_cpf('11144477735') == '111.444.777-35'
    assert _normalizar_cpf('111.444.777-35') == '111.444.777-35'


def test_normalizar_cpf_rejeita_invalido():
    assert _normalizar_cpf('111.111.111-11') is None
    assert _normalizar_cpf('abc') is None


def test_listar_pacientes_filtra_por_usuario(auth_client_padrao, paciente_factory,
                                             usuario_padrao, admin):
    paciente_factory(nome='Do Outro', id_usuario=admin.id)
    paciente_factory(nome='Meu Paciente', id_usuario=usuario_padrao.id)

    r = auth_client_padrao.get('/pacientes/')
    body = r.data.decode('utf-8')
    assert 'Meu Paciente' in body
    assert 'Do Outro' not in body


def test_cadastro_paciente_cpf_invalido(auth_client):
    r = auth_client.post('/pacientes/novo', data={
        'nome': 'Test', 'cpf': '111.111.111-11', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'responsavel': '',
        'consentimento': 'on',
    })
    body = r.data.decode('utf-8')
    assert 'CPF inválido' in body


def test_cadastro_paciente_ok(auth_client, app, db):
    auth_client.post('/pacientes/novo', data={
        'nome': 'Joao', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'responsavel': 'Mae',
        'consentimento': 'on',
    }, follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Joao').first()
        assert p is not None
        assert p.cpf == '111.444.777-35'
        assert p.consentimento_dado_em is not None


def test_cpf_duplicado_rejeita(auth_client, paciente_factory):
    paciente_factory(nome='Existente', cpf='111.444.777-35')
    r = auth_client.post('/pacientes/novo', data={
        'nome': 'Outro', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'responsavel': '',
        'consentimento': 'on',
    })
    body = r.data.decode('utf-8')
    assert 'Já existe' in body


def test_cadastro_sem_consentimento_rejeita(auth_client):
    r = auth_client.post('/pacientes/novo', data={
        'nome': 'Sem Consent', 'cpf': '52998224725', 'sexo': 'M',
        'data_nascimento': '2015-01-01',
    })
    body = r.data.decode('utf-8')
    assert 'consentimento' in body.lower()


# ---- Tabela Responsavel ----

def test_paciente_sem_responsavel(auth_client, app, db):
    auth_client.post('/pacientes/novo', data={
        'nome': 'Sem Resp', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
    }, follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Sem Resp').first()
        assert p is not None
        assert p.id_responsavel is None
        assert Responsavel.query.count() == 0


def test_paciente_com_responsavel_novo_cria_registro(auth_client, app, db):
    auth_client.post('/pacientes/novo', data={
        'nome': 'Com Resp', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
        'resp_nome': 'Joana Silva', 'resp_cpf': '52998224725',
        'resp_email': 'joana@example.com', 'resp_telefone': '11999990000',
        'resp_parentesco': 'mae',
    }, follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Com Resp').first()
        assert p is not None and p.id_responsavel is not None
        r = Responsavel.query.get(p.id_responsavel)
        assert r.nome == 'Joana Silva'
        assert r.cpf == '529.982.247-25'
        assert r.parentesco == 'mae'


def test_paciente_reaproveita_responsavel_via_id(auth_client, app, db):
    with app.app_context():
        r = Responsavel(nome='Joana', cpf='529.982.247-25', parentesco='mae')
        db.session.add(r)
        db.session.commit()
        resp_id = r.id

    auth_client.post('/pacientes/novo', data={
        'nome': 'Irmao 1', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
        'responsavel_id': str(resp_id),
    }, follow_redirects=True)
    auth_client.post('/pacientes/novo', data={
        'nome': 'Irmao 2', 'cpf': '39053344705', 'sexo': 'F',
        'data_nascimento': '2017-01-01', 'consentimento': 'on',
        'responsavel_id': str(resp_id),
    }, follow_redirects=True)

    with app.app_context():
        # so existe 1 responsavel (nao duplicou)
        assert Responsavel.query.count() == 1
        p1 = Paciente.query.filter_by(nome='Irmao 1').first()
        p2 = Paciente.query.filter_by(nome='Irmao 2').first()
        assert p1.id_responsavel == resp_id
        assert p2.id_responsavel == resp_id


def test_paciente_reaproveita_responsavel_via_cpf(auth_client, app, db):
    """Sem responsavel_id, mas com CPF que ja existe -> reaproveita em vez de duplicar."""
    with app.app_context():
        db.session.add(Responsavel(nome='Joana', cpf='529.982.247-25'))
        db.session.commit()

    auth_client.post('/pacientes/novo', data={
        'nome': 'Filho', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
        'resp_nome': 'Joana Reescrita', 'resp_cpf': '52998224725',
    }, follow_redirects=True)
    with app.app_context():
        assert Responsavel.query.count() == 1
        r = Responsavel.query.first()
        # Mantem o nome original (nao sobrescreve)
        assert r.nome == 'Joana'


def test_autocomplete_responsaveis(auth_client, app, db):
    with app.app_context():
        db.session.add_all([
            Responsavel(nome='Joana Silva', cpf='529.982.247-25', parentesco='mae'),
            Responsavel(nome='Maria Souza', parentesco='tia'),
            Responsavel(nome='Outro Nome'),
        ])
        db.session.commit()

    r = auth_client.get('/pacientes/responsaveis/buscar?q=joana')
    assert r.status_code == 200
    rows = json.loads(r.data)
    assert len(rows) == 1
    assert rows[0]['nome'] == 'Joana Silva'

    # busca por CPF exato
    r = auth_client.get('/pacientes/responsaveis/buscar?q=529.982.247-25')
    rows = json.loads(r.data)
    assert len(rows) == 1


def test_migracao_responsavel_string_para_tabela(app, paciente_factory, db):
    """A funcao migrar_responsavel_string_para_tabela popula a tabela a partir do campo legado."""
    from controllers.seed_data import migrar_responsavel_string_para_tabela

    paciente_factory(nome='P1', responsavel='Carlos')
    paciente_factory(nome='P2', responsavel='Carlos')  # mesmo responsavel string
    paciente_factory(nome='P3', responsavel='Outra Pessoa')
    paciente_factory(nome='P4', responsavel='')

    with app.app_context():
        migrar_responsavel_string_para_tabela()
        assert Responsavel.query.count() == 2  # Carlos (1x) + Outra Pessoa
        p1 = Paciente.query.filter_by(nome='P1').first()
        p2 = Paciente.query.filter_by(nome='P2').first()
        p4 = Paciente.query.filter_by(nome='P4').first()
        assert p1.id_responsavel == p2.id_responsavel  # deduplicou
        assert p4.id_responsavel is None  # vazio nao migra
