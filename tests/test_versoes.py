"""Testes do versionamento de pesos."""

from models.models import (Sintoma, VersaoPesos, SintomaPesoVersao, Avaliacao,
                           db as _db)
from controllers.versoes_pesos import versao_ativa


def test_seed_inicial_cria_v1(db, app):
    with app.app_context():
        v = versao_ativa()
        assert v is not None
        assert v.nome == 'V1'
        assert v.ativa is True
        # 12 sintomas seed -> 12 entradas em SintomaPesoVersao
        assert SintomaPesoVersao.query.filter_by(id_versao=v.id).count() == 12


def test_avaliacao_grava_versao_ativa(auth_client, paciente_factory, app, db):
    p = paciente_factory(sexo='M')
    with app.app_context():
        sintomas = Sintoma.query.filter_by(ativo=True).all()
        data = {'id_paciente': p.id}
        for s in sintomas:
            data[f'sintoma_{s.id}'] = 'on'
    auth_client.post('/avaliacoes/nova', data=data, follow_redirects=False)
    with app.app_context():
        av = Avaliacao.query.filter_by(id_paciente=p.id).first()
        v = versao_ativa()
        assert av.id_versao_pesos == v.id


def test_alteracao_peso_cria_v2(auth_client, app, db):
    """Editar peso de um sintoma deve criar nova versão (V2) e desativar V1."""
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
    auth_client.post(f'/sintomas/{sid}/editar', data={
        'label': 'Agressividade',
        'peso_masculino': '0.05',  # antes era 0.01
        'peso_feminino': '0.02',
        'ativo': 'on',
        'notas_versao': 'Recalibracao por estudo X',
    }, follow_redirects=True)
    with app.app_context():
        ativa = versao_ativa()
        assert ativa.nome == 'V2'
        assert ativa.notas == 'Recalibracao por estudo X'
        # V1 deve continuar existindo, mas inativa
        v1 = VersaoPesos.query.filter_by(nome='V1').first()
        assert v1.ativa is False
        # Snapshot V2 deve refletir peso novo (0.05)
        snap = (SintomaPesoVersao.query
                .filter_by(id_versao=ativa.id, id_sintoma=sid).first())
        assert snap.peso_masculino == 0.05
        # Snapshot V1 deve manter o peso original (0.01)
        snap_v1 = (SintomaPesoVersao.query
                   .filter_by(id_versao=v1.id, id_sintoma=sid).first())
        assert snap_v1.peso_masculino == 0.01


def test_alteracao_sem_notas_eh_rejeitada(auth_client, app, db):
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
        peso_antes = s.peso_masculino
    r = auth_client.post(f'/sintomas/{sid}/editar', data={
        'label': 'Agressividade',
        'peso_masculino': '0.99',
        'peso_feminino': '0.02',
        'ativo': 'on',
        # sem notas_versao
    })
    assert r.status_code == 200  # form re-renderizado, nao redirecionou
    with app.app_context():
        s = Sintoma.query.get(sid)
        # peso NAO foi alterado (rollback)
        assert s.peso_masculino == peso_antes
        # so existe V1 ainda
        assert VersaoPesos.query.count() == 1


def test_novo_sintoma_cria_v2(auth_client, app, db):
    """Adicionar um sintoma deve criar nova versão (V2) e snapshotar o novo sintoma."""
    auth_client.post('/sintomas/novo', data={
        'chave': 'sintoma_teste',
        'label': 'Sintoma Teste',
        'peso_masculino': '0.10',
        'peso_feminino': '0.20',
        'ativo': 'on',
    }, follow_redirects=True)
    with app.app_context():
        ativa = versao_ativa()
        assert ativa.nome == 'V2'
        # V1 continua existindo, inativa
        v1 = VersaoPesos.query.filter_by(nome='V1').first()
        assert v1.ativa is False
        # V2 inclui o novo sintoma (13 = 12 seed + 1 novo)
        assert SintomaPesoVersao.query.filter_by(id_versao=ativa.id).count() == 13
        # V1 NAO foi corrompida: continua com 12 sintomas
        assert SintomaPesoVersao.query.filter_by(id_versao=v1.id).count() == 12
        s = Sintoma.query.filter_by(chave='sintoma_teste').first()
        snap = (SintomaPesoVersao.query
                .filter_by(id_versao=ativa.id, id_sintoma=s.id).first())
        assert snap.peso_masculino == 0.10


def test_toggle_ativo_nao_cria_versao(auth_client, app, db):
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
    auth_client.post(f'/sintomas/{sid}/toggle', follow_redirects=True)
    with app.app_context():
        assert VersaoPesos.query.count() == 1  # ainda so V1


def test_alteracao_so_label_nao_cria_versao(auth_client, app, db):
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
        peso_m = s.peso_masculino
        peso_f = s.peso_feminino
    auth_client.post(f'/sintomas/{sid}/editar', data={
        'label': 'Novo Label',
        'peso_masculino': str(peso_m),
        'peso_feminino': str(peso_f),
        'ativo': 'on',
    }, follow_redirects=True)
    with app.app_context():
        # pesos iguais -> sem nova versao
        assert VersaoPesos.query.count() == 1


def test_pagina_versoes_lista_historico(auth_client):
    r = auth_client.get('/sintomas/versoes')
    assert r.status_code == 200
    assert b'V1' in r.data


def test_pagina_versoes_proibe_padrao(auth_client_padrao):
    r = auth_client_padrao.get('/sintomas/versoes')
    assert r.status_code == 403
