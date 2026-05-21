"""Testes da tela de relatorios e exportacoes."""

import json


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
