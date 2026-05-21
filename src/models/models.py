import re
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime

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


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(10), nullable=False, default='padrao')  # 'admin' | 'padrao'

    token_reset = db.Column(db.String(80), nullable=True, index=True)
    token_reset_expira_em = db.Column(db.DateTime, nullable=True)

    pacientes = db.relationship('Paciente', backref='usuario', lazy=True)
    avaliacoes = db.relationship('Avaliacao', backref='usuario', lazy=True)
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


class Paciente(db.Model):
    __tablename__ = 'pacientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    sexo = db.Column(db.String(1), nullable=False)  # 'M' | 'F'
    data_nascimento = db.Column(db.Date, nullable=False)
    responsavel = db.Column(db.String(120))
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    consentimento_dado_em = db.Column(db.DateTime, nullable=True)
    removido_em = db.Column(db.DateTime, nullable=True, index=True)

    avaliacoes = db.relationship('Avaliacao', backref='paciente', lazy=True)

    @property
    def ativo(self):
        return self.removido_em is None


class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'
    id = db.Column(db.Integer, primary_key=True)
    id_paciente = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, default=date.today, index=True)
    score = db.Column(db.Float, nullable=False)
    recomendacao = db.Column(db.String(20), nullable=False, index=True)  # 'ENCAMINHAR' | 'NÃO ENCAMINHAR'
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    id_versao_pesos = db.Column(db.Integer, db.ForeignKey('versoes_pesos.id'),
                                nullable=True, index=True)
    removido_em = db.Column(db.DateTime, nullable=True, index=True)

    versao_pesos = db.relationship('VersaoPesos')

    sintomas = db.relationship(
        'SintomaAvaliacao', backref='avaliacao', lazy=True, cascade='all, delete-orphan'
    )

    @property
    def ativo(self):
        return self.removido_em is None


class Sintoma(db.Model):
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


class VersaoPesos(db.Model):
    """
    Snapshot imutavel dos pesos cientificos vigentes em um momento.
    Toda avaliacao aponta para a versao usada no calculo.
    Apenas UMA versao tem `ativa=True` ao mesmo tempo (versao corrente).
    """
    __tablename__ = 'versoes_pesos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(10), unique=True, nullable=False)  # 'V1', 'V2', ...
    criada_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    criada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    notas = db.Column(db.Text, nullable=True)
    ativa = db.Column(db.Boolean, nullable=False, default=False, index=True)

    criada_por = db.relationship('Usuario')
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
