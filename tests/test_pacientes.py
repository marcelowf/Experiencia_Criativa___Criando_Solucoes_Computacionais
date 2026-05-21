"""Testes do CRUD de pacientes (com foco em CPF e ownership)."""

from controllers.paciente_controller import _cpf_digitos_validos, _normalizar_cpf
from models.models import Paciente


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
