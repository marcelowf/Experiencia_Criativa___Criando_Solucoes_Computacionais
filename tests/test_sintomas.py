"""Testes do CRUD de sintomas (admin-only)."""

from models.models import Sintoma


def test_lista_sintomas_admin(auth_client):
    r = auth_client.get('/sintomas/')
    assert r.status_code == 200
    assert 'Deficiência Intelectual' in r.data.decode('utf-8')


def test_lista_sintomas_proibe_padrao(auth_client_padrao):
    r = auth_client_padrao.get('/sintomas/')
    assert r.status_code == 403


def test_seed_inicial_tem_12_sintomas(db, app):
    with app.app_context():
        assert Sintoma.query.count() == 12


def test_toggle_sintoma(auth_client, app, db):
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
        ativo_antes = s.ativo
    auth_client.post(f'/sintomas/{sid}/toggle', follow_redirects=True)
    with app.app_context():
        s = Sintoma.query.get(sid)
        assert s.ativo == (not ativo_antes)


def test_editar_sintoma_persiste(auth_client, app, db):
    """Edicao apenas de label (sem mudar peso) nao exige notas."""
    with app.app_context():
        s = Sintoma.query.filter_by(chave='agressividade').first()
        sid = s.id
        peso_m, peso_f = s.peso_masculino, s.peso_feminino
    auth_client.post(
        f'/sintomas/{sid}/editar',
        data={
            'label': 'Agressividade Atualizada',
            'peso_masculino': str(peso_m),
            'peso_feminino': str(peso_f),
            'ativo': 'on',
        },
        follow_redirects=True,
    )
    with app.app_context():
        s = Sintoma.query.filter_by(id=sid).first()
        assert s.label == 'Agressividade Atualizada'
