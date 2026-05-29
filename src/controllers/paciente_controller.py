import re
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from controllers.audit import log_audit
from models.models import Anamnese, DadosSocioeconomicos, Paciente, Responsavel, db

paciente_bp = Blueprint('paciente', __name__, url_prefix='/pacientes')


def _bool_sim_nao(valor):
    """'sim' -> True, 'nao' -> False, qualquer outro/vazio -> None (não respondido)."""
    v = (valor or '').strip()
    if v == 'sim':
        return True
    if v == 'nao':
        return False
    return None


def _tri(valor):
    """Normaliza campo ternário: 'sim'/'nao'/'nao_sei' ou None."""
    v = (valor or '').strip()
    return v if v in ('sim', 'nao', 'nao_sei') else None


def _salvar_anamnese(paciente, form):
    """Cria ou atualiza a Anamnese (contexto clínico/familiar) do paciente.

    Campos prefixados `an_` no form. Se nada foi respondido, não cria/altera.
    """
    ja_fez = _bool_sim_nao(form.get('an_ja_fez_exame_dna'))
    interesse = _bool_sim_nao(form.get('an_interesse_exame_pcr'))
    RESULTADOS = {
        'mutacao_completa',
        'pre_mutacao',
        'zona_gray',
        'mosaicismo',
        'negativo',
        'nao_sei',
    }
    resultado = (form.get('an_resultado_exame') or '').strip() or None
    if resultado not in RESULTADOS:
        resultado = None
    autismo = _bool_sim_nao(form.get('an_diagnostico_autismo'))
    irmaos = _bool_sim_nao(form.get('an_tem_irmaos'))
    fam_neuro = _tri(form.get('an_familia_neurodesenvolvimento'))
    fam_meno = _tri(form.get('an_familia_menopausa_precoce'))
    fam_ataxia = _tri(form.get('an_familia_ataxia_tremores'))

    valores = [
        ja_fez,
        interesse,
        resultado,
        autismo,
        irmaos,
        fam_neuro,
        fam_meno,
        fam_ataxia,
    ]
    if all(v is None for v in valores):
        return

    a = paciente.anamnese
    if a is None:
        a = Anamnese(id_paciente=paciente.id)
        db.session.add(a)
    a.ja_fez_exame_dna = ja_fez
    a.interesse_exame_pcr = interesse
    a.resultado_exame = resultado
    a.diagnostico_autismo = autismo
    a.tem_irmaos = irmaos
    a.familia_neurodesenvolvimento = fam_neuro
    a.familia_menopausa_precoce = fam_meno
    a.familia_ataxia_tremores = fam_ataxia


def _salvar_dados_socioeconomicos(paciente, form):
    """Cria ou atualiza DadosSocioeconomicos do paciente a partir do form.

    Se todos os campos socioecon forem vazios, nao cria/altera o registro.
    """
    renda = (form.get('se_renda_faixa') or '').strip() or None
    profissao = (form.get('se_profissao') or '').strip() or None
    escolaridade = (form.get('se_escolaridade') or '').strip() or None
    num_dep_raw = (form.get('se_num_dependentes') or '').strip()
    num_dep = int(num_dep_raw) if num_dep_raw.isdigit() else None

    algum_preenchido = any([renda, profissao, escolaridade, num_dep is not None])
    if not algum_preenchido:
        return

    dados = paciente.dados_socioeconomicos
    if dados is None:
        dados = DadosSocioeconomicos(id_paciente=paciente.id)
        db.session.add(dados)
    dados.renda_faixa = renda
    dados.profissao = profissao
    dados.escolaridade = escolaridade
    dados.num_dependentes = num_dep


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


