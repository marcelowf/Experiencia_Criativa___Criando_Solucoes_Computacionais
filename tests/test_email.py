"""Testes de configuracao + disparo de e-mail (SMTP mockado)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from models.models import (
    Avaliacao,
    EmailConfig,
    LogAuditoria,
    QrCadastroToken,
    Responsavel,
    db,
)

# ---------- helpers ----------


def _criar_config(senha_plain='senha-de-app-1234', ativo=True):
    """Cria uma EmailConfig (assume um app_context ativo, fornecido pela fixture db)."""
    from controllers.email_service import cifrar_senha

    c = EmailConfig(
        remetente_email='envio@gmail.com',
        remetente_nome='Triagem SXF',
        senha_app_cifrada=cifrar_senha(senha_plain),
        ativo=ativo,
    )
    db.session.add(c)
    db.session.commit()
    return c


# ---------- cripto ----------


def test_cifrar_decifrar_roundtrip(app):
    from controllers.email_service import cifrar_senha, decifrar_senha

    with app.app_context():
        cifra = cifrar_senha('minha-senha-secreta')
        assert cifra != 'minha-senha-secreta'
        assert decifrar_senha(cifra) == 'minha-senha-secreta'


def test_decifrar_token_invalido_levanta(app):
    from controllers.email_service import SenhaAppInvalidaError, decifrar_senha

    with app.app_context():
        with pytest.raises(SenhaAppInvalidaError):
            decifrar_senha('token-invalido-qualquer')


# ---------- config controller ----------


def test_salvar_config_admin(auth_client, app):
    r = auth_client.post(
        '/config/email/',
        data={
            'remetente_email': 'envio@gmail.com',
            'remetente_nome': 'Triagem SXF',
            'senha_app': 'abcd efgh ijkl mnop',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        c = EmailConfig.query.first()
        assert c is not None
        assert c.remetente_email == 'envio@gmail.com'
        # senha guardada cifrada (nao em texto plano)
        assert 'abcd efgh' not in c.senha_app_cifrada
        from controllers.email_service import decifrar_senha

        assert decifrar_senha(c.senha_app_cifrada) == 'abcd efgh ijkl mnop'
        # auditoria sem expor senha
        log = LogAuditoria.query.filter_by(entidade='email_config').first()
        assert log is not None
        assert 'abcd' not in (log.detalhes or '')


def test_config_nao_revela_senha(auth_client, app):
    _criar_config(senha_plain='super-secreta-xyz')
    r = auth_client.get('/config/email/')
    assert 'super-secreta-xyz' not in r.data.decode('utf-8')


def test_config_requer_admin(auth_client_padrao):
    r = auth_client_padrao.get('/config/email/')
    assert r.status_code == 403


def test_senha_em_branco_mantem_atual(auth_client, app):
    _criar_config(senha_plain='original-123')
    cifra_antes = EmailConfig.query.first().senha_app_cifrada

    auth_client.post(
        '/config/email/',
        data={
            'remetente_email': 'novo@gmail.com',
            'remetente_nome': 'Novo Nome',
            'senha_app': '',  # em branco
        },
        follow_redirects=True,
    )

    c = EmailConfig.query.first()
    assert c.remetente_email == 'novo@gmail.com'
    assert c.senha_app_cifrada == cifra_antes  # senha preservada


def test_desativar(auth_client, app):
    _criar_config()
    auth_client.post('/config/email/desativar', follow_redirects=True)
    assert EmailConfig.query.first().ativo is False


# ---------- service ----------


def test_email_configurado_flag(db):
    from controllers.email_service import email_configurado

    assert email_configurado() is False
    _criar_config(ativo=True)
    assert email_configurado() is True
    EmailConfig.query.first().ativo = False
    db.session.commit()
    assert email_configurado() is False


def test_enviar_sem_config_levanta_erro(db):
    from controllers.email_service import EmailNaoConfiguradoError, enviar_email

    with pytest.raises(EmailNaoConfiguradoError):
        enviar_email('x@y.com', 'Assunto', '<p>oi</p>')


def test_enviar_email_chama_smtp(db):
    from controllers import email_service

    _criar_config(senha_plain='app-pass-123')
    with patch.object(email_service.smtplib, 'SMTP') as mock_smtp:
        instancia = MagicMock()
        mock_smtp.return_value.__enter__.return_value = instancia
        email_service.enviar_email('destino@x.com', 'Assunto', '<p>corpo</p>')
        instancia.starttls.assert_called_once()
        instancia.login.assert_called_once_with('envio@gmail.com', 'app-pass-123')
        instancia.send_message.assert_called_once()


# ---------- integracao: reset de senha ----------


def test_reset_envia_email_quando_configurado(client, app):
    _criar_config()
    from controllers import reset_senha_controller

    with patch.object(reset_senha_controller, 'enviar_email') as mock_env:
        r = client.post('/esqueci-senha', data={'email': 'admin@admin.com'}, follow_redirects=True)
        assert r.status_code == 200
        mock_env.assert_called_once()
        # link NAO deve aparecer no flash quando enviado por email
        assert '/reset/' not in r.data.decode('utf-8')


def test_reset_fallback_flash_sem_config(client, app):
    # sem EmailConfig -> link no flash (modo dev)
    r = client.post('/esqueci-senha', data={'email': 'admin@admin.com'}, follow_redirects=True)
    assert '/reset/' in r.data.decode('utf-8')


# ---------- integracao: QR ----------


def test_qr_enviar_email(auth_client, app):
    _criar_config()
    auth_client.post('/pacientes/qr/gerar')
    qr_id = QrCadastroToken.query.first().id

    from controllers import qr_cadastro_controller

    with patch.object(qr_cadastro_controller, 'enviar_email') as mock_env:
        r = auth_client.post(
            f'/pacientes/qr/{qr_id}/enviar-email',
            data={'email_destino': 'paciente@x.com'},
            follow_redirects=True,
        )
        assert r.status_code == 200
        mock_env.assert_called_once()
        args = mock_env.call_args[0]
        assert args[0] == 'paciente@x.com'
    assert (
        LogAuditoria.query.filter_by(acao='EMAIL_ENVIADO', entidade='qr_cadastro_token').count()
        == 1
    )


# ---------- integracao: resultado de exame ----------


def _criar_avaliacao_com_responsavel(admin, email_resp='mae@x.com'):
    """Assume app_context ativo (fixture db via auth_client)."""
    from controllers.versoes_pesos import versao_ativa
    from models.models import Paciente

    resp = Responsavel(nome='Mae', email=email_resp)
    db.session.add(resp)
    db.session.flush()
    p = Paciente(
        nome='Filho',
        cpf='111.444.777-35',
        sexo='M',
        data_nascimento=date(2015, 1, 1),
        id_responsavel=resp.id,
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.flush()
    av = Avaliacao(
        id_paciente=p.id,
        data=date.today(),
        score=0.5,
        recomendacao='ENCAMINHAR',
        id_usuario=admin.id,
        id_versao_pesos=versao_ativa().id,
    )
    db.session.add(av)
    db.session.commit()
    return av.id


def test_resultado_sugere_email_do_responsavel(auth_client, app, admin):
    av_id = _criar_avaliacao_com_responsavel(admin, email_resp='mae@exemplo.com')
    _criar_config()
    r = auth_client.get(f'/avaliacoes/{av_id}/resultado')
    assert 'mae@exemplo.com' in r.data.decode('utf-8')


def test_resultado_enviar_email_anexa_pdf(auth_client, app, admin):
    av_id = _criar_avaliacao_com_responsavel(admin)
    _criar_config()

    from controllers import avaliacao_controller

    with (
        patch.object(avaliacao_controller, 'enviar_email') as mock_env,
        patch.object(
            avaliacao_controller, '_resultado_pdf_bytes', return_value=b'%PDF-fake'
        ) as mock_pdf,
    ):
        r = auth_client.post(
            f'/avaliacoes/{av_id}/enviar-email',
            data={'email_destino': 'destino@x.com'},
            follow_redirects=True,
        )
        assert r.status_code == 200
        mock_pdf.assert_called_once()
        mock_env.assert_called_once()
        kwargs = mock_env.call_args.kwargs
        anexos = kwargs.get('anexos') or mock_env.call_args[0][3]
        assert anexos[0][2] == 'application/pdf'
    assert LogAuditoria.query.filter_by(acao='EMAIL_ENVIADO', entidade='avaliacao').count() == 1


def test_testar_envio(auth_client, app):
    _criar_config()
    from controllers import email_config_controller

    with patch.object(email_config_controller, 'enviar_email') as mock_env:
        r = auth_client.post('/config/email/testar', follow_redirects=True)
        assert r.status_code == 200
        mock_env.assert_called_once()
        # destinatario do teste e o proprio admin
        assert mock_env.call_args[0][0] == 'admin@admin.com'


# ---------- email_destino: cascata paciente.email -> responsavel.email -> '' ----------


def test_email_destino_paciente_proprio(db, admin):
    from controllers.email_service import email_destino
    from models.models import Paciente

    p = Paciente(
        nome='Adulto',
        cpf='111.444.777-35',
        sexo='M',
        data_nascimento=date(1990, 1, 1),
        email='adulto@exemplo.com',
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.commit()
    assert email_destino(p) == 'adulto@exemplo.com'


def test_email_destino_fallback_responsavel(db, admin):
    from controllers.email_service import email_destino
    from models.models import Paciente

    resp = Responsavel(nome='Mae', email='mae@exemplo.com')
    db.session.add(resp)
    db.session.flush()
    p = Paciente(
        nome='Crianca',
        cpf='111.444.777-35',
        sexo='F',
        data_nascimento=date(2018, 1, 1),
        id_responsavel=resp.id,
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.commit()
    assert email_destino(p) == 'mae@exemplo.com'


def test_email_destino_paciente_prevalece_sobre_responsavel(db, admin):
    from controllers.email_service import email_destino
    from models.models import Paciente

    resp = Responsavel(nome='Mae', email='mae@x.com')
    db.session.add(resp)
    db.session.flush()
    p = Paciente(
        nome='Adolescente',
        cpf='111.444.777-35',
        sexo='M',
        data_nascimento=date(2010, 1, 1),
        email='ado@x.com',
        id_responsavel=resp.id,
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.commit()
    assert email_destino(p) == 'ado@x.com'


def test_email_destino_vazio_quando_ninguem_tem(db, admin):
    from controllers.email_service import email_destino
    from models.models import Paciente

    p = Paciente(
        nome='Sem Email',
        cpf='111.444.777-35',
        sexo='M',
        data_nascimento=date(1990, 1, 1),
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.commit()
    assert email_destino(p) == ''


def test_cadastro_paciente_grava_email(auth_client, app):
    from models.models import Paciente

    auth_client.post(
        '/pacientes/novo',
        data={
            'nome': 'Com Email',
            'cpf': '11144477735',
            'sexo': 'M',
            'data_nascimento': '1990-01-01',
            'consentimento': 'on',
            'email': 'paciente@exemplo.com',
        },
        follow_redirects=True,
    )
    p = Paciente.query.filter_by(nome='Com Email').first()
    assert p is not None
    assert p.email == 'paciente@exemplo.com'


def test_resultado_sugere_email_do_paciente_quando_existe(auth_client, app, admin):
    """Quando paciente tem e-mail proprio, ele tem prioridade sobre o do responsavel."""
    from controllers.versoes_pesos import versao_ativa
    from models.models import Avaliacao as Av
    from models.models import Paciente

    resp = Responsavel(nome='Mae', email='mae@x.com')
    db.session.add(resp)
    db.session.flush()
    p = Paciente(
        nome='Pac',
        cpf='111.444.777-35',
        sexo='M',
        data_nascimento=date(2010, 1, 1),
        email='paciente@x.com',
        id_responsavel=resp.id,
        id_usuario=admin.id,
    )
    db.session.add(p)
    db.session.flush()
    av = Av(
        id_paciente=p.id,
        data=date.today(),
        score=0.5,
        recomendacao='ENCAMINHAR',
        id_usuario=admin.id,
        id_versao_pesos=versao_ativa().id,
    )
    db.session.add(av)
    db.session.commit()

    _criar_config()
    r = auth_client.get(f'/avaliacoes/{av.id}/resultado')
    body = r.data.decode('utf-8')
    assert 'paciente@x.com' in body
    assert 'mae@x.com' not in body  # não aparece pq paciente.email prevalece
