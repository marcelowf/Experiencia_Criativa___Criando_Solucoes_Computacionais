import re
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from sqlalchemy import event
from sqlalchemy.orm import declared_attr

db = SQLAlchemy()


class SenhaFracaError(ValueError):
    """Senha nao atende a politica minima."""


def validar_forca_senha(senha: str) -> None:
    """Levanta SenhaFracaError se a senha for fraca.

    Requisitos: >=8 caracteres, ao menos 1 letra e 1 numero.
    """
    if not senha or len(senha) < 8:
        raise SenhaFracaError('A senha deve ter ao menos 8 caracteres.')
    if not re.search(r'[A-Za-z]', senha):
        raise SenhaFracaError('A senha deve conter ao menos uma letra.')
    if not re.search(r'\d', senha):
        raise SenhaFracaError('A senha deve conter ao menos um número.')


# ---------- Mixins de auditoria ----------

class Auditable:
    """Adiciona criado_em / atualizado_em / criado_por_id / atualizado_por_id."""
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False,
                              default=datetime.utcnow, onupdate=datetime.utcnow)

    @declared_attr
    def criado_por_id(cls):
        return db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    @declared_attr
    def atualizado_por_id(cls):
        return db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)


class SoftDeletable:
    """Adiciona removido_em + propriedade ativo."""
    removido_em = db.Column(db.DateTime, nullable=True, index=True)

    @property
    def ativo(self):
        return self.removido_em is None


# ---------- Modelos ----------

class Usuario(UserMixin, Auditable, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(10), nullable=False, default='padrao')  # 'admin' | 'padrao'

    token_reset = db.Column(db.String(80), nullable=True, index=True)
    token_reset_expira_em = db.Column(db.DateTime, nullable=True)

    pacientes = db.relationship('Paciente', backref='usuario', lazy=True,
                                foreign_keys='Paciente.id_usuario')
    avaliacoes = db.relationship('Avaliacao', backref='usuario', lazy=True,
                                 foreign_keys='Avaliacao.id_usuario')
    preferencias = db.relationship(
        'UserPreference', backref='usuario', uselist=False,
        cascade='all, delete-orphan'
    )

    def set_senha(self, senha, validar=True):
        if validar:
            validar_forca_senha(senha)
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self):
        return self.perfil == 'admin'


class UserPreference(db.Model):
    __tablename__ = 'user_preferences'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), unique=True, nullable=False)
    tema = db.Column(db.String(20), nullable=False, default='claro')    # 'claro' | 'escuro' | 'auto'