def _resolver_responsavel(form):
    """Le do form e devolve o id do Responsavel (ou None se nao informado).

    Estrategia:
      - Se `responsavel_id` foi enviado (escolha via autocomplete), usa direto.
      - Se `resp_cpf` foi enviado e bate com Responsavel existente, reaproveita.
      - Senao, se `resp_nome` foi preenchido, cria novo Responsavel.
    """
    resp_id = (form.get('responsavel_id') or '').strip()
    if resp_id:
        existente = db.session.get(Responsavel, int(resp_id))
        if existente:
            return existente.id

    nome = (form.get('resp_nome') or '').strip()
    cpf_raw = (form.get('resp_cpf') or '').strip()
    cpf = _normalizar_cpf(cpf_raw) if cpf_raw else None

    if cpf:
        existente = Responsavel.query.filter_by(cpf=cpf).first()
        if existente:
            return existente.id

    if not nome:
        return None

    resp = Responsavel(
        nome=nome,
        cpf=cpf,
        email=(form.get('resp_email') or '').strip() or None,
        telefone=(form.get('resp_telefone') or '').strip() or None,
        parentesco=(form.get('resp_parentesco') or '').strip() or None,
    )
    db.session.add(resp)
    db.session.flush()
    return resp.id


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
    return f'{so_digitos[0:3]}.{so_digitos[3:6]}.{so_digitos[6:9]}-{so_digitos[9:11]}'


@paciente_bp.route('/responsaveis/buscar')
@login_required
def buscar_responsaveis():
    termo = (request.args.get('q') or '').strip()
    if not termo:
        return jsonify([])
    like = f'%{termo}%'
    rows = (
        Responsavel.query.filter(db.or_(Responsavel.nome.ilike(like), Responsavel.cpf == termo))
        .order_by(Responsavel.nome)
        .limit(10)
        .all()
    )
    return jsonify(
        [{'id': r.id, 'nome': r.nome, 'cpf': r.cpf, 'parentesco': r.parentesco} for r in rows]
    )


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
    pacientes = (
        Paciente.query.filter(Paciente.removido_em.isnot(None))
        .order_by(Paciente.removido_em.desc())
        .all()
    )
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
    log_audit(
        'DELETE',
        entidade='paciente',
        id_entidade=paciente.id,
        detalhes={'soft': True, 'nome': paciente.nome, 'cpf': paciente.cpf},
    )
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
    log_audit(
        'UPDATE',
        entidade='paciente',
        id_entidade=paciente.id,
        detalhes={'restaurado': True},
    )
    flash(f'Paciente "{paciente.nome}" restaurado.', 'success')
    return redirect(url_for('paciente.lixeira'))


@paciente_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        from datetime import datetime

        if not request.form.get('consentimento'):
            flash(
                'É necessário confirmar o consentimento do paciente/responsável (LGPD).',
                'danger',
            )
            return render_template(
                'pacientes/form.html',
                paciente=None,
                form_data=request.form,
                acao='Cadastrar Paciente',
            )
        nome = request.form['nome'].strip()
        cpf = _normalizar_cpf(request.form.get('cpf'))
        if not cpf:
            flash(
                'CPF inválido. Verifique os dígitos (algoritmo módulo 11) e o formato (000.000.000-00 ou 11 dígitos).',
                'danger',
            )
            return render_template(
                'pacientes/form.html',
                paciente=None,
                form_data=request.form,
                acao='Cadastrar Paciente',
            )
        if Paciente.query.filter_by(cpf=cpf).first():
            flash('Já existe um paciente com este CPF.', 'danger')
            return render_template(
                'pacientes/form.html',
                paciente=None,
                form_data=request.form,
                acao='Cadastrar Paciente',
            )
        sexo = request.form['sexo']
        data_nasc = date.fromisoformat(request.form['data_nascimento'])
        email_paciente = (request.form.get('email') or '').strip() or None
        id_responsavel = _resolver_responsavel(request.form)
        paciente = Paciente(
            nome=nome,
            cpf=cpf,
            sexo=sexo,
            data_nascimento=data_nasc,
            email=email_paciente,
            id_responsavel=id_responsavel,
            id_usuario=current_user.id,
            consentimento_dado_em=datetime.utcnow(),
        )
        db.session.add(paciente)
        db.session.flush()
        _salvar_dados_socioeconomicos(paciente, request.form)
        _salvar_anamnese(paciente, request.form)
        db.session.commit()
        log_audit(
            'CREATE',
            entidade='paciente',
            id_entidade=paciente.id,
            detalhes={
                'nome': nome,
                'cpf': cpf,
                'sexo': sexo,
                'data_nascimento': data_nasc.isoformat(),
                'email': email_paciente,
                'id_responsavel': id_responsavel,
            },
        )
        flash(f'Paciente {nome} cadastrado com sucesso.', 'success')
        return redirect(url_for('paciente.lista'))
    return render_template(
        'pacientes/form.html', paciente=None, form_data=None, acao='Cadastrar Paciente'
    )


