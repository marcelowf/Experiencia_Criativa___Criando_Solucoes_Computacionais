"""Gerenciamento de versoes dos pesos cientificos.

Toda alteracao em peso de sintoma gera uma nova VersaoPesos imutavel,
permitindo rastrear qual peso foi aplicado em cada avaliacao historica.
"""

from models.models import Sintoma, SintomaPesoVersao, VersaoPesos, db


def versao_ativa() -> VersaoPesos | None:
    return VersaoPesos.query.filter_by(ativa=True).first()


def _proximo_nome() -> str:
    """V1, V2, V3... — auto-incrementado pelo numero de versoes existentes."""
    n = VersaoPesos.query.count() + 1
    return f'V{n}'


def criar_versao_inicial(criado_por_id=None, notas='Pesos cientificos iniciais (Herai/PUCPR)'):
    """Cria V1 com os pesos atuais dos sintomas. Idempotente (no-op se ja existe)."""
    if VersaoPesos.query.count() > 0:
        return None
    v = VersaoPesos(nome='V1', criado_por_id=criado_por_id, notas=notas, ativa=True)
    db.session.add(v)
    db.session.flush()
    for s in Sintoma.query.all():
        db.session.add(
            SintomaPesoVersao(
                id_versao=v.id,
                id_sintoma=s.id,
                peso_masculino=s.peso_masculino,
                peso_feminino=s.peso_feminino,
            )
        )
    db.session.commit()
    return v


def criar_nova_versao(criado_por_id: int, notas: str = '') -> VersaoPesos:
    """
    Snapshot dos pesos ATUAIS de todos os sintomas como uma nova versao.
    Desativa a anterior, ativa a nova.

    Convencao: chamar APOS aplicar as mudancas em Sintoma.peso_*.
    """
    # Desativa atual (se existir)
    VersaoPesos.query.filter_by(ativa=True).update({'ativa': False})

    nova = VersaoPesos(
        nome=_proximo_nome(),
        criado_por_id=criado_por_id,
        notas=notas or None,
        ativa=True,
    )
    db.session.add(nova)
    db.session.flush()

    for s in Sintoma.query.all():
        db.session.add(
            SintomaPesoVersao(
                id_versao=nova.id,
                id_sintoma=s.id,
                peso_masculino=s.peso_masculino,
                peso_feminino=s.peso_feminino,
            )
        )
    db.session.commit()
    return nova
