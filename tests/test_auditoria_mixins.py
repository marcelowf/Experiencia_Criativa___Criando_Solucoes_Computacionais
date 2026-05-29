"""Testes dos mixins Auditable + SoftDeletable e do auto-fill via event listeners."""

from datetime import datetime

from models.models import Paciente, Responsavel, Sintoma


def test_responsavel_tem_audit_cols_no_create(app, db):
    with app.app_context():
        r = Responsavel(nome='Joao')
        db.session.add(r)
        db.session.commit()
        assert r.criado_em is not None
        assert r.atualizado_em is not None
        assert r.removido_em is None
        assert r.ativo is True


def test_atualizado_em_muda_em_update(app, db):
    with app.app_context():
        r = Responsavel(nome='Antes')
        db.session.add(r)
        db.session.commit()
        antes = r.atualizado_em
        # forca onupdate
        r.nome = 'Depois'
        db.session.commit()
        assert r.atualizado_em > antes


def test_soft_delete_marca_inativo(app, db):
    with app.app_context():
        r = Responsavel(nome='Sumir')
        db.session.add(r)
        db.session.commit()
        assert r.ativo is True
        r.removido_em = datetime.utcnow()
        db.session.commit()
        assert r.ativo is False


def test_criado_por_id_preenchido_via_request(auth_client, app, db, admin):
    """Ao criar Paciente via HTTP autenticado, criado_por_id deve ser current_user.id."""
    with app.app_context():
        admin_id = admin.id

    auth_client.post(
        '/pacientes/novo',
        data={
            'nome': 'Audit Paciente',
            'cpf': '11144477735',
            'sexo': 'M',
            'data_nascimento': '2015-01-01',
            'consentimento': 'on',
        },
        follow_redirects=True,
    )

    with app.app_context():
        p = Paciente.query.filter_by(nome='Audit Paciente').first()
        assert p is not None
        assert p.criado_por_id == admin_id
        assert p.atualizado_por_id == admin_id


def test_atualizado_por_id_preenchido_em_update(auth_client, app, db, admin, paciente_factory):
    """Editar paciente por outro usuario muda atualizado_por_id."""
    p = paciente_factory(nome='Para Editar')
    with app.app_context():
        pid = p.id
        admin_id = admin.id

    # cria 2o admin e loga com ele
    from tests.test_usuarios import _criar_admin_extra

    with app.app_context():
        admin2 = _criar_admin_extra()
        admin2_id = admin2.id

    client2 = app.test_client()
    client2.post('/login', data={'email': 'admin2@admin.com', 'senha': 'admin1234'})
    client2.post(
        f'/pacientes/{pid}/editar',
        data={
            'nome': 'Editado',
            'cpf': '111.444.777-35',
            'sexo': 'M',
            'data_nascimento': '2015-01-01',
        },
        follow_redirects=True,
    )

    with app.app_context():
        p2 = Paciente.query.get(pid)
        assert p2.nome == 'Editado'
        assert p2.atualizado_por_id == admin2_id
        # criado_por_id NAO deve mudar (so updated)
        assert p2.criado_por_id != admin2_id or p2.criado_por_id == admin_id


def test_sem_request_context_nao_falha(app, db):
    """Criar registros via codigo (sem request) nao deve quebrar — campos ficam NULL."""
    with app.app_context():
        s = Sintoma(chave='teste_audit', label='Teste', peso_masculino=0.1, peso_feminino=0.1)
        db.session.add(s)
        db.session.commit()
        assert s.criado_em is not None
        assert s.criado_por_id is None  # sem current_user


def test_versao_pesos_renomeada(app, db):
    """VersaoPesos agora tem criado_em/criado_por_id (renomeados de criada_*)."""
    from models.models import VersaoPesos

    with app.app_context():
        v = VersaoPesos.query.first()
        assert v is not None
        assert hasattr(v, 'criado_em')
        assert hasattr(v, 'criado_por')
        assert not hasattr(v, 'criada_em')
