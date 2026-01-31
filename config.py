import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-secreta-super-segura-2024'
    SQLALCHEMY_DATABASE_URI = 'postgresql://neondb_owner:npg_NdD0h6CyXqTK@ep-old-truth-ah84vn8i-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/images/products'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    