class Responsavel(Auditable, SoftDeletable, db.Model):
    __tablename__ = 'responsaveis'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, index=True)
    cpf = db.Column(db.String(14), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    parentesco = db.Column(db.String(40), nullable=True)

    pacientes = db.relationship('Paciente', backref='responsavel_obj', lazy=True)


class Paciente(Auditable, SoftDeletable, db.Model):
    __tablename__ = 'pacientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    sexo = db.Column(db.String(1), nullable=False)  # 'M' | 'F'
    data_nascimento = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    responsavel = db.Column(db.String(120))  # legado: nome livre antes de Responsavel
    id_responsavel = db.Column(db.Integer, db.ForeignKey('responsaveis.id'),
                               nullable=True, index=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    consentimento_dado_em = db.Column(db.DateTime, nullable=True)

    avaliacoes = db.relationship('Avaliacao', backref='paciente', lazy=True)


FAIXAS_RENDA = [
    ('sem_renda', 'Sem renda'),
    ('ate_1sm',   'Até 1 salário mínimo'),
    ('1_3sm',     '1 a 3 salários mínimos'),
    ('3_5sm',     '3 a 5 salários mínimos'),
    ('acima_5sm', 'Acima de 5 salários mínimos'),
]

ESCOLARIDADES = [
    ('sem_instrucao', 'Sem instrução'),
    ('fundamental',   'Ensino Fundamental'),
    ('medio',         'Ensino Médio'),
    ('superior',      'Ensino Superior ou mais'),
]

BAIXA_RENDA_FAIXAS = {'sem_renda', 'ate_1sm'}


class DadosSocioeconomicos(Auditable, db.Model):
    """Informacoes socioeconomicas opcionais do paciente (1:1)."""
    __tablename__ = 'dados_socioeconomicos'
    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'),
                            unique=True, nullable=False, index=True)
    renda_faixa = db.Column(db.String(20), nullable=True)
    profissao = db.Column(db.String(120), nullable=True)
    escolaridade = db.Column(db.String(20), nullable=True)
    num_dependentes = db.Column(db.Integer, nullable=True)

    paciente = db.relationship('Paciente',
                               backref=db.backref('dados_socioeconomicos', uselist=False))

    @property
    def baixa_renda(self):
        return self.renda_faixa in BAIXA_RENDA_FAIXAS


# Opcoes da anamnese (historia clinica/familiar). Sao CONTEXTO: nao entram no score.
RESULTADO_EXAME_OPCOES = [
    ('mutacao_completa', 'Mutação Completa (+200 repetições CGG)'),
    ('pre_mutacao',      'Pré-mutação (55 a 199 repetições)'),
    ('zona_gray',        'Zona Gray / Intermediária (45 a 54 repetições)'),
    ('mosaicismo',       'Mosaicismo'),
    ('negativo',         'Negativo para X Frágil (até 39 repetições)'),
    ('nao_sei',          'Não sei'),
]
_RESULTADO_EXAME_MAP = dict(RESULTADO_EXAME_OPCOES)
_TRI_MAP = {'sim': 'Sim', 'nao': 'Não', 'nao_sei': 'Não sei'}


class Anamnese(Auditable, db.Model):
    """História clínica/familiar do paciente (1:1). Contexto de triagem — NÃO afeta o score.

    Espelha o questionário de intake do cliente (Q1–Q8). Campos booleanos usam
    None = não respondido; campos ternários guardam 'sim'/'nao'/'nao_sei'.
    """
    __tablename__ = 'anamnese'
    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'),
                            unique=True, nullable=False, index=True)

    # Q1 — já fez exame de DNA (sangue/saliva) para SXF
    ja_fez_exame_dna = db.Column(db.Boolean, nullable=True)
    # Q2 — interesse em fazer o exame de DNA (PCR)
    interesse_exame_pcr = db.Column(db.Boolean, nullable=True)
    # Q3 — resultado confirmado por laboratório (se já tem), por nº de repetições CGG
    resultado_exame = db.Column(db.String(20), nullable=True)
    # Q4 — diagnóstico de autismo
    diagnostico_autismo = db.Column(db.Boolean, nullable=True)
    # Q5 — tem irmãos
    tem_irmaos = db.Column(db.Boolean, nullable=True)
    # Q6 — família com def. intelectual / atraso / dificuldades de aprendizagem / autismo
    familia_neurodesenvolvimento = db.Column(db.String(10), nullable=True)
    # Q7 — antecedentes de menopausa precoce na família (sugestivo de FXPOI / pré-mutação)
    familia_menopausa_precoce = db.Column(db.String(10), nullable=True)
    # Q8 — antecedentes de ataxia (descoordenação) e tremores (sugestivo de FXTAS / pré-mutação)
    familia_ataxia_tremores = db.Column(db.String(10), nullable=True)

    paciente = db.relationship('Paciente',
                               backref=db.backref('anamnese', uselist=False))

    @property
    def resultado_exame_label(self):
        return _RESULTADO_EXAME_MAP.get(self.resultado_exame)

    @staticmethod
    def _bool_label(v):
        return None if v is None else ('Sim' if v else 'Não')

    @property
    def ja_fez_exame_dna_label(self):   return self._bool_label(self.ja_fez_exame_dna)
    @property
    def interesse_exame_pcr_label(self): return self._bool_label(self.interesse_exame_pcr)
    @property
    def diagnostico_autismo_label(self): return self._bool_label(self.diagnostico_autismo)
    @property
    def tem_irmaos_label(self):          return self._bool_label(self.tem_irmaos)
    @property
    def familia_neurodesenvolvimento_label(self): return _TRI_MAP.get(self.familia_neurodesenvolvimento)
    @property
    def familia_menopausa_precoce_label(self):    return _TRI_MAP.get(self.familia_menopausa_precoce)
    @property
    def familia_ataxia_tremores_label(self):      return _TRI_MAP.get(self.familia_ataxia_tremores)

    @property
    def sugestivo_pre_mutacao(self):
        """True se há sinais familiares de portador de pré-mutação (FXPOI ou FXTAS)."""
        return 'sim' in (self.familia_menopausa_precoce, self.familia_ataxia_tremores)


