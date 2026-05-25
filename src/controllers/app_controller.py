import os
from flask import Flask, render_template
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from models.models import db, Usuario, UserPreference, Sintoma
from controllers.seed_data import SINTOMAS_INICIAIS


migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_overrides=None):
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'views'),
                static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'))

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-mude-em-producao')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'postgresql://sxf_user:sxf_pass@localhost:5432/sxf_db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    from controllers.auth_controller import auth_bp
    from controllers.paciente_controller import paciente_bp
    from controllers.avaliacao_controller import avaliacao_bp
    from controllers.relatorio_controller import relatorio_bp
    from controllers.usuario_controller import usuario_bp
    from controllers.sintoma_controller import sintoma_bp
    from controllers.logs_controller import logs_bp
    from controllers.reset_senha_controller import reset_bp
    from controllers.qr_cadastro_controller import qr_bp, publico_bp

    for bp in [auth_bp, paciente_bp, avaliacao_bp, relatorio_bp,
               usuario_bp, sintoma_bp, logs_bp, reset_bp,
               qr_bp, publico_bp]:
        app.register_blueprint(bp)

    @app.route('/health')
    def health():
        from sqlalchemy import text
        try:
            db.session.execute(text('SELECT 1'))
            return {'status': 'ok'}, 200
        except Exception as e:
            return {'status': 'error', 'detail': str(e)}, 503

    # Disponibiliza tema atual no template
    @app.context_processor
    def inject_tema():
        if current_user.is_authenticated and current_user.preferencias:
            return {'tema_atual': current_user.preferencias.tema}
        return {'tema_atual': 'claro'}

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    with app.app_context():
        db.create_all()
        from controllers.seed_data import (migrar_schema_auditoria,
                                           migrar_responsavel_string_para_tabela)
        migrar_schema_auditoria()
        _seed_sintomas()
        _seed_admin()
        _seed_user_preferences()
        _seed_versao_pesos_inicial()
        migrar_responsavel_string_para_tabela()

    return app


def _seed_versao_pesos_inicial():
    from controllers.versoes_pesos import criar_versao_inicial
    admin = Usuario.query.filter_by(email='admin@admin.com').first()
    criar_versao_inicial(criado_por_id=admin.id if admin else None)


def _seed_sintomas():
    if Sintoma.query.count() == 0:
        for s in SINTOMAS_INICIAIS:
            db.session.add(Sintoma(**s, ativo=True))
        db.session.commit()
        return
    # Sintomas ja existem: completar a `descricao_clinica` se estiver vazia
    # (preserva edicoes manuais do admin).
    for s in SINTOMAS_INICIAIS:
        existente = Sintoma.query.filter_by(chave=s['chave']).first()
        if existente and not existente.descricao_clinica:
            existente.descricao_clinica = s.get('descricao_clinica')
    db.session.commit()


def _seed_admin():
    if not Usuario.query.filter_by(email='admin@admin.com').first():
        admin = Usuario(nome='Administrador', email='admin@admin.com', perfil='admin')
        admin.set_senha('admin123')
        db.session.add(admin)
        db.session.commit()


def _seed_user_preferences():
    """Garante que todo usuario tenha uma row em user_preferences."""
    usuarios_sem_prefs = Usuario.query.filter(~Usuario.preferencias.has()).all()
    for u in usuarios_sem_prefs:
        db.session.add(UserPreference(id_usuario=u.id, tema='claro'))
    if usuarios_sem_prefs:
        db.session.commit()
