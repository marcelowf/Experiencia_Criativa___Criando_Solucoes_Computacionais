"""Testes do login federado via Google.

A lógica crítica (só entra quem já está cadastrado + e-mail verificado) está
isolada em `resolver_usuario_google`, testada aqui sem depender da rede/OAuth.
As rotas devem ficar 404 enquanto o recurso estiver desligado (sem credenciais).
"""

from controllers.auth_controller import resolver_usuario_google


def test_resolver_usuario_existente_e_verificado(app, db, admin):
    with app.app_context():
        usuario, erro = resolver_usuario_google('admin@admin.com', True)
        assert erro is None
        assert usuario is not None
        assert usuario.email == 'admin@admin.com'


def test_resolver_normaliza_caixa_e_espacos(app, db, admin):
    with app.app_context():
        usuario, erro = resolver_usuario_google('  ADMIN@Admin.COM  ', True)
        assert erro is None
        assert usuario is not None


def test_resolver_email_nao_cadastrado_recusa(app, db):
    with app.app_context():
        usuario, erro = resolver_usuario_google('desconhecido@gmail.com', True)
        assert usuario is None
        assert 'não está cadastrado' in erro


def test_resolver_email_nao_verificado_recusa(app, db, admin):
    """Mesmo cadastrado, e-mail não verificado pelo Google é rejeitado."""
    with app.app_context():
        usuario, erro = resolver_usuario_google('admin@admin.com', False)
        assert usuario is None
        assert 'verificado' in erro


def test_rota_google_desabilitada_404(client):
    """Sem credenciais configuradas, o recurso fica desligado."""
    assert client.get('/login/google').status_code == 404
    assert client.get('/login/google/callback').status_code == 404


def test_login_sem_botao_google_quando_desabilitado(client):
    r = client.get('/login')
    assert r.status_code == 200
    assert b'Entrar com Google' not in r.data