class Avaliacao(Auditable, SoftDeletable, db.Model):
    __tablename__ = 'avaliacoes'
    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, default=date.today, index=True)
    score = db.Column(db.Float, nullable=False)
    recomendacao = db.Column(db.String(20), nullable=False, index=True)  # 'ENCAMINHAR' | 'NÃO ENCAMINHAR'
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    id_versao_pesos = db.Column(db.Integer, db.ForeignKey('versoes_pesos.id'),
                                nullable=True, index=True)

    versao_pesos = db.relationship('VersaoPesos')

    sintomas = db.relationship(
        'SintomaAvaliacao', backref='avaliacao', lazy=True, cascade='all, delete-orphan'
    )


class Sintoma(Auditable, SoftDeletable, db.Model):
    """
    Definicao do sintoma. Os campos `peso_masculino`/`peso_feminino` sao uma
    denormalizacao dos pesos da versao ATIVA — fonte canonica do historico
    fica em SintomaPesoVersao.
    """
    __tablename__ = 'sintomas'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(60), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    peso_masculino = db.Column(db.Float, nullable=True)
    peso_feminino = db.Column(db.Float, nullable=True)
    descricao_clinica = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    def peso_para_sexo(self, sexo):
        return self.peso_masculino if sexo == 'M' else self.peso_feminino


class VersaoPesos(Auditable, SoftDeletable, db.Model):
    """
    Snapshot imutavel dos pesos cientificos vigentes em um momento.
    Toda avaliacao aponta para a versao usada no calculo.
    Apenas UMA versao tem `ativa=True` ao mesmo tempo (versao corrente).
    """
    __tablename__ = 'versoes_pesos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(10), unique=True, nullable=False)  # 'V1', 'V2', ...
    notas = db.Column(db.Text, nullable=True)
    ativa = db.Column(db.Boolean, nullable=False, default=False, index=True)

    criado_por = db.relationship('Usuario', foreign_keys='VersaoPesos.criado_por_id')
    pesos = db.relationship('SintomaPesoVersao', backref='versao',
                            lazy=True, cascade='all, delete-orphan')


class SintomaPesoVersao(db.Model):
    """Peso de um sintoma em uma versao especifica (imutavel apos criacao)."""
    __tablename__ = 'sintoma_peso_versao'
    id = db.Column(db.Integer, primary_key=True)
    id_versao = db.Column(db.Integer, db.ForeignKey('versoes_pesos.id'),
                          nullable=False, index=True)
    id_sintoma = db.Column(db.Integer, db.ForeignKey('sintomas.id'),
                           nullable=False, index=True)
    peso_masculino = db.Column(db.Float, nullable=True)
    peso_feminino = db.Column(db.Float, nullable=True)

    sintoma = db.relationship('Sintoma')

    __table_args__ = (
        db.UniqueConstraint('id_versao', 'id_sintoma', name='uq_versao_sintoma'),
    )


class SintomaAvaliacao(db.Model):
    __tablename__ = 'sintomas_avaliacao'
    id = db.Column(db.Integer, primary_key=True)
    id_avaliacao = db.Column(db.Integer, db.ForeignKey('avaliacoes.id'), nullable=False, index=True)
    id_sintoma = db.Column(db.Integer, db.ForeignKey('sintomas.id'), nullable=False, index=True)
    presente = db.Column(db.Boolean, nullable=False)

    sintoma = db.relationship('Sintoma')


