"""Testes dos dados socioeconômicos e relatório."""

from datetime import date
from models.models import db, Paciente, DadosSocioeconomicos


def _criar_paciente(admin, cpf='111.444.777-35', nome='Paciente Socio'):
    p = Paciente(nome=nome, cpf=cpf, sexo='F',
                 data_nascimento=date(1990, 1, 1),
                 id_usuario=admin.id)
    db.session.add(p)
    db.session.commit()
    return p


# ---- coleta no form interno ----

def test_cadastro_salva_dados_socioeconomicos(auth_client, app, admin):
    auth_client.post('/pacientes/novo', data={
        'nome': 'Com SE', 'cpf': '11144477735', 'sexo': 'F',
        'data_nascimento': '1990-01-01', 'consentimento': 'on',
        'se_renda_faixa': 'sem_renda',
        'se_profissao': 'Agricultora',
        'se_escolaridade': 'fundamental',
        'se_num_dependentes': '3',
    }, follow_redirects=True)
    p = Paciente.query.filter_by(nome='Com SE').first()
    assert p is not None
    se = p.dados_socioeconomicos
    assert se is not None
    assert se.renda_faixa == 'sem_renda'
    assert se.profissao == 'Agricultora'
    assert se.escolaridade == 'fundamental'
    assert se.num_dependentes == 3
    assert se.baixa_renda is True


def test_cadastro_sem_se_nao_cria_registro(auth_client, app):
    auth_client.post('/pacientes/novo', data={
        'nome': 'Sem SE', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '1990-01-01', 'consentimento': 'on',
        # sem campos se_*
    }, follow_redirects=True)
    p = Paciente.query.filter_by(nome='Sem SE').first()
    assert p is not None
    assert p.dados_socioeconomicos is None


def test_editar_atualiza_dados_socioeconomicos(auth_client, app, admin):
    p = _criar_paciente(admin)
    se = DadosSocioeconomicos(id_paciente=p.id, renda_faixa='ate_1sm')
    db.session.add(se)
    db.session.commit()

    auth_client.post(f'/pacientes/{p.id}/editar', data={
        'nome': p.nome, 'cpf': p.cpf, 'sexo': p.sexo,
        'data_nascimento': p.data_nascimento.isoformat(),
        'se_renda_faixa': '1_3sm',
        'se_profissao': 'Costureira',
        'se_escolaridade': 'medio',
        'se_num_dependentes': '2',
    }, follow_redirects=True)
    se = DadosSocioeconomicos.query.filter_by(id_paciente=p.id).first()
    assert se.renda_faixa == '1_3sm'
    assert se.profissao == 'Costureira'
    assert se.num_dependentes == 2
    assert se.baixa_renda is False


def test_baixa_renda_property():
    from models.models import DadosSocioeconomicos
    for faixa in ('sem_renda', 'ate_1sm'):
        se = DadosSocioeconomicos(renda_faixa=faixa)
        assert se.baixa_renda is True
    for faixa in ('1_3sm', '3_5sm', 'acima_5sm'):
        se = DadosSocioeconomicos(renda_faixa=faixa)
        assert se.baixa_renda is False


# ---- relatório ----

def test_relatorio_socioeconomico_renderiza(auth_client):
    r = auth_client.get('/relatorios/socioeconomico')
    assert r.status_code == 200
    assert 'Perfil Socioecon' in r.data.decode('utf-8')


def test_relatorio_socioeconomico_proibe_padrao(auth_client_padrao):
    r = auth_client_padrao.get('/relatorios/socioeconomico')
    assert r.status_code == 403


def test_relatorio_mostra_cobertura(auth_client, app, admin):
    # 2 pacientes, 1 com dados
    p1 = _criar_paciente(admin, cpf='111.444.777-35', nome='P1')
    p2 = _criar_paciente(admin, cpf='529.982.247-25', nome='P2')
    db.session.add(DadosSocioeconomicos(id_paciente=p1.id, renda_faixa='sem_renda'))
    db.session.commit()

    r = auth_client.get('/relatorios/socioeconomico')
    body = r.data.decode('utf-8')
    # 1 de 2 = 50%
    assert '50' in body or '50.0' in body


def test_relatorio_lista_baixa_renda(auth_client, app, admin):
    p = _criar_paciente(admin, nome='Pobre')
    db.session.add(DadosSocioeconomicos(id_paciente=p.id,
                                        renda_faixa='sem_renda',
                                        profissao='Desempregada'))
    db.session.commit()
    r = auth_client.get('/relatorios/socioeconomico')
    body = r.data.decode('utf-8')
    assert 'Pobre' in body
    assert 'Desempregada' in body
