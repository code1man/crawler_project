# -*- coding: utf-8 -*-
"""
API 层初始化 - Flask-RESTX Swagger 配置
"""
from flask_restx import Api

# 创建 API 实例，配置 Swagger 文档
# 注意：prefix 必须设置，否则会接管根路由
api = Api(
    title='舆情分析系统 API',
    version='1.0',
    description='基于 Flask-RESTX 的 SOA 架构 API 文档',
    doc='/api/docs',  # Swagger UI 路径
    prefix='/api',    # API 路径前缀，避免接管根路由
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'JWT Token，格式：Bearer <token>'
        }
    },
    security='Bearer'
)
