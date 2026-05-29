# Pesos cientificamente validados (Herai/PUCPR) vivem no banco (tabela `sintomas`).
# Os limiares de corte sao constantes do dominio e ficam aqui.

from models.models import Sintoma

LIMIAR_MASCULINO = 0.56
LIMIAR_FEMININO = 0.55


def get_sintomas_para_sexo(sexo: str):
    """Retorna lista de Sintoma ativos cujo peso para o sexo informado nao e null."""
    coluna = Sintoma.peso_masculino if sexo == 'M' else Sintoma.peso_feminino
    return (
        Sintoma.query.filter(Sintoma.ativo.is_(True), coluna.isnot(None))
        .order_by(coluna.desc())
        .all()
    )


def calcular_score(sintomas_presentes: dict, sexo: str) -> dict:
    """
    sintomas_presentes: {sintoma_id (int): 0 ou 1, ...}
    sexo: 'M' ou 'F'
    Retorna: {'score': float, 'recomendacao': 'ENCAMINHAR' ou 'NÃO ENCAMINHAR'}
    """
    sintomas = get_sintomas_para_sexo(sexo)
    score = 0.0
    for s in sintomas:
        if sintomas_presentes.get(s.id):
            score += s.peso_para_sexo(sexo) or 0.0

    limiar = LIMIAR_MASCULINO if sexo == 'M' else LIMIAR_FEMININO
    recomendacao = 'ENCAMINHAR' if score >= limiar else 'NÃO ENCAMINHAR'
    return {'score': round(score, 4), 'recomendacao': recomendacao}


def get_limiar(sexo: str) -> float:
    return LIMIAR_MASCULINO if sexo == 'M' else LIMIAR_FEMININO