@paciente_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    paciente = db.get_or_404(Paciente, id)
    _check_ownership(paciente)
    if request.method == 'POST':
        cpf = _normalizar_cpf(request.form.get('cpf'))
        if not cpf:
            flash(
                'CPF inválido. Verifique os dígitos (algoritmo módulo 11) e o formato (000.000.000-00 ou 11 dígitos).',
                'danger',
            )
            return render_template(
                'pacientes/form.html',
                paciente=paciente,
                form_data=request.form,
                acao='Salvar Alterações',
            )
        outro = Paciente.query.filter(Paciente.cpf == cpf, Paciente.id != paciente.id).first()
        if outro:
            flash('Já existe outro paciente com este CPF.', 'danger')
            return render_template(
                'pacientes/form.html',
                paciente=paciente,
                form_data=request.form,
                acao='Salvar Alterações',
            )

        antes = {
            'nome': paciente.nome,
            'cpf': paciente.cpf,
            'sexo': paciente.sexo,
            'data_nascimento': paciente.data_nascimento.isoformat(),
            'email': paciente.email,
            'id_responsavel': paciente.id_responsavel,
        }
        paciente.nome = request.form['nome'].strip()
        paciente.cpf = cpf
        paciente.sexo = request.form['sexo']
        paciente.data_nascimento = date.fromisoformat(request.form['data_nascimento'])
        paciente.email = (request.form.get('email') or '').strip() or None
        paciente.id_responsavel = _resolver_responsavel(request.form)
        _salvar_dados_socioeconomicos(paciente, request.form)
        _salvar_anamnese(paciente, request.form)
        db.session.commit()
        depois = {
            'nome': paciente.nome,
            'cpf': paciente.cpf,
            'sexo': paciente.sexo,
            'data_nascimento': paciente.data_nascimento.isoformat(),
            'email': paciente.email,
            'id_responsavel': paciente.id_responsavel,
        }
        log_audit(
            'UPDATE',
            entidade='paciente',
            id_entidade=paciente.id,
            detalhes={'antes': antes, 'depois': depois},
        )
        flash('Dados do paciente atualizados.', 'success')
        return redirect(url_for('paciente.detalhe', id=id))
    return render_template(
        'pacientes/form.html',
        paciente=paciente,
        form_data=None,
        acao='Salvar Alterações',
    )


@paciente_bp.route('/<int:id>')
@login_required
def detalhe(id):
    from controllers.scoring import get_limiar
    from models.models import Avaliacao

    paciente = db.get_or_404(Paciente, id)
    _check_ownership(paciente)
    avaliacoes = (
        Avaliacao.query.filter_by(id_paciente=id)
        .filter(Avaliacao.removido_em.is_(None))
        .order_by(Avaliacao.data.asc())
        .all()
    )
    serie = [
        {
            'data': a.data.strftime('%d/%m/%Y'),
            'score': round(a.score, 4),
            'recomendacao': a.recomendacao,
        }
        for a in avaliacoes
    ]
    return render_template(
        'pacientes/detalhe.html',
        paciente=paciente,
        avaliacoes=avaliacoes,
        serie=serie,
        limiar=get_limiar(paciente.sexo),
    )
