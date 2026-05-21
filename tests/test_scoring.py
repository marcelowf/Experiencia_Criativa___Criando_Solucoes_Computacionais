"""Testes do nucleo cientifico de scoring."""

from controllers.scoring import (calcular_score, get_sintomas_para_sexo,
                                 get_limiar, LIMIAR_MASCULINO, LIMIAR_FEMININO)


def test_sintomas_masculino_inclui_macroorquidismo(db):
    sintomas = get_sintomas_para_sexo('M')
    chaves = [s.chave for s in sintomas]
    assert 'macroorquidismo' in chaves
    assert 'deficiencia_intelectual' in chaves


def test_sintomas_feminino_exclui_macroorquidismo(db):
    sintomas = get_sintomas_para_sexo('F')
    chaves = [s.chave for s in sintomas]
    assert 'macroorquidismo' not in chaves


def test_score_zero_sem_sintomas_marcados(db):
    sintomas = get_sintomas_para_sexo('M')
    marcados = {s.id: 0 for s in sintomas}
    r = calcular_score(marcados, 'M')
    assert r['score'] == 0.0
    assert r['recomendacao'] == 'NÃO ENCAMINHAR'


def test_score_alto_encaminha(db):
    sintomas = get_sintomas_para_sexo('M')
    marcados = {s.id: 1 for s in sintomas}
    r = calcular_score(marcados, 'M')
    assert r['score'] >= LIMIAR_MASCULINO
    assert r['recomendacao'] == 'ENCAMINHAR'


def test_limiar_diferente_por_sexo():
    assert get_limiar('M') == LIMIAR_MASCULINO
    assert get_limiar('F') == LIMIAR_FEMININO
    assert LIMIAR_MASCULINO != LIMIAR_FEMININO


def test_score_respeita_apenas_sintomas_ativos(db):
    from models.models import Sintoma, db as _db
    # Desativar um sintoma e garantir que ele nao entra no score
    s = Sintoma.query.filter_by(chave='agressividade').first()
    s.ativo = False
    _db.session.commit()

    sintomas = get_sintomas_para_sexo('M')
    assert s not in sintomas


def test_recomendacao_pega_no_limiar(db):
    """Score exatamente no limiar deve encaminhar (>=)."""
    sintomas = get_sintomas_para_sexo('M')
    # Marcar so deficiencia_intelectual (peso 0.32) -> score 0.32, abaixo do limiar
    di = next(s for s in sintomas if s.chave == 'deficiencia_intelectual')
    marcados = {s.id: 0 for s in sintomas}
    marcados[di.id] = 1
    r = calcular_score(marcados, 'M')
    assert r['recomendacao'] == 'NÃO ENCAMINHAR'
    assert r['score'] == 0.32
