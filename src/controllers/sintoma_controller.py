from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from models.models import db, Sintoma, VersaoPesos, SintomaPesoVersao
from controllers.audit import admin_required, log_audit
from controllers.versoes_pesos import criar_nova_versao, versao_ativa

sintoma_bp = Blueprint('sintoma', __name__, url_prefix='/sintomas')


def _parse_float(value):
    value = (value or '').strip().replace(',', '.')
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _pesos_mudaram(antes, depois):
    return (antes['peso_masculino'] != depois['peso_masculino']
            or antes['peso_feminino'] != depois['peso_feminino'])


@sintoma_bp.route('/')
@login_required
@admin_required
def lista():
    sintomas = Sintoma.query.order_by(Sintoma.label).all()
    return render_template('sintomas/lista.html',
                           sintomas=sintomas, versao=versao_ativa())


@sintoma_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo():
    if request.method == 'POST':
        chave = request.form['chave'].strip()
        if Sintoma.query.filter_by(chave=chave).first():
            flash('Já existe um sintoma com essa chave.', 'danger')
            return render_template('sintomas/form.html', sintoma=None,
                                   acao='Novo Sintoma', form_data=request.form)
        s = Sintoma(
            chave=chave,
            label=request.form['label'].strip(),
            peso_masculino=_parse_float(request.form.get('peso_masculino')),
            peso_feminino=_parse_float(request.form.get('peso_feminino')),
            descricao_clinica=request.form.get('descricao_clinica', '').strip() or None,
            ativo=request.form.get('ativo') == 'on',
        )
        db.session.add(s)
        db.session.commit()
        # Adicionar um sintoma muda o modelo de escore -> congela uma nova versao
        # (snapshot de todos os sintomas, incluindo o novo). Nao mutar versoes antigas.
        nova = criar_nova_versao(
            criado_por_id=current_user.id,
            notas=f'Novo sintoma adicionado: {s.label}',
        )
        log_audit('CREATE', entidade='sintoma', id_entidade=s.id, detalhes={
            'chave': s.chave, 'label': s.label,
            'peso_masculino': s.peso_masculino, 'peso_feminino': s.peso_feminino,
            'ativo': s.ativo, 'nova_versao': nova.nome,
        })
        flash(f'Sintoma "{s.label}" cadastrado. Pesos congelados como {nova.nome}.', 'success')
        return redirect(url_for('sintoma.lista'))
    return render_template('sintomas/form.html', sintoma=None, acao='Novo Sintoma')


@sintoma_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    s = db.get_or_404(Sintoma, id)
    if request.method == 'POST':
        antes = {
            'label': s.label,
            'peso_masculino': s.peso_masculino,
            'peso_feminino': s.peso_feminino,
            'ativo': s.ativo,
        }
        s.label = request.form['label'].strip()
        s.peso_masculino = _parse_float(request.form.get('peso_masculino'))
        s.peso_feminino = _parse_float(request.form.get('peso_feminino'))
        s.descricao_clinica = request.form.get('descricao_clinica', '').strip() or None
        s.ativo = request.form.get('ativo') == 'on'
        depois = {
            'label': s.label,
            'peso_masculino': s.peso_masculino,
            'peso_feminino': s.peso_feminino,
            'ativo': s.ativo,
        }

        # Se mudou peso, exigir nota e snapshotar uma nova versao
        if _pesos_mudaram(antes, depois):
            notas = (request.form.get('notas_versao') or '').strip()
            if not notas:
                flash('Ao alterar pesos é obrigatório informar o motivo (nova versão).', 'danger')
                db.session.rollback()
                return render_template('sintomas/form.html', sintoma=s, acao='Editar Sintoma',
                                       exigir_notas=True)
            db.session.commit()  # aplica mudancas em Sintoma.peso_*
            nova = criar_nova_versao(criado_por_id=current_user.id, notas=notas)
            log_audit('UPDATE', entidade='sintoma', id_entidade=s.id, detalhes={
                'antes': antes, 'depois': depois,
                'nova_versao': nova.nome, 'notas': notas,
            })
            flash(f'Sintoma atualizado. Pesos congelados como {nova.nome}.', 'success')
        else:
            db.session.commit()
            log_audit('UPDATE', entidade='sintoma', id_entidade=s.id,
                      detalhes={'antes': antes, 'depois': depois})
            flash('Sintoma atualizado.', 'success')
        return redirect(url_for('sintoma.lista'))
    return render_template('sintomas/form.html', sintoma=s, acao='Editar Sintoma')


@sintoma_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle(id):
    s = db.get_or_404(Sintoma, id)
    s.ativo = not s.ativo
    db.session.commit()
    log_audit('UPDATE', entidade='sintoma', id_entidade=s.id,
              detalhes={'ativo': s.ativo})
    flash(f'Sintoma "{s.label}" {"ativado" if s.ativo else "desativado"}.', 'success')
    return redirect(url_for('sintoma.lista'))


@sintoma_bp.route('/versoes')
@login_required
@admin_required
def versoes():
    """Historico de versoes de pesos."""
    versoes = (VersaoPesos.query
               .order_by(VersaoPesos.criado_em.desc())
               .all())
    return render_template('sintomas/versoes.html', versoes=versoes)


@sintoma_bp.route('/versoes/<int:id>')
@login_required
@admin_required
def versao_detalhe(id):
    v = db.get_or_404(VersaoPesos, id)
    pesos = (SintomaPesoVersao.query
             .filter_by(id_versao=v.id)
             .join(Sintoma)
             .order_by(Sintoma.label)
             .all())
    return render_template('sintomas/versao_detalhe.html', versao=v, pesos=pesos)
