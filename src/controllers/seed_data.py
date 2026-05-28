# Dados iniciais para popular o banco em ambiente novo.
# Pesos derivados de Random Forest (Herai/PUCPR, 419 casos + 201 controles, sensibilidade 95%).
# Estes valores sao o seed inicial; após a primeira execução vivem no banco e podem
# ser editados pelo admin via /sintomas.
#
# As descricoes clinicas servem de tooltip no formulario de avaliacao
# e como apoio ao profissional na triagem.

SINTOMAS_INICIAIS = [
    {
        'chave': 'deficiencia_intelectual',
        'label': 'Deficiência Intelectual',
        'peso_masculino': 0.32, 'peso_feminino': 0.20,
        'descricao_clinica': (
            'Comprometimento das funções cognitivas (raciocínio, aprendizado, resolução de problemas) '
            'manifesto antes dos 18 anos. Em SXF, geralmente leve a moderada em meninos; '
            'em meninas, frequentemente menos grave ou apenas dificuldades específicas.'
        ),
    },
    {
        'chave': 'face_alongada_orelhas',
        'label': 'Face Alongada / Orelhas Proeminentes',
        'peso_masculino': 0.29, 'peso_feminino': 0.09,
        'descricao_clinica': (
            'Características faciais clássicas da SXF: face longa e estreita, mandíbula proeminente, '
            'orelhas grandes e abanadas. Tornam-se mais evidentes após a puberdade.'
        ),
    },
    {
        'chave': 'macroorquidismo',
        'label': 'Macroorquidismo',
        'peso_masculino': 0.26, 'peso_feminino': None,
        'descricao_clinica': (
            'Aumento do volume testicular além da média da idade. Sinal pós-puberal '
            'presente em ~80% dos homens com SXF. Avaliado por orquidômetro de Prader.'
        ),
    },
    {
        'chave': 'hipermobilidade_articular',
        'label': 'Hipermobilidade Articular',
        'peso_masculino': 0.19, 'peso_feminino': 0.04,
        'descricao_clinica': (
            'Amplitude articular acima do normal, com frouxidão ligamentar. Avaliada '
            'pela escala de Beighton (>=4/9 sugere hipermobilidade generalizada).'
        ),
    },
    {
        'chave': 'dificuldades_aprendizagem',
        'label': 'Dificuldades de Aprendizagem',
        'peso_masculino': 0.18, 'peso_feminino': 0.28,
        'descricao_clinica': (
            'Defasagem no desempenho escolar incompatível com a idade/instrução, '
            'mesmo sem deficiência intelectual evidente. Áreas comuns: matemática, leitura, '
            'memória de trabalho. Marca preditiva forte em meninas.'
        ),
    },
    {
        'chave': 'deficit_atencao',
        'label': 'Déficit de Atenção',
        'peso_masculino': 0.17, 'peso_feminino': 0.12,
        'descricao_clinica': (
            'Dificuldade sustentada de manter atenção em tarefas, distratibilidade, '
            'esquecimentos frequentes. Pode ocorrer com ou sem hiperatividade.'
        ),
    },
    {
        'chave': 'movimentos_repetitivos',
        'label': 'Movimentos Repetitivos',
        'peso_masculino': 0.17, 'peso_feminino': 0.05,
        'descricao_clinica': (
            'Estereotipias motoras: balanço corporal, bater de mãos (flapping), girar objetos, '
            'andar na ponta dos pés. Comum em SXF e em outros transtornos do neurodesenvolvimento.'
        ),
    },
    {
        'chave': 'atraso_fala',
        'label': 'Atraso na Fala',
        'peso_masculino': 0.14, 'peso_feminino': 0.01,
        'descricao_clinica': (
            'Aquisição tardia das primeiras palavras (>18 meses) ou de frases (>30 meses). '
            'Frequentemente acompanhado de fala perseverativa, ecolalia ou ritmo acelerado.'
        ),
    },
    {
        'chave': 'hiperatividade',
        'label': 'Hiperatividade',
        'peso_masculino': 0.12, 'peso_feminino': 0.04,
        'descricao_clinica': (
            'Inquietação motora persistente, dificuldade de permanecer sentado, fala excessiva, '
            'impulsividade. Pode preceder o diagnóstico de TDAH em crianças com SXF.'
        ),
    },
    {
        'chave': 'evita_contato_visual',
        'label': 'Evita Contato Visual',
        'peso_masculino': 0.06, 'peso_feminino': 0.08,
        'descricao_clinica': (
            'Tendência a desviar o olhar durante interação social, sobretudo com estranhos. '
            'Característica frequentemente associada à ansiedade social na SXF.'
        ),
    },
    {
        'chave': 'evita_contato_fisico',
        'label': 'Evita Contato Físico',
        'peso_masculino': 0.04, 'peso_feminino': 0.07,
        'descricao_clinica': (
            'Defensividade tátil: reação adversa a abraços, toques inesperados, etiquetas em roupas. '
            'Parte do perfil de hipersensibilidade sensorial típico da SXF.'
        ),
    },
    {
        'chave': 'agressividade',
        'label': 'Agressividade',
        'peso_masculino': 0.01, 'peso_feminino': 0.02,
        'descricao_clinica': (
            'Episódios de hetero ou autoagressão (morder, bater, gritar) frequentemente desencadeados '
            'por sobrecarga sensorial ou frustração. Sinal de menor peso preditivo isolado.'
        ),
    },
]


