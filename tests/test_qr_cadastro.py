"""Testes do fluxo de QR Code para auto-cadastro de paciente."""

from datetime import datetime, timedelta

from models.models import db, Paciente, QrCadastroToken, LogAuditoria, Usuario


def _gerar_qr(client):
    """Submete POST em /pacientes/qr/gerar e retorna o QR criado."""
    client.post('/pacientes/qr/gerar', follow_redirects=False)
    return QrCadastroToken.query.order_by(QrCadastroToken.id.desc()).first()


# ---- Geração / Listagem ----

def test_gerar_qr_cria_token(auth_client, app, admin):
    with app.app_context():
        admin_id = admin.id
    auth_client.post('/pacientes/qr/gerar', follow_redirects=False)
    with app.app_context():
        qr = QrCadastroToken.query.first()
        assert qr is not None
        assert qr.id_usuario_emissor == admin_id
        assert qr.tipo == 'basico'
        assert qr.token and len(qr.token) >= 30
        # expira ~24h
        delta = qr.expira_em - datetime.utcnow()
        assert timedelta(hours=23) < delta <= timedelta(hours=24)


def test_qr_imagem_retorna_png(auth_client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        qr_id = QrCadastroToken.query.first().id
    r = auth_client.get(f'/pacientes/qr/{qr_id}/imagem.png')
    assert r.status_code == 200
    assert r.mimetype == 'image/png'
    assert r.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_padrao_ve_so_seus_qrs(app, admin, usuario_padrao):
    """Cria QRs como admin E como padrao usando clients distintos.

    O fixture auth_client/auth_client_padrao compartilham o mesmo client,
    entao o segundo login sobrescreve o primeiro. Aqui criamos dois clients.
    """
    c_admin = app.test_client()
    c_admin.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    c_admin.post('/pacientes/qr/gerar')

    c_padrao = app.test_client()
    c_padrao.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    c_padrao.post('/pacientes/qr/gerar')

    with app.app_context():
        qrs_padrao = QrCadastroToken.query.filter_by(id_usuario_emissor=usuario_padrao.id).all()
        qrs_admin = QrCadastroToken.query.filter_by(id_usuario_emissor=admin.id).all()
        assert len(qrs_padrao) == 1
        assert len(qrs_admin) == 1

    body = c_padrao.get('/pacientes/qr/').data.decode('utf-8')
    with app.app_context():
        for outro in QrCadastroToken.query.filter_by(id_usuario_emissor=admin.id).all():
            assert outro.token not in body


def test_admin_ve_todos_os_qrs(app, admin, usuario_padrao):
    c_padrao = app.test_client()
    c_padrao.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    c_padrao.post('/pacientes/qr/gerar')

    c_admin = app.test_client()
    c_admin.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    c_admin.post('/pacientes/qr/gerar')

    r = c_admin.get('/pacientes/qr/')
    assert r.status_code == 200
    with app.app_context():
        assert QrCadastroToken.query.count() == 2


# ---- Acesso publico ----

def test_publico_token_invalido_404(client):
    r = client.get('/publico/cadastro/token-que-nao-existe')
    assert r.status_code == 404


def test_publico_token_expirado_410(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        qr = QrCadastroToken.query.first()
        qr.expira_em = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        token = qr.token

    r = client.get(f'/publico/cadastro/{token}')
    assert r.status_code == 410
    assert 'expirado' in r.data.decode('utf-8').lower()


def test_publico_get_renderiza_form(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        token = QrCadastroToken.query.first().token

    r = client.get(f'/publico/cadastro/{token}')
    assert r.status_code == 200
    body = r.data.decode('utf-8')
    assert 'Cadastro do Paciente' in body
    assert 'name="cpf"' in body
    assert 'name="consentimento"' in body


def test_publico_post_cria_paciente_vinculado_ao_emissor(auth_client, client, app, admin):
    with app.app_context():
        admin_id = admin.id
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        qr_id = QrCadastroToken.query.first().id
        token = QrCadastroToken.query.first().token

    r = client.post(f'/publico/cadastro/{token}', data={
        'nome': 'Paciente Publico', 'cpf': '111.444.777-35', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
    })
    assert r.status_code == 200
    assert 'recebido' in r.data.decode('utf-8').lower()

    with app.app_context():
        p = Paciente.query.filter_by(nome='Paciente Publico').first()
        assert p is not None
        assert p.id_usuario == admin_id
        assert p.consentimento_dado_em is not None
        log = LogAuditoria.query.filter_by(acao='CREATE_VIA_QR',
                                            entidade='paciente').first()
        assert log is not None
        assert log.id_usuario == admin_id
        import json
        d = json.loads(log.detalhes)
        assert d['token_id'] == qr_id


def test_publico_cria_paciente_com_responsavel(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        token = QrCadastroToken.query.first().token

    r = client.post(f'/publico/cadastro/{token}', data={
        'nome': 'Crianca', 'cpf': '111.444.777-35', 'sexo': 'F',
        'data_nascimento': '2018-01-01', 'consentimento': 'on',
        'resp_nome': 'Mae Joana', 'resp_cpf': '52998224725',
        'resp_email': 'joana@example.com', 'resp_parentesco': 'mae',
    })
    assert r.status_code == 200
    with app.app_context():
        p = Paciente.query.filter_by(nome='Crianca').first()
        assert p is not None
        assert p.responsavel_obj is not None
        assert p.responsavel_obj.nome == 'Mae Joana'
        assert p.responsavel_obj.cpf == '529.982.247-25'


def test_publico_cpf_invalido_rejeita(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        token = QrCadastroToken.query.first().token

    r = client.post(f'/publico/cadastro/{token}', data={
        'nome': 'X', 'cpf': '111.111.111-11', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
    })
    body = r.data.decode('utf-8')
    assert 'CPF inválido' in body
    with app.app_context():
        assert Paciente.query.count() == 0


def test_publico_cpf_duplicado_rejeita(auth_client, client, paciente_factory, app):
    paciente_factory(nome='Existente', cpf='111.444.777-35')
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        token = QrCadastroToken.query.first().token

    r = client.post(f'/publico/cadastro/{token}', data={
        'nome': 'Duplicado', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
    })
    body = r.data.decode('utf-8')
    assert 'Já existe' in body


def test_publico_sem_consentimento_rejeita(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        token = QrCadastroToken.query.first().token

    r = client.post(f'/publico/cadastro/{token}', data={
        'nome': 'Sem Consent', 'cpf': '111.444.777-35', 'sexo': 'M',
        'data_nascimento': '2015-01-01',
    })
    body = r.data.decode('utf-8')
    assert 'consentimento' in body.lower()
    with app.app_context():
        assert Paciente.query.count() == 0


# ---- Revogacao ----

def test_revogar_invalida_link(auth_client, client, app):
    auth_client.post('/pacientes/qr/gerar')
    with app.app_context():
        qr = QrCadastroToken.query.first()
        token = qr.token
        qr_id = qr.id

    # ainda ativo
    assert client.get(f'/publico/cadastro/{token}').status_code == 200

    auth_client.post(f'/pacientes/qr/{qr_id}/revogar')

    r = client.get(f'/publico/cadastro/{token}')
    assert r.status_code == 410


def test_padrao_nao_pode_revogar_qr_de_outro(app, admin, usuario_padrao):
    c_admin = app.test_client()
    c_admin.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    c_admin.post('/pacientes/qr/gerar')
    with app.app_context():
        qr_id = QrCadastroToken.query.first().id

    c_padrao = app.test_client()
    c_padrao.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    r = c_padrao.post(f'/pacientes/qr/{qr_id}/revogar')
    assert r.status_code == 403
