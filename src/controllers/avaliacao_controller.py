from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from controllers.audit import log_audit
from controllers.email_service import (
    EmailNaoConfiguradoError,
    SenhaAppInvalidaError,
    email_configurado,
    email_destino,
    enviar_email,
)
from controllers.scoring import calcular_score, get_limiar, get_sintomas_para_sexo
from controllers.versoes_pesos import versao_ativa
from models.models import Avaliacao, Paciente, SintomaAvaliacao, db


def _resultado_pdf_bytes(avaliacao):
    from weasyprint import HTML

    html_str = render_template(
        'avaliacoes/resultado_pdf.html',
        avaliacao=avaliacao,
        paciente=avaliacao.paciente,
        limiar=get_limiar(avaliacao.paciente.sexo),
    )
    return HTML(string=html_str, base_url=request.host_url).write_pdf()


avaliacao_bp = Blueprint('avaliacao', __name__, url_prefix='/avaliacoes')


def _check_access(obj_usuario_id):
    if not current_user.is_admin and obj_usuario_id != current_user.id:
        abort(403)


@avaliacao_bp.route('/nova/<int:id_paciente>', methods=['GET'])
@login_required
def formulario(id_paciente):
    paciente = db.get_or_404(Paciente, id_paciente)
    _check_access(paciente.id_usuario)
    sintomas = get_sintomas_para_sexo(paciente.sexo)
    return render_template('avaliacoes/formulario.html', paciente=paciente, sintomas=sintomas)


@avaliacao_bp.route('/nova', methods=['POST'])
@login_required
def processar():
    id_paciente = int(request.form['id_paciente'])
    paciente = db.get_or_404(Paciente, id_paciente)
    _check_access(paciente.id_usuario)

    sintomas = get_sintomas_para_sexo(paciente.sexo)
    sintomas_dict = {
        s.id: 1 if request.form.get(f'sintoma_{s.id}') == 'on' else 0 for s in sintomas
    }

    resultado = calcular_score(sintomas_dict, paciente.sexo)
    versao = versao_ativa()

    avaliacao = Avaliacao(
        id_paciente=id_paciente,
        data=date.today(),
        score=resultado['score'],
        recomendacao=resultado['recomendacao'],
        id_usuario=current_user.id,
        id_versao_pesos=versao.id if versao else None,
    )
    db.session.add(avaliacao)
    db.session.flush()

    for s in sintomas:
        db.session.add(
            SintomaAvaliacao(
                id_avaliacao=avaliacao.id,
                id_sintoma=s.id,
                presente=bool(sintomas_dict.get(s.id)),
            )
        )

    db.session.commit()
    log_audit(
        'CREATE',
        entidade='avaliacao',
        id_entidade=avaliacao.id,
        detalhes={
            'id_paciente': id_paciente,
            'score': resultado['score'],
            'recomendacao': resultado['recomendacao'],
        },
    )
    return redirect(url_for('avaliacao.resultado', id=avaliacao.id))


@avaliacao_bp.route('/<int:id>/resultado')
@login_required
def resultado(id):
    avaliacao = db.get_or_404(Avaliacao, id)
    _check_access(avaliacao.id_usuario)
    return render_template(
        'avaliacoes/resultado.html',
        avaliacao=avaliacao,
        paciente=avaliacao.paciente,
        limiar=get_limiar(avaliacao.paciente.sexo),
        email_ok=email_configurado(),
        email_sugerido=email_destino(avaliacao.paciente),
    )


@avaliacao_bp.route('/<int:id>/enviar-email', methods=['POST'])
@login_required
def enviar_email_resultado(id):
    avaliacao = db.get_or_404(Avaliacao, id)
    _check_access(avaliacao.id_usuario)
    destino = (request.form.get('email_destino') or '').strip()
    if not destino:
        flash('Informe o e-mail de destino.', 'danger')
        return redirect(url_for('avaliacao.resultado', id=id))

    corpo = (
        f'<p>Segue em anexo o resultado da triagem de '
        f'<strong>{avaliacao.paciente.nome}</strong> '
        f'realizada em {avaliacao.data.strftime("%d/%m/%Y")}.</p>'
    )
    try:
        pdf = _resultado_pdf_bytes(avaliacao)
        enviar_email(
            destino,
            'Resultado da triagem — Triagem SXF',
            corpo,
            anexos=[('resultado_triagem.pdf', pdf, 'application/pdf')],
        )
        log_audit(
            'EMAIL_ENVIADO',
            entidade='avaliacao',
            id_entidade=id,
            detalhes={'para': destino},
        )
        flash(f'Resultado enviado para {destino}.', 'success')
    except EmailNaoConfiguradoError:
        flash('Configure o e-mail em Administração antes de enviar.', 'danger')
    except SenhaAppInvalidaError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Falha ao enviar: {e}', 'danger')
    return redirect(url_for('avaliacao.resultado', id=id))


@avaliacao_bp.route('/historico/<int:id_paciente>')
@login_required
def historico(id_paciente):
    paciente = db.get_or_404(Paciente, id_paciente)
    _check_access(paciente.id_usuario)
    avaliacoes = (
        Avaliacao.query.filter_by(id_paciente=id_paciente)
        .filter(Avaliacao.removido_em.is_(None))
        .order_by(Avaliacao.data.desc())
        .all()
    )
    return render_template('avaliacoes/historico.html', paciente=paciente, avaliacoes=avaliacoes)
