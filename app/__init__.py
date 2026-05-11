from flask import Flask
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from config import config
from app.models import db
from app.models.user import bcrypt

def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    # Debug: print DB URI and SECRET_KEY to stderr to diagnose encoding issues
    import sys
    try:
        sys.stderr.write(f"SQLALCHEMY_DATABASE_URI repr: {repr(app.config.get('SQLALCHEMY_DATABASE_URI'))}\n")
        sys.stderr.write(f"SECRET_KEY repr: {repr(app.config.get('SECRET_KEY'))}\n")
    except Exception:
        pass
    # Ensure client encoding is set to utf8 to avoid psycopg2 decode issues
    try:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if uri and 'client_encoding' not in uri:
            sep = '&' if '?' in uri else '?'
            app.config['SQLALCHEMY_DATABASE_URI'] = uri + f"{sep}client_encoding=utf8"
            sys.stderr.write(f"Adjusted SQLALCHEMY_DATABASE_URI repr: {repr(app.config.get('SQLALCHEMY_DATABASE_URI'))}\n")
    except Exception:
        pass
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt = JWTManager(app)
    
    # Register blueprints
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
    
    # Context processor for templates
    from app.utils.helpers import get_subject_image
    app.context_processor(lambda: dict(get_subject_image=get_subject_image))
    
    # Database initialization
    @app.before_request
    def init_database():
        if not hasattr(app, '_db_initialized'):
            db.create_all()
            
            # Initialize admin user
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
            
            # Initialize universities if empty
            from app.models.course import University
            if not University.query.first():
                from app.utils.helpers import init_universities
                init_universities()
            
            app._db_initialized = True
    
    # Create app context for database operations
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            import traceback
            sys.stderr.write("Exception during db.create_all():\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("Continuing without creating database tables (startup suppressed).\n")
    
    return app
