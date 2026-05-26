import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ВАШ_СЕКРЕТНЫЙ_КЛЮЧ_ЗДЕСЬ'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'ВАШ_JWT_СЕКРЕТ_ЗДЕСЬ'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_COOKIE_CSRF_PROTECT = False


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'client_encoding': 'utf8'}
    }


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'client_encoding': 'utf8'}
    }




config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
