# -*- coding: utf-8 -*-
"""
应用配置文件
"""
import os
from datetime import timedelta


class Config:
    """基础配置"""
    # Flask 密钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # JWT 配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)  # 2 小时过期
    JWT_ALGORITHM = 'HS256'
    
    # MySQL 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:12345678@localhost:3306/my_demo'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Gitee OAuth 配置
    GITEE_CLIENT_ID = '10ff318a50ae7b65c1b556217e2247ef754f8180e528ff3af5885d41bdac5d7b'
    GITEE_CLIENT_SECRET = '9f833bc7a590ffede493573d0a6951dc3a226f2714424e601bea552f9866c5e2'
    GITEE_REDIRECT_URI = 'http://localhost:5000/auth/gitee/callback'
    GITEE_AUTHORIZE_URL = 'https://gitee.com/oauth/authorize'
    GITEE_TOKEN_URL = 'https://gitee.com/oauth/token'
    GITEE_USER_URL = 'https://gitee.com/api/v5/user'
    
    # 头像上传配置
    AVATAR_UPLOAD_FOLDER = 'static/avatars'
    AVATAR_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB

    COZE_API_TOKEN = 'pat_VImIWmkJP7ggaday9BY9AOorq0FAUYvRATsQdf7tEFD7xJFdB5gIiMoz8jRMyMkn'
    WORKFLOW_ID = '7581414272291733544'

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