class QrCadastroToken(Auditable, SoftDeletable, db.Model):
    """Token publico para um paciente preencher o proprio cadastro via QR Code."""
    __tablename__ = 'qr_cadastro_tokens'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    id_usuario_emissor = db.Column(db.Integer, db.ForeignKey('usuarios.id'),
                                   nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default='basico')
    expira_em = db.Column(db.DateTime, nullable=False, index=True)
    sem_expiracao = db.Column(db.Boolean, nullable=False, default=False)
    revogado_em = db.Column(db.DateTime, nullable=True)

    emissor = db.relationship('Usuario', foreign_keys=[id_usuario_emissor])

    @property
    def valido(self):
        return (self.revogado_em is None
                and self.removido_em is None
                and (self.sem_expiracao or self.expira_em > datetime.utcnow()))


class EmailConfig(Auditable, db.Model):
    """Configuracao singleton de envio de e-mail (Gmail via senha de app)."""
    __tablename__ = 'email_configs'
    id = db.Column(db.Integer, primary_key=True)
    remetente_email = db.Column(db.String(120), nullable=False)
    remetente_nome = db.Column(db.String(120), nullable=True, default='Triagem SXF')
    senha_app_cifrada = db.Column(db.Text, nullable=False)  # token Fernet
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class AiConfig(Auditable, db.Model):
    """Configuracao singleton do assistente de IA (Ollama)."""
    __tablename__ = 'ai_configs'
    id = db.Column(db.Integer, primary_key=True)
    base_url = db.Column(db.String(200), nullable=False, default='http://ollama:11434')
    modelo = db.Column(db.String(80), nullable=False, default='qwen2.5:7b')
    temperatura = db.Column(db.Float, nullable=False, default=0.3)
    max_iteracoes = db.Column(db.Integer, nullable=False, default=5)
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class ChatConversa(Auditable, SoftDeletable, db.Model):
    """Conversa do assistente de IA. Pertence a um usuario (privada)."""
    __tablename__ = 'chat_conversas'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    titulo = db.Column(db.String(160), nullable=False, default='Nova conversa')

    usuario = db.relationship('Usuario', foreign_keys=[id_usuario])
    mensagens = db.relationship(
        'ChatMensagem', backref='conversa', lazy=True,
        cascade='all, delete-orphan', order_by='ChatMensagem.criado_em'
    )


class ChatMensagem(db.Model):
    """Mensagem de uma conversa. papel: 'user' | 'assistant' | 'tool'."""
    __tablename__ = 'chat_mensagens'
    id = db.Column(db.Integer, primary_key=True)
    id_conversa = db.Column(db.Integer, db.ForeignKey('chat_conversas.id'),
                            nullable=False, index=True)
    papel = db.Column(db.String(12), nullable=False)
    conteudo = db.Column(db.Text, nullable=True)
    tool_nome = db.Column(db.String(60), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class LogAuditoria(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    acao = db.Column(db.String(20), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, LOGIN_FALHO
    entidade = db.Column(db.String(40), nullable=True, index=True)  # paciente, avaliacao, sintoma, usuario
    id_entidade = db.Column(db.Integer, nullable=True)
    detalhes = db.Column(db.Text, nullable=True)            # JSON serializado
    ip = db.Column(db.String(45), nullable=True)
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    usuario = db.relationship('Usuario')


# ---------- Event listeners para auto-popular criado_por/atualizado_por ----------

AUDITABLE_CLASSES = [Usuario, Responsavel, Paciente, DadosSocioeconomicos,
                     Avaliacao, Sintoma, VersaoPesos,
                     QrCadastroToken, EmailConfig, AiConfig, ChatConversa]


def _current_user_id_ou_none():
    """Retorna current_user.id se houver request autenticada, senao None."""
    try:
        from flask import has_request_context
        from flask_login import current_user
        if has_request_context() and getattr(current_user, 'is_authenticated', False):
            return current_user.id
    except Exception:
        pass
    return None


def _audit_before_insert(mapper, connection, target):
    uid = _current_user_id_ou_none()
    if uid is not None:
        if target.criado_por_id is None:
            target.criado_por_id = uid
        if target.atualizado_por_id is None:
            target.atualizado_por_id = uid


def _audit_before_update(mapper, connection, target):
    uid = _current_user_id_ou_none()
    if uid is not None:
        target.atualizado_por_id = uid


for _cls in AUDITABLE_CLASSES:
    event.listen(_cls, 'before_insert', _audit_before_insert)
    event.listen(_cls, 'before_update', _audit_before_update)
