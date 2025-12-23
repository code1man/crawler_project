# -*- coding: utf-8 -*-
"""
鉴权 API (Auth API)
处理 OAuth 登录、本地注册/登录
"""
from flask import redirect, request
from flask_restx import Namespace, Resource, fields
from services.auth_service import AuthService
from services.audit_service import AuditService

# 创建命名空间
auth_ns = Namespace('auth', description='鉴权相关接口')

# ==================== 请求/响应模型 ====================

register_request = auth_ns.model('RegisterRequest', {
    'username': fields.String(required=True, description='用户名'),
    'password': fields.String(required=True, description='密码（最少6位）')
})

login_request = auth_ns.model('LoginRequest', {
    'username': fields.String(required=True, description='用户名'),
    'password': fields.String(required=True, description='密码')
})

token_response = auth_ns.model('TokenResponse', {
    'code': fields.Integer(description='状态码'),
    'message': fields.String(description='消息'),
    'data': fields.Nested(auth_ns.model('TokenData', {
        'token': fields.String(description='JWT Token'),
        'user': fields.Raw(description='用户信息'),
        'status': fields.String(description='账号状态 complete/incomplete')
    }))
})

error_response = auth_ns.model('ErrorResponse', {
    'code': fields.Integer(description='错误码'),
    'message': fields.String(description='错误消息')
})


# ==================== 本地账号注册/登录 ====================

@auth_ns.route('/register')
class Register(Resource):
    @auth_ns.doc('register')
    @auth_ns.expect(register_request)
    @auth_ns.marshal_with(token_response)
    def post(self):
        """
        用户注册
        
        注册成功后自动登录，返回 JWT Token
        """
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username:
            return {'code': 400, 'message': '用户名不能为空', 'data': None}, 400
        
        if not password:
            return {'code': 400, 'message': '密码不能为空', 'data': None}, 400
        
        # 注册
        user, error = AuthService.register_user(username, password)
        if error:
            return {'code': 400, 'message': error, 'data': None}, 400
        
        # 记录登录日志
        AuditService.log_login(user.id, login_type='local')
        
        # 生成 JWT
        jwt_token = AuthService.generate_jwt(user)
        
        return {
            'code': 200,
            'message': '注册成功',
            'data': {
                'token': jwt_token,
                'user': user.to_dict(),
                'status': 'complete'
            }
        }


@auth_ns.route('/login/local')
class LocalLogin(Resource):
    @auth_ns.doc('local_login')
    @auth_ns.expect(login_request)
    @auth_ns.marshal_with(token_response)
    def post(self):
        """
        用户名密码登录
        
        返回 JWT Token
        """
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return {'code': 400, 'message': '用户名和密码不能为空', 'data': None}, 400
        
        # 验证
        user, error = AuthService.authenticate_local(username, password)
        if error:
            return {'code': 401, 'message': error, 'data': None}, 401
        
        # 记录登录日志
        AuditService.log_login(user.id, login_type='local')
        
        # 生成 JWT
        jwt_token = AuthService.generate_jwt(user)
        
        return {
            'code': 200,
            'message': '登录成功',
            'data': {
                'token': jwt_token,
                'user': user.to_dict(),
                'status': 'complete' if user.is_profile_complete else 'incomplete'
            }
        }


# ==================== Gitee OAuth ====================

@auth_ns.route('/gitee/login')
class GiteeLogin(Resource):
    @auth_ns.doc('gitee_login', 
                 responses={302: '重定向到 Gitee 授权页'})
    def get(self):
        """跳转到 Gitee 授权页面"""
        auth_url = AuthService.get_gitee_auth_url()
        return redirect(auth_url)


@auth_ns.route('/gitee/callback')
class GiteeCallback(Resource):
    @auth_ns.doc('gitee_callback',
                 params={'code': 'Gitee 授权码'},
                 responses={
                     200: ('登录成功', token_response),
                     400: ('授权失败', error_response)
                 })
    def get(self):
        """
        处理 Gitee OAuth 回调
        
        返回 JWT Token 和用户信息
        """
        code = request.args.get('code')
        
        if not code:
            return redirect('/login?error=no_code')
        
        # 1. 换取 access_token
        access_token = AuthService.exchange_code_for_token(code)
        if not access_token:
            return redirect('/login?error=token_exchange_failed')
        
        # 2. 获取用户信息
        gitee_user = AuthService.get_gitee_user_info(access_token)
        if not gitee_user:
            return redirect('/login?error=user_info_failed')
        
        # 3. 登录或注册（使用新方法名）
        user, is_new = AuthService.login_or_register_gitee(gitee_user)
        
        # 4. 记录登录日志
        AuditService.log_login(user.id, login_type='gitee')
        
        # 5. 生成 JWT（包含 status）
        jwt_token = AuthService.generate_jwt(user)
        
        # 6. 判断是否需要完善信息
        status = 'complete' if user.is_profile_complete else 'incomplete'
        
        # 7. 重定向到前端，携带 token 和 status
        from urllib.parse import quote
        return redirect(f'/?token={jwt_token}&username={quote(user.username)}&avatar_url={quote(user.avatar_url or "")}&status={status}')