def migrar_schema_auditoria():
    """Adiciona colunas de auditoria (criado_em / atualizado_em / criado_por_id /
    atualizado_por_id / removido_em) em DBs antigos. Idempotente.

    Tambem renomeia VersaoPesos.criada_em -> criado_em e criada_por_id -> criado_por_id.
    """
    from sqlalchemy import text, inspect
    from models.models import db

    AUDIT_TABLES = {
        'usuarios':                {'auditable': True,  'soft': False},
        'responsaveis':            {'auditable': True,  'soft': True},
        'pacientes':               {'auditable': True,  'soft': True},
        'dados_socioeconomicos':   {'auditable': True,  'soft': False},
        'avaliacoes':              {'auditable': True,  'soft': True},
        'sintomas':       {'auditable': True,  'soft': True},
        'versoes_pesos':  {'auditable': True,  'soft': True},
    }
    insp = inspect(db.engine)

    with db.engine.begin() as conn:
        # rename em versoes_pesos (se ainda nao foi feito)
        if insp.has_table('versoes_pesos'):
            vcols = {c['name'] for c in insp.get_columns('versoes_pesos')}
            if 'criada_em' in vcols and 'criado_em' not in vcols:
                conn.execute(text('ALTER TABLE versoes_pesos RENAME COLUMN criada_em TO criado_em'))
            if 'criada_por_id' in vcols and 'criado_por_id' not in vcols:
                conn.execute(text('ALTER TABLE versoes_pesos RENAME COLUMN criada_por_id TO criado_por_id'))

        # adicionar colunas faltantes
        insp = inspect(db.engine)  # re-inspect apos rename
        for tabela, flags in AUDIT_TABLES.items():
            if not insp.has_table(tabela):
                continue
            cols = {c['name'] for c in insp.get_columns(tabela)}
            adds = []
            if flags['auditable']:
                if 'criado_em' not in cols:
                    adds.append("ADD COLUMN criado_em TIMESTAMP NOT NULL DEFAULT NOW()")
                if 'atualizado_em' not in cols:
                    adds.append("ADD COLUMN atualizado_em TIMESTAMP NOT NULL DEFAULT NOW()")
                if 'criado_por_id' not in cols:
                    adds.append("ADD COLUMN criado_por_id INTEGER REFERENCES usuarios(id)")
                if 'atualizado_por_id' not in cols:
                    adds.append("ADD COLUMN atualizado_por_id INTEGER REFERENCES usuarios(id)")
            if flags['soft'] and 'removido_em' not in cols:
                adds.append("ADD COLUMN removido_em TIMESTAMP")
            if adds:
                conn.execute(text(f'ALTER TABLE {tabela} ' + ', '.join(adds)))


def migrar_responsavel_string_para_tabela():
    """Move o campo legado Paciente.responsavel (string) para a tabela Responsavel.

    Idempotente: roda no boot e ignora pacientes que ja tem id_responsavel ou
    nao tem nome de responsavel. Tambem garante a coluna `id_responsavel`
    em DBs antigos (db.create_all nao executa ALTER TABLE).
    """
    from sqlalchemy import text, inspect
    from models.models import db, Paciente, Responsavel

    insp = inspect(db.engine)
    cols = {c['name'] for c in insp.get_columns('pacientes')}
    if 'id_responsavel' not in cols:
        with db.engine.begin() as conn:
            conn.execute(text(
                'ALTER TABLE pacientes ADD COLUMN id_responsavel INTEGER '
                'REFERENCES responsaveis(id)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_pacientes_id_responsavel '
                'ON pacientes (id_responsavel)'
            ))
    if 'email' not in cols:
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE pacientes ADD COLUMN email VARCHAR(120)'))

    if insp.has_table('qr_cadastro_tokens'):
        qr_cols = {c['name'] for c in insp.get_columns('qr_cadastro_tokens')}
        if 'sem_expiracao' not in qr_cols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    'ALTER TABLE qr_cadastro_tokens '
                    'ADD COLUMN sem_expiracao BOOLEAN NOT NULL DEFAULT FALSE'
                ))

    pendentes = (Paciente.query
                 .filter(Paciente.id_responsavel.is_(None))
                 .filter(Paciente.responsavel.isnot(None))
                 .filter(Paciente.responsavel != '')
                 .all())
    if not pendentes:
        return

    # Cache por nome normalizado para deduplicar dentro do mesmo batch
    cache = {}
    for p in pendentes:
        chave = (p.responsavel or '').strip().lower()
        if not chave:
            continue
        resp = cache.get(chave)
        if resp is None:
            resp = Responsavel.query.filter(
                db.func.lower(Responsavel.nome) == chave
            ).first()
        if resp is None:
            resp = Responsavel(nome=p.responsavel.strip())
            db.session.add(resp)
            db.session.flush()
        cache[chave] = resp
        p.id_responsavel = resp.id
    db.session.commit()
