import re
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from models.models import db, Paciente
from controllers.audit import log_audit
from datetime import date

paciente_bp = Blueprint('paciente', __name__, url_prefix='/pacientes')


def _check_ownership(paciente, permitir_removido=False):
    if not current_user.is_admin and paciente.id_usuario != current_user.id:
        abort(403)
    if not permitir_removido and paciente.removido_em is not None:
        abort(404)


def _cpf_digitos_validos(digitos: str) -> bool:
    """Algoritmo modulo 11 dos dois digitos verificadores."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for i, fator_inicial in [(9, 10), (10, 11)]:
        soma = sum(int(digitos[j]) * (fator_inicial - j) for j in range(i))
        dv = (soma * 10) % 11
        if dv == 10:
            dv = 0
        if dv != int(digitos[i]):
            return False
    return True


def _normalizar_cpf(raw):
    """Aceita '000.000.000-00' ou '00000000000'. Retorna formatado ou None se invalido.

    Valida formato + algoritmo dos digitos verificadores. Rejeita CPFs triviais
    (todos iguais).
    """
    raw = (raw or '').strip()
    if not raw:
        return None
    so_digitos = re.sub(r'\D', '', raw)
    if not _cpf_digitos_validos(so_digitos):
        return None
    return f"{so_digitos[0:3]}.{so_digitos[3:6]}.{so_digitos[6:9]}-{so_digitos[9:11]}"


@paciente_bp.route('/')
@login_required
def lista():
    q = Paciente.query.filter(Paciente.removido_em.is_(None))
    if not current_user.is_admin:
        q = q.filter_by(id_usuario=current_user.id)
    pacientes = q.order_by(Paciente.nome).all()
    return render_template('pacientes/lista.html', pacientes=pacientes)


@paciente_bp.route('/lixeira')
@login_required
def lixeira():
    """Apenas admin ve a lixeira."""
    if not current_user.is_admin:
        abort(403)
    pacientes = (Paciente.query
                 .filter(Paciente.removido_em.isnot(None))
                 .order_by(Paciente.removido_em.desc())
                 .all())
    return render_template('pacientes/lixeira.html', pacientes=pacientes)


@paciente_bp.route('/<int:id>/remover', methods=['POST'])
@login_required
def remover(id):
    from datetime import datetime
    paciente = db.get_or_404(Paciente, id)
    _check_ownership(paciente, permitir_removido=True)
    if paciente.removido_em is not None:
        flash('Paciente já estava removido.', 'warning')
        return redirect(url_for('paciente.lista'))
    paciente.removido_em = datetime.utcnow()
    db.session.commit()
    log_audit('DELETE', entidade='paciente', id_entidade=paciente.id,
              detalhes={'soft': True, 'nome': paciente.nome, 'cpf': paciente.cpf})
    flash(f'Paciente "{paciente.nome}" removido.', 'success')
    return redirect(url_for('paciente.lista'))


@paciente_bp.route('/<int:id>/restaurar', methods=['POST'])
@login_required
def restaurar(id):
    if not current_user.is_admin:
        abort(403)
    paciente = db.get_or_404(Paciente, id)
    if paciente.removido_em is None:
        flash('Paciente já estava ativo.', 'warning')
        return redirect(url_for('paciente.lixeira'))
    paciente.removido_em = None
    db.session.commit()
    log_audit('UPDATE', entidade='paciente', id_entidade=paciente.id,
              detalhes={'restaurado': True})
    flash(f'Paciente "{paciente.nome}" restaurado.', 'success')
    return redirect(url_for('paciente.lixeira'))


@paciente_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        from datetime import datetime
        if not request.form.get('consentimento'):
            flash('É necessário confirmar o consentimento do paciente/responsável (LGPD).', 'danger')
            return render_template('pacientes/form.html', paciente=None, form_data=request.form, acao='Cadastrar Paciente')
        nome = request.form['nome'].strip()
        cpf = _normalizar_cpf(request.form.get('cpf'))
        if not cpf:
            flash('CPF inválido. Verifique os dígitos (algoritmo módulo 11) e o formato (000.000.000-00 ou 11 dígitos).', 'danger')
            return render_template('pacientes/form.html', paciente=None, form_data=request.form, acao='Cadastrar Paciente')
        if Paciente.query.filter_by(cpf=cpf).first():
            flash('Já existe um paciente com este CPF.', 'danger')
            return render_template('pacientes/form.html', paciente=None, form_data=request.form, acao='Cadastrar Paciente')
        sexo = request.form['sexo']
        data_nasc = date.fromisoformat(request.form['data_nascimento'])
        responsavel = request.form.get('responsavel', '').strip()
        paciente = Paciente(
            nome=nome, cpf=cpf, sexo=sexo, data_nascimento=data_nasc,
            responsavel=responsavel, id_usuario=current_user.id,
            consentimento_dado_em=datetime.utcnow(),
        )
        db.session.add(paciente)
        db.session.commit()
        log_audit('CREATE', entidade='paciente', id_entidade=paciente.id, detalhes={
            'nome': nome, 'cpf': cpf, 'sexo': sexo,
            'data_nascimento': data_nasc.isoformat(),
        })
        flash(f'Paciente {nome} cadastrado com sucesso.', 'success')
        return redirect(url_for('paciente.lista'))
    return render_template('pacientes/form.html', paciente=None, form_data=None, acao='Cadastrar Paciente')


@paciente_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    paciente = db.get_or_404(Paciente, id)
    _check_ownership(paciente)
    if request.method == 'POST':
        cpf = _normalizar_cpf(request.form.get('cpf'))
        if not cpf:
            flash('CPF inválido. Verifique os dígitos (algoritmo módulo 11) e o formato (000.000.000-00 ou 11 dígitos).', 'danger')
            return render_template('pacientes/form.html', paciente=paciente, form_data=request.form, acao='Salvar Alterações')
        outro = Paciente.query.filter(Paciente.cpf == cpf, Paciente.id != paciente.id).first()
        if outro:
            flash('Já existe outro paciente com este CPF.', 'danger')
            return render_template('pacientes/form.html', paciente=paciente, form_data=request.form, acao='Salvar Alterações')

        antes = {
            'nome': paciente.nome, 'cpf': paciente.cpf, 'sexo': paciente.sexo,
            'data_nascimento': paciente.data_nascimento.isoformat(),
            'responsavel': paciente.responsavel,
        }
        paciente.nome = request.form['nome'].strip()
        paciente.cpf = cpf
        paciente.sexo = request.form['sexo']
        paciente.data_nascimento = date.fromisoformat(request.form['data_nascimento'])
        paciente.responsavel = request.form.get('responsavel', '').strip()
        db.session.commit()
        depois = {
            'nome': paciente.nome, 'cpf': paciente.cpf, 'sexo': paciente.sexo,
            'data_nascimento': paciente.data_nascimento.isoformat(),
            'responsavel': paciente.responsavel,
        }
        log_audit('UPDATE', entidade='paciente', id_entidade=paciente.id,
                  detalhes={'antes': antes, 'depois': depois})
        flash('Dados do paciente atualizados.', 'success')
        return redirect(url_for('paciente.detalhe', id=id))
    return render_template('pacientes/form.html', paciente=paciente, form_data=None, acao='Salvar Alterações')


@paciente_bp.route('/<int:id>')
@login_required
def detalhe(id):
    from models.models import Avaliacao
    from controllers.scoring import get_limiar
    paciente = db.get_or_404(Paciente, id)
    _check_ownership(paciente)
    avaliacoes = (Avaliacao.query
                  .filter_by(id_paciente=id)
                  .filter(Avaliacao.removido_em.is_(None))
                  .order_by(Avaliacao.data.asc())
                  .all())
    serie = [{'data': a.data.strftime('%d/%m/%Y'),
              'score': round(a.score, 4),
              'recomendacao': a.recomendacao}
             for a in avaliacoes]
    return render_template('pacientes/detalhe.html',
                           paciente=paciente,
                           avaliacoes=avaliacoes,
                           serie=serie,
                           limiar=get_limiar(paciente.sexo))
