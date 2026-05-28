from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models.models import db, Usuario, UserPreference, SenhaFracaError
from controllers.audit import admin_required, log_audit

usuario_bp = Blueprint('usuario', __name__, url_prefix='/usuarios')


def _total_admins():
    return Usuario.query.filter_by(perfil='admin').count()


def _eh_ultimo_admin(usuario):
    return usuario.perfil == 'admin' and _total_admins() <= 1


@usuario_bp.route('/')
@login_required
@admin_required
def lista():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template('usuarios/lista.html',
                           usuarios=usuarios,
                           total_admins=_total_admins())


@usuario_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        if Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado.', 'danger')
            return render_template('usuarios/form.html', usuario=None,
                                   acao='Cadastrar Usuário', form_data=request.form)
        u = Usuario(
            nome=request.form['nome'].strip(),
            email=email,
            perfil=request.form.get('perfil', 'padrao')
        )
        try:
            u.set_senha(request.form['senha'])
        except SenhaFracaError as e:
            flash(str(e), 'danger')
            return render_template('usuarios/form.html', usuario=None,
                                   acao='Cadastrar Usuário', form_data=request.form)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserPreference(id_usuario=u.id))
        db.session.commit()
        log_audit('CREATE', entidade='usuario', id_entidade=u.id, detalhes={
            'nome': u.nome, 'email': u.email, 'perfil': u.perfil
        })
        flash('Usuário cadastrado com sucesso.', 'success')
        return redirect(url_for('usuario.lista'))
    return render_template('usuarios/form.html', usuario=None, acao='Cadastrar Usuário',
                           form_data=None)


@usuario_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    usuario = db.get_or_404(Usuario, id)
    if request.method == 'POST':
        antes = {'nome': usuario.nome, 'perfil': usuario.perfil}
        novo_perfil = request.form.get('perfil', 'padrao')
        if (usuario.perfil == 'admin' and novo_perfil != 'admin'
                and _eh_ultimo_admin(usuario)):
            flash('Não é possível remover o perfil admin do último administrador.', 'danger')
            return render_template('usuarios/form.html', usuario=usuario,
                                   acao='Salvar Alterações', form_data=request.form,
                                   eh_ultimo_admin=_eh_ultimo_admin(usuario))
        usuario.nome = request.form['nome'].strip()
        usuario.perfil = novo_perfil
        nova_senha = request.form.get('senha', '').strip()
        senha_alterada = bool(nova_senha)
        if senha_alterada:
            try:
                usuario.set_senha(nova_senha)
            except SenhaFracaError as e:
                flash(str(e), 'danger')
                return render_template('usuarios/form.html', usuario=usuario,
                                       acao='Salvar Alterações', form_data=request.form,
                                       eh_ultimo_admin=_eh_ultimo_admin(usuario))
        db.session.commit()
        log_audit('UPDATE', entidade='usuario', id_entidade=usuario.id, detalhes={
            'antes': antes,
            'depois': {'nome': usuario.nome, 'perfil': usuario.perfil},
            'senha_alterada': senha_alterada,
        })
        flash('Usuário atualizado.', 'success')
        return redirect(url_for('usuario.lista'))
    return render_template('usuarios/form.html', usuario=usuario, acao='Salvar Alterações',
                           eh_ultimo_admin=_eh_ultimo_admin(usuario))


@usuario_bp.route('/<int:id>/remover', methods=['POST'])
@login_required
@admin_required
def remover(id):
    usuario = db.get_or_404(Usuario, id)
    if usuario.id == current_user.id:
        flash('Você não pode remover sua própria conta.', 'danger')
        return redirect(url_for('usuario.lista'))
    if _eh_ultimo_admin(usuario):
        flash('Não é possível remover o último administrador do sistema.', 'danger')
        return redirect(url_for('usuario.lista'))
    info = {'nome': usuario.nome, 'email': usuario.email}
    db.session.delete(usuario)
    db.session.commit()
    log_audit('DELETE', entidade='usuario', id_entidade=id, detalhes=info)
    flash('Usuário removido.', 'success')
    return redirect(url_for('usuario.lista'))
