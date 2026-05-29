"""QR Code para auto-cadastro de paciente via celular.

Profissional logado gera um QR (link publico com token, valido por 24h).
Paciente abre no celular e preenche o cadastro de informacoes basicas.
"""

import io
import secrets
from datetime import datetime, timedelta

import qrcode
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from controllers.audit import log_audit
from controllers.email_service import (
    EmailNaoConfiguradoError,
    SenhaAppInvalidaError,
    email_configurado,
    enviar_email,
)
from controllers.paciente_controller import (
    _normalizar_cpf,
    _resolver_responsavel,
    _salvar_anamnese,
)
from models.models import Paciente, QrCadastroToken, db

TOKEN_VALIDADE_HORAS = 24


# ---------- Blueprint logado ----------

qr_bp = Blueprint('qr', __name__, url_prefix='/pacientes/qr')


def _check_ownership_qr(qr):
    if not current_user.is_admin and qr.id_usuario_emissor != current_user.id:
        abort(403)


def _pacientes_criados_via(qr):
    """Conta quantos pacientes foram criados via este QR (via LogAuditoria)."""
    import json

    from models.models import LogAuditoria

    candidatos = LogAuditoria.query.filter_by(acao='CREATE_VIA_QR', entidade='paciente').all()
    n = 0
    for log in candidatos:
        if not log.detalhes:
            continue
        try:
            if json.loads(log.detalhes).get('token_id') == qr.id:
                n += 1
        except Exception:
            pass
    return n


@qr_bp.route('/')
@login_required
def lista():
    q = QrCadastroToken.query.filter(QrCadastroToken.removido_em.is_(None))
    if not current_user.is_admin:
        q = q.filter_by(id_usuario_emissor=current_user.id)
    qrs = q.order_by(QrCadastroToken.criado_em.desc()).all()
    linhas = [{'qr': qr, 'pacientes': _pacientes_criados_via(qr)} for qr in qrs]
    return render_template('qr/lista.html', linhas=linhas)


@qr_bp.route('/gerar', methods=['POST'])
@login_required
def gerar():
    token = secrets.token_urlsafe(32)
    qr = QrCadastroToken(
        token=token,
        id_usuario_emissor=current_user.id,
        tipo='basico',
        expira_em=datetime.utcnow() + timedelta(hours=TOKEN_VALIDADE_HORAS),
    )
    db.session.add(qr)
    db.session.commit()
    log_audit(
        'CREATE',
        entidade='qr_cadastro_token',
        id_entidade=qr.id,
        detalhes={'tipo': 'basico'},
    )
    flash('QR de cadastro gerado. Compartilhe o link/imagem com o paciente.', 'success')
    return redirect(url_for('qr.detalhe', id=qr.id))


@qr_bp.route('/<int:id>')
@login_required
def detalhe(id):
    qr = db.get_or_404(QrCadastroToken, id)
    _check_ownership_qr(qr)
    link_publico = url_for('publico.cadastro_paciente', token=qr.token, _external=True)
    return render_template(
        'qr/detalhe.html',
        qr=qr,
        link_publico=link_publico,
        pacientes_criados=_pacientes_criados_via(qr),
        email_ok=email_configurado(),
    )


@qr_bp.route('/<int:id>/imagem.png')
@login_required
def imagem(id):
    qr = db.get_or_404(QrCadastroToken, id)
    _check_ownership_qr(qr)
    url = url_for('publico.cadastro_paciente', token=qr.token, _external=True)
    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name=f'qr_cadastro_{qr.id}.png')


@qr_bp.route('/<int:id>/enviar-email', methods=['POST'])
@login_required
def enviar_email_qr(id):
    qr = db.get_or_404(QrCadastroToken, id)
    _check_ownership_qr(qr)
    destino = (request.form.get('email_destino') or '').strip()
    if not destino:
        flash('Informe o e-mail de destino.', 'danger')
        return redirect(url_for('qr.detalhe', id=qr.id))
    if not qr.valido:
        flash('Este QR não está mais válido.', 'danger')
        return redirect(url_for('qr.detalhe', id=qr.id))

    link = url_for('publico.cadastro_paciente', token=qr.token, _external=True)
    corpo = (
        f'<p>Olá! Para preencher seu cadastro, acesse o link abaixo no seu celular:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f'<p>O link é válido até {qr.expira_em.strftime("%d/%m/%Y %H:%M")}.</p>'
    )
    try:
        enviar_email(destino, 'Cadastro de paciente — Triagem SXF', corpo)
        log_audit(
            'EMAIL_ENVIADO',
            entidade='qr_cadastro_token',
            id_entidade=qr.id,
            detalhes={'para': destino},
        )
        flash(f'Link enviado para {destino}.', 'success')
    except EmailNaoConfiguradoError:
        flash('Configure o e-mail em Administração antes de enviar.', 'danger')
    except SenhaAppInvalidaError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Falha ao enviar: {e}', 'danger')
    return redirect(url_for('qr.detalhe', id=qr.id))


