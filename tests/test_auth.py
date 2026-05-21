"""Testes de autenticacao + auditoria de login."""

from models.models import LogAuditoria


def test_login_sucesso_redireciona(client, db):
    r = client.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'},
                    follow_redirects=False)
    assert r.status_code in (302, 303)
    assert '/home' in r.headers.get('Location', '')


def test_login_falho_loga_evento(client, app, db):
    client.post('/login', data={'email': 'admin@admin.com', 'senha': 'errada'})
    with app.app_context():
        log = LogAuditoria.query.filter_by(acao='LOGIN_FALHO').first()
        assert log is not None
        assert 'admin@admin.com' in (log.detalhes or '')


def test_login_sucesso_loga(client, app, db):
    client.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    with app.app_context():
        log = LogAuditoria.query.filter_by(acao='LOGIN').first()
        assert log is not None
        assert log.id_usuario is not None


def test_logoff_requer_post(auth_client):
    """GET no logoff deve falhar; POST deve funcionar."""
    r = auth_client.get('/logoff')
    assert r.status_code == 405  # Method Not Allowed
    r = auth_client.post('/logoff', follow_redirects=False)
    assert r.status_code in (302, 303)


def test_home_requer_login(client, db):
    r = client.get('/home', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'login' in r.headers.get('Location', '').lower()
