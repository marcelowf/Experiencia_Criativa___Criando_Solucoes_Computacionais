"""Testes da anamnese (história clínica/familiar) — Q1..Q8.

A anamnese é CONTEXTO: persiste e exibe, mas não afeta o score.
"""

from models.models import Paciente, Anamnese


def _dados_base(**extra):
    d = {
        'nome': 'Paciente Anamnese', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
    }
    d.update(extra)
    return d


def test_cadastro_sem_anamnese_nao_cria_registro(auth_client, app, db):
    """Se nenhum campo de anamnese vier, não cria Anamnese."""
    auth_client.post('/pacientes/novo', data=_dados_base(), follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Paciente Anamnese').first()
        assert p is not None
        assert p.anamnese is None
        assert Anamnese.query.count() == 0


def test_cadastro_com_anamnese_persiste_todos_os_campos(auth_client, app, db):
    auth_client.post('/pacientes/novo', data=_dados_base(
        an_ja_fez_exame_dna='sim',
        an_resultado_exame='pre_mutacao',
        an_interesse_exame_pcr='nao',
        an_diagnostico_autismo='sim',
        an_tem_irmaos='nao',
        an_familia_neurodesenvolvimento='nao_sei',
        an_familia_menopausa_precoce='sim',
        an_familia_ataxia_tremores='nao',
    ), follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Paciente Anamnese').first()
        a = p.anamnese
        assert a is not None
        assert a.ja_fez_exame_dna is True
        assert a.resultado_exame == 'pre_mutacao'
        assert a.interesse_exame_pcr is False
        assert a.diagnostico_autismo is True
        assert a.tem_irmaos is False
        assert a.familia_neurodesenvolvimento == 'nao_sei'
        assert a.familia_menopausa_precoce == 'sim'
        assert a.familia_ataxia_tremores == 'nao'
        # labels de exibição
        assert a.resultado_exame_label.startswith('Pré-mutação')
        assert a.ja_fez_exame_dna_label == 'Sim'
        assert a.interesse_exame_pcr_label == 'Não'
        # menopausa precoce na família => suspeita de pré-mutação (FXPOI)
        assert a.sugestivo_pre_mutacao is True


def test_resultado_exame_invalido_e_ignorado(auth_client, app, db):
    auth_client.post('/pacientes/novo', data=_dados_base(
        an_resultado_exame='valor_qualquer',
    ), follow_redirects=True)
    with app.app_context():
        p = Paciente.query.filter_by(nome='Paciente Anamnese').first()
        # único campo era inválido -> vira None -> nada respondido -> sem registro
        assert p.anamnese is None


def test_editar_paciente_atualiza_anamnese(auth_client, paciente_factory, app, db):
    p = paciente_factory(nome='Edita Anamnese', sexo='F')
    with app.app_context():
        pid = p.id
    auth_client.post(f'/pacientes/{pid}/editar', data={
        'nome': 'Edita Anamnese', 'cpf': '11144477735', 'sexo': 'F',
        'data_nascimento': '2015-01-01',
        'an_familia_ataxia_tremores': 'sim',
    }, follow_redirects=True)
    with app.app_context():
        a = Paciente.query.get(pid).anamnese
        assert a is not None
        assert a.familia_ataxia_tremores == 'sim'
        # ataxia/tremores na família => FXTAS => suspeita de pré-mutação
        assert a.sugestivo_pre_mutacao is True


def test_sugestivo_pre_mutacao_falso_sem_sinais(auth_client, app, db):
    auth_client.post('/pacientes/novo', data=_dados_base(
        an_diagnostico_autismo='sim',
        an_familia_menopausa_precoce='nao',
        an_familia_ataxia_tremores='nao_sei',
    ), follow_redirects=True)
    with app.app_context():
        a = Paciente.query.filter_by(nome='Paciente Anamnese').first().anamnese
        assert a.sugestivo_pre_mutacao is False


def test_anamnese_aparece_no_detalhe(auth_client, paciente_factory, app, db):
    p = paciente_factory(nome='Detalhe Anamnese')
    with app.app_context():
        pid = p.id
    auth_client.post(f'/pacientes/{pid}/editar', data={
        'nome': 'Detalhe Anamnese', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01',
        'an_familia_menopausa_precoce': 'sim',
    }, follow_redirects=True)
    r = auth_client.get(f'/pacientes/{pid}')
    body = r.data.decode('utf-8')
    assert 'Anamnese' in body
    assert 'FXPOI' in body  # badge da suspeita de pré-mutação


def test_cadastro_publico_salva_anamnese(client, app, db):
    """Fluxo público via QR também grava a anamnese."""
    from datetime import datetime, timedelta
    from models.models import QrCadastroToken, Usuario
    with app.app_context():
        admin = Usuario.query.filter_by(email='admin@admin.com').first()
        qr = QrCadastroToken(token='tok-anamnese', id_usuario_emissor=admin.id,
                             tipo='basico',
                             expira_em=datetime.utcnow() + timedelta(hours=24))
        db.session.add(qr)
        db.session.commit()

    client.post('/publico/cadastro/tok-anamnese', data={
        'nome': 'Publico Anamnese', 'cpf': '11144477735', 'sexo': 'M',
        'data_nascimento': '2015-01-01', 'consentimento': 'on',
        'an_ja_fez_exame_dna': 'nao',
        'an_familia_ataxia_tremores': 'sim',
    })
    with app.app_context():
        p = Paciente.query.filter_by(nome='Publico Anamnese').first()
        assert p is not None
        assert p.anamnese is not None
        assert p.anamnese.ja_fez_exame_dna is False
        assert p.anamnese.familia_ataxia_tremores == 'sim'
