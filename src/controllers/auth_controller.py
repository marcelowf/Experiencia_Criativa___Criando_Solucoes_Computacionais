from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from controllers.audit import log_audit
from models.models import LogAuditoria, UserPreference, Usuario, db

auth_bp = Blueprint('auth', __name__)


MAX_TENTATIVAS_LOGIN = 5
JANELA_BLOQUEIO_MIN = 15


def _conta_bloqueada(email: str) -> bool:
    """True se houve >= MAX_TENTATIVAS_LOGIN LOGIN_FALHO para o email nos
    ultimos JANELA_BLOQUEIO_MIN minutos."""
    if not email:
        return False
    janela = datetime.utcnow() - timedelta(minutes=JANELA_BLOQUEIO_MIN)
    falhas = LogAuditoria.query.filter(
        LogAuditoria.acao == 'LOGIN_FALHO',
        LogAuditoria.data_hora >= janela,
        LogAuditoria.detalhes.like(f'%{email}%'),
    ).count()
    return falhas >= MAX_TENTATIVAS_LOGIN


@auth_bp.route('/', methods=['GET'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        if _conta_bloqueada(email):
            flash(
                f'Conta temporariamente bloqueada por excesso de tentativas. '
                f'Tente novamente em {JANELA_BLOQUEIO_MIN} minutos.',
                'danger',
            )
            return render_template('login.html')

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            log_audit('LOGIN', id_usuario=usuario.id)
            return redirect(url_for('auth.home'))
        log_audit('LOGIN_FALHO', detalhes={'email': email}, id_usuario=None)
        flash('Email ou senha incorretos.', 'danger')
    return render_template('login.html')


# ---------- Login federado via Google (OAuth/OIDC) ----------


def resolver_usuario_google(email: str, email_verificado: bool):
    """Resolve o usuário para login via Google.

    Regra de segurança: só entra quem JÁ existe na base (provisionado por um
    admin). Exige e-mail verificado pelo Google.

    Retorna (usuario, erro): usuario=None quando há erro; erro=None no sucesso.
    """
    email = (email or '').strip().lower()
    if not email or not email_verificado:
        return None, 'Não foi possível obter um e-mail verificado do Google.'
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is None:
        return None, (
            'Este e-mail do Google não está cadastrado. '
            'Peça a um administrador para criar seu acesso.'
        )
    return usuario, None


@auth_bp.route('/login/google')
def login_google():
    if not current_app.config.get('GOOGLE_LOGIN_ENABLED'):
        abort(404)
    from controllers.oauth import oauth

    redirect_uri = url_for('auth.callback_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/login/google/callback')
def callback_google():
    if not current_app.config.get('GOOGLE_LOGIN_ENABLED'):
        abort(404)
    from controllers.oauth import oauth

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        flash('Falha na autenticação com o Google. Tente novamente.', 'danger')
        return redirect(url_for('auth.login'))

    info = token.get('userinfo') or {}
    email = info.get('email', '')
    verificado = bool(info.get('email_verified'))

    usuario, erro = resolver_usuario_google(email, verificado)
    if erro:
        log_audit(
            'LOGIN_FALHO',
            id_usuario=None,
            detalhes={'email': (email or '').strip().lower(), 'metodo': 'google'},
        )
        flash(erro, 'danger')
        return redirect(url_for('auth.login'))

    login_user(usuario)
    log_audit('LOGIN', id_usuario=usuario.id, detalhes={'metodo': 'google'})
    return redirect(url_for('auth.home'))


@auth_bp.route('/home')
@login_required
def home():
    from datetime import date

    from werkzeug.datastructures import MultiDict

    from controllers.relatorio_stats import calcular_kpis, dados_por_mes, montar_query

    # Janela: do dia 1 do mes corrente ate hoje
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    # KPIs do mes
    args_mes = MultiDict([('data_inicio', inicio_mes.isoformat()), ('data_fim', hoje.isoformat())])
    avs_mes = montar_query(args_mes, current_user).all()
    kpis_mes = calcular_kpis(avs_mes)

    # Mini grafico: ultimos 6 meses
    seis_meses_atras = hoje.replace(day=1)
    for _ in range(5):
        # Volta 5 meses do inicio do mes corrente -> total 6 meses
        if seis_meses_atras.month == 1:
            seis_meses_atras = seis_meses_atras.replace(year=seis_meses_atras.year - 1, month=12)
        else:
            seis_meses_atras = seis_meses_atras.replace(month=seis_meses_atras.month - 1)
    args_6m = MultiDict(
        [('data_inicio', seis_meses_atras.isoformat()), ('data_fim', hoje.isoformat())]
    )
    avs_6m = montar_query(args_6m, current_user).all()
    serie_6m = dados_por_mes(avs_6m)

    return render_template('home.html', kpis_mes=kpis_mes, serie_6m=serie_6m)


@auth_bp.route('/logoff', methods=['POST'])
@login_required
def logoff():
    user_id = current_user.id
    logout_user()
    log_audit('LOGOUT', id_usuario=user_id)
    return redirect(url_for('auth.login'))


TEMAS_VALIDOS = ('claro', 'escuro')


@auth_bp.route('/tema/<valor>', methods=['POST'])
@login_required
def set_tema(valor):
    """Atualiza o tema (claro/escuro) do usuario logado e volta a pagina anterior."""
    if valor in TEMAS_VALIDOS:
        if not current_user.preferencias:
            db.session.add(UserPreference(id_usuario=current_user.id, tema=valor))
        else:
            current_user.preferencias.tema = valor
        db.session.commit()
    return redirect(request.referrer or url_for('auth.home'))
