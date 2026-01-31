import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-secreta-super-segura-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///freefire_store.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/images/products'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    