@qr_bp.route('/<int:id>/prorrogar', methods=['POST'])
@login_required
def prorrogar(id):
    if not current_user.is_admin:
        abort(403)
    qr = db.get_or_404(QrCadastroToken, id)
    if qr.revogado_em is not None:
        flash('Não é possível prorrogar um QR revogado.', 'danger')
        return redirect(url_for('qr.detalhe', id=qr.id))

    unidade = (request.form.get('unidade') or '').strip()
    UNIDADES = {'minuto', 'hora', 'dia', 'mes', 'ano', 'sem_prazo'}

    if unidade not in UNIDADES:
        flash('Unidade de prazo inválida.', 'danger')
        return redirect(url_for('qr.detalhe', id=qr.id))

    if unidade == 'sem_prazo':
        qr.sem_expiracao = True
        detalhe = {'sem_expiracao': True}
    else:
        try:
            qtd = int(request.form.get('quantidade', ''))
            if qtd <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            flash('Informe uma quantidade válida (número inteiro positivo).', 'danger')
            return redirect(url_for('qr.detalhe', id=qr.id))

        DELTA = {
            'minuto': timedelta(minutes=qtd),
            'hora': timedelta(hours=qtd),
            'dia': timedelta(days=qtd),
            'mes': timedelta(days=qtd * 30),
            'ano': timedelta(days=qtd * 365),
        }
        base = max(datetime.utcnow(), qr.expira_em)
        qr.expira_em = base + DELTA[unidade]
        qr.sem_expiracao = False
        detalhe = {
            'quantidade': qtd,
            'unidade': unidade,
            'nova_expiracao': qr.expira_em.isoformat(),
        }

    db.session.commit()
    log_audit(
        'UPDATE',
        entidade='qr_cadastro_token',
        id_entidade=qr.id,
        detalhes={'prorrogado': detalhe},
    )
    flash('QR prorrogado com sucesso.', 'success')
    return redirect(url_for('qr.detalhe', id=qr.id))


@qr_bp.route('/<int:id>/revogar', methods=['POST'])
@login_required
def revogar(id):
    qr = db.get_or_404(QrCadastroToken, id)
    _check_ownership_qr(qr)
    if qr.revogado_em is None:
        qr.revogado_em = datetime.utcnow()
        db.session.commit()
        log_audit(
            'UPDATE',
            entidade='qr_cadastro_token',
            id_entidade=qr.id,
            detalhes={'revogado': True},
        )
        flash('QR revogado.', 'success')
    return redirect(url_for('qr.lista'))


# ---------- Blueprint publico (sem login) ----------

publico_bp = Blueprint('publico', __name__, url_prefix='/publico')


def _carregar_qr_valido(token):
    qr = QrCadastroToken.query.filter_by(token=token).first()
    if qr is None:
        return None
    if not qr.valido:
        return False
    return qr


@publico_bp.route('/cadastro/<token>', methods=['GET', 'POST'])
def cadastro_paciente(token):
    from datetime import date

    qr = _carregar_qr_valido(token)
    if qr is None:
        abort(404)
    if qr is False:
        return render_template('publico/link_expirado.html'), 410

    if request.method == 'POST':
        if not request.form.get('consentimento'):
            flash('É necessário confirmar o consentimento (LGPD).', 'danger')
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Informe o nome completo.', 'danger')
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )
        cpf = _normalizar_cpf(request.form.get('cpf'))
        if not cpf:
            flash('CPF inválido. Verifique os dígitos.', 'danger')
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )
        if Paciente.query.filter_by(cpf=cpf).first():
            flash(
                'Já existe um cadastro com este CPF. Procure seu profissional.',
                'danger',
            )
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )
        sexo = request.form.get('sexo')
        if sexo not in ('M', 'F'):
            flash('Selecione o sexo.', 'danger')
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )
        try:
            data_nasc = date.fromisoformat(request.form.get('data_nascimento', ''))
        except ValueError:
            flash('Data de nascimento inválida.', 'danger')
            return render_template(
                'publico/cadastro_paciente.html', token=token, form_data=request.form
            )

        id_responsavel = _resolver_responsavel(request.form)
        email_paciente = (request.form.get('email') or '').strip() or None

        paciente = Paciente(
            nome=nome,
            cpf=cpf,
            sexo=sexo,
            data_nascimento=data_nasc,
            email=email_paciente,
            id_responsavel=id_responsavel,
            id_usuario=qr.id_usuario_emissor,
            consentimento_dado_em=datetime.utcnow(),
        )
        db.session.add(paciente)
        db.session.flush()
        _salvar_anamnese(paciente, request.form)
        db.session.commit()

        log_audit(
            'CREATE_VIA_QR',
            entidade='paciente',
            id_entidade=paciente.id,
            id_usuario=qr.id_usuario_emissor,
            detalhes={
                'token_id': qr.id,
                'ip': request.remote_addr,
                'nome': nome,
                'cpf': cpf,
            },
        )
        return render_template('publico/cadastro_sucesso.html', token=token)

    return render_template('publico/cadastro_paciente.html', token=token, form_data=None)
