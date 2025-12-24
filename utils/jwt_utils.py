# -*- coding: utf-8 -*-
"""
JWT 工具类 - 签发、校验 Token
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g


def generate_token(user_id, username, status='complete'):
    """
    生成 JWT Token
    
    Args:
        user_id: 用户 ID
        username: 用户名
        status: 账号状态 complete/incomplete
        
    Returns:
        str: JWT Token
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'status': status,  # 账号完整状态
        'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        'iat': datetime.utcnow()
    }
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM']
    )
    return token


def decode_token(token):
    """
    解码 JWT Token
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        dict: payload 数据，失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token 已过期
    except jwt.InvalidTokenError:
        return None  # 无效 Token


def token_required(f):
    """
    JWT Token 校验装饰器
    需要在请求 Header 中携带: Authorization: Bearer <token>
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从 Header 获取 Token
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            return jsonify({
                'code': 401,
                'message': '缺少访问令牌，请先登录'
            }), 401
        
        # 验证 Token
        payload = decode_token(token)
        if not payload:
            return jsonify({
                'code': 401,
                'message': '令牌无效或已过期，请重新登录'
            }), 401
        
        # 将用户信息存入 g 对象，供后续使用
        g.current_user_id = payload.get('user_id')
        g.current_username = payload.get('username')
        g.current_user_status = payload.get('status', 'complete')
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user_id():
    """获取当前登录用户 ID"""
    return getattr(g, 'current_user_id', None)


def get_current_username():
    """获取当前登录用户名"""
    return getattr(g, 'current_username', None)
