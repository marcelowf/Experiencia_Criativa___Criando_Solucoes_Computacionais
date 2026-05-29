"""Testes de gestao de usuarios + protecao do ultimo admin."""

from models.models import UserPreference, Usuario, db


def _criar_admin_extra(nome='Admin Dois', email='admin2@admin.com', senha='admin1234'):
    u = Usuario(nome=nome, email=email, perfil='admin')
    u.set_senha(senha)
    db.session.add(u)
    db.session.flush()
    db.session.add(UserPreference(id_usuario=u.id))
    db.session.commit()
    return u


def test_ultimo_admin_helper(app, admin):
    from controllers.usuario_controller import _eh_ultimo_admin, _total_admins

    with app.app_context():
        admin_db = Usuario.query.filter_by(email='admin@admin.com').first()
        assert _total_admins() == 1
        assert _eh_ultimo_admin(admin_db) is True
        _criar_admin_extra()
        admin_db = Usuario.query.filter_by(email='admin@admin.com').first()
        assert _total_admins() == 2
        assert _eh_ultimo_admin(admin_db) is False


def test_editar_ultimo_admin_nao_rebaixa(auth_client, app, admin):
    with app.app_context():
        admin_id = admin.id

    r = auth_client.post(
        f'/usuarios/{admin_id}/editar',
        data={'nome': 'Admin', 'perfil': 'padrao'},
        follow_redirects=False,
    )
    # agora retorna 200 (render_template no erro) em vez de redirect
    assert r.status_code in (200, 302, 303)
    with app.app_context():
        u = Usuario.query.get(admin_id)
        assert u.perfil == 'admin'


def test_editar_rebaixa_admin_quando_ha_outro(auth_client, app, admin):
    with app.app_context():
        admin2 = _criar_admin_extra()
        admin2_id = admin2.id

    r = auth_client.post(
        f'/usuarios/{admin2_id}/editar',
        data={'nome': 'Admin Dois', 'perfil': 'padrao'},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    with app.app_context():
        u = Usuario.query.get(admin2_id)
        assert u.perfil == 'padrao'


def test_remover_admin_quando_ha_outro(auth_client, app, admin):
    with app.app_context():
        admin2 = _criar_admin_extra()
        admin2_id = admin2.id

    r = auth_client.post(f'/usuarios/{admin2_id}/remover', follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        assert Usuario.query.get(admin2_id) is None
        assert Usuario.query.filter_by(perfil='admin').count() == 1


def test_self_delete_bloqueado(auth_client, app, admin):
    with app.app_context():
        admin_id = admin.id
    r = auth_client.post(f'/usuarios/{admin_id}/remover', follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        assert Usuario.query.get(admin_id) is not None
