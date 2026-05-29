"""Testes do fluxo de avaliacao."""

from models.models import Avaliacao, Sintoma, SintomaAvaliacao


def test_formulario_exibe_sintomas(auth_client, paciente_factory):
    p = paciente_factory(sexo='M')
    r = auth_client.get(f'/avaliacoes/nova/{p.id}')
    body = r.data.decode('utf-8')
    assert 'Macroorquidismo' in body  # so existe para M
    assert 'Deficiência Intelectual' in body


def test_formulario_feminino_oculta_macroorquidismo(auth_client, paciente_factory):
    p = paciente_factory(sexo='F')
    r = auth_client.get(f'/avaliacoes/nova/{p.id}')
    assert 'Macroorquidismo' not in r.data.decode('utf-8')


def test_processar_avaliacao_salva_score(auth_client, paciente_factory, app, db):
    p = paciente_factory(sexo='M')
    with app.app_context():
        sintomas = Sintoma.query.filter_by(ativo=True).all()
        data = {'id_paciente': p.id}
        for s in sintomas:
            data[f'sintoma_{s.id}'] = 'on'
    r = auth_client.post('/avaliacoes/nova', data=data, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        av = Avaliacao.query.filter_by(id_paciente=p.id).first()
        assert av is not None
        assert av.recomendacao == 'ENCAMINHAR'
        assert av.score > 0
        # cada sintoma deve ter sido registrado
        assert SintomaAvaliacao.query.filter_by(id_avaliacao=av.id).count() > 0


def test_acesso_negado_paciente_de_outro(auth_client_padrao, paciente_factory, admin):
    p = paciente_factory(id_usuario=admin.id)
    r = auth_client_padrao.get(f'/avaliacoes/nova/{p.id}')
    assert r.status_code == 403
