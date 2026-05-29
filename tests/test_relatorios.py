"""Testes da tela de relatorios e exportacoes."""

import json
from datetime import date

from controllers.versoes_pesos import versao_ativa
from models.models import Avaliacao, VersaoPesos, db


def _criar_avaliacao(paciente, id_versao, score=0.3, recomendacao='NÃO ENCAMINHAR'):
    av = Avaliacao(
        id_paciente=paciente.id,
        data=date.today(),
        score=score,
        recomendacao=recomendacao,
        id_usuario=paciente.id_usuario,
        id_versao_pesos=id_versao,
    )
    db.session.add(av)
    db.session.commit()
    return av


def test_relatorios_index_renderiza(auth_client):
    r = auth_client.get('/relatorios/')
    assert r.status_code == 200
    assert b'Relat' in r.data  # "Relatórios"


def test_api_dados_retorna_json_vazio(auth_client):
    r = auth_client.get('/relatorios/api/dados')
    assert r.status_code == 200
    payload = json.loads(r.data)
    assert 'kpis' in payload
    assert payload['kpis']['total'] == 0


def test_export_pdf_retorna_pdf(auth_client):
    r = auth_client.get('/relatorios/export/pdf')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data[:4] == b'%PDF'


def test_export_xlsx_retorna_xlsx(auth_client):
    r = auth_client.get('/relatorios/export/xlsx')
    assert r.status_code == 200
    assert 'spreadsheet' in r.mimetype
    # XLSX e um zip; comeca com PK
    assert r.data[:2] == b'PK'


def test_filtro_versao_pesos_isola_resultados(auth_client, paciente_factory, app, db):
    p = paciente_factory(sexo='M')
    with app.app_context():
        v1 = versao_ativa()
        v2 = VersaoPesos(nome='V2', ativa=False)
        db.session.add(v2)
        db.session.commit()
        v1_id, v2_id = v1.id, v2.id
        _criar_avaliacao(p, v1_id, score=0.2, recomendacao='NÃO ENCAMINHAR')
        _criar_avaliacao(p, v1_id, score=0.3, recomendacao='NÃO ENCAMINHAR')
        _criar_avaliacao(p, v2_id, score=0.8, recomendacao='ENCAMINHAR')

    r = auth_client.get(f'/relatorios/api/dados?id_versao_pesos={v1_id}')
    assert r.status_code == 200
    assert json.loads(r.data)['kpis']['total'] == 2

    r = auth_client.get(f'/relatorios/api/dados?id_versao_pesos={v2_id}')
    assert json.loads(r.data)['kpis']['total'] == 1


def test_comparativo_renderiza_lado_a_lado(auth_client, paciente_factory, app, db):
    p = paciente_factory(sexo='M')
    with app.app_context():
        v1 = versao_ativa()
        v2 = VersaoPesos(nome='V2', ativa=False)
        db.session.add(v2)
        db.session.commit()
        v1_id, v2_id = v1.id, v2.id
        _criar_avaliacao(p, v1_id, score=0.2, recomendacao='NÃO ENCAMINHAR')
        _criar_avaliacao(p, v2_id, score=0.8, recomendacao='ENCAMINHAR')
        _criar_avaliacao(p, v2_id, score=0.9, recomendacao='ENCAMINHAR')

    r = auth_client.get(f'/relatorios/comparativo?versao_a={v1_id}&versao_b={v2_id}')
    assert r.status_code == 200
    body = r.data.decode('utf-8')
    # Ambos os blocos devem aparecer
    assert 'Versão A' in body
    assert 'Versão B' in body


def test_comparativo_sem_selecao(auth_client):
    r = auth_client.get('/relatorios/comparativo')
    assert r.status_code == 200
    assert 'Selecione duas vers' in r.data.decode('utf-8')
