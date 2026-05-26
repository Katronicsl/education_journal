from flask import Flask
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from config import config
from app.models import db
from app.models.user import bcrypt

def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    
    app.config.from_object(config[config_name])
    import sys
    try:
        sys.stderr.write(f"SQLALCHEMY_DATABASE_URI repr: {repr(app.config.get('SQLALCHEMY_DATABASE_URI'))}\n")
        sys.stderr.write(f"SECRET_KEY repr: {repr(app.config.get('SECRET_KEY'))}\n")
    except Exception:
        pass
    try:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if uri and 'client_encoding' not in uri:
            sep = '&' if '?' in uri else '?'
            app.config['SQLALCHEMY_DATABASE_URI'] = uri + f"{sep}client_encoding=utf8"
            sys.stderr.write(f"Adjusted SQLALCHEMY_DATABASE_URI repr: {repr(app.config.get('SQLALCHEMY_DATABASE_URI'))}\n")
    except Exception:
        pass
    
    db.init_app(app)
    bcrypt.init_app(app)
    jwt = JWTManager(app)
    
    from app.controllers.auth import auth_bp
    from app.controllers.main import main_bp
    from app.controllers.student import student_bp
    from app.controllers.teacher import teacher_bp
    from app.controllers.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)
    
    from app.utils.helpers import get_subject_image
    app.context_processor(lambda: dict(get_subject_image=get_subject_image))
    
    @app.before_request
    def init_database():
        if not hasattr(app, '_db_initialized'):
            db.create_all()
            
            from app.models.user import User
            if not User.query.filter_by(role='admin').first():
                admin = User(
                    last_name='Admin',
                    first_name='Super',
                    middle_name='User',
                    email='admin@example.com',
                    password_hash=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
            
            app._db_initialized = True
    
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            import traceback
            sys.stderr.write("Exception during db.create_all():\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("Continuing without creating database tables (startup suppressed).\n")
    
    return app
