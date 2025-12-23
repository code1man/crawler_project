# -*- coding: utf-8 -*-
"""
鉴权服务 (Auth Service)
处理 Gitee OAuth 回调、本地注册/登录、JWT 签发
"""
import requests
from flask import current_app
from models import db, User
from utils.jwt_utils import generate_token


class AuthService:
    """鉴权服务类"""
    
    # ==================== 本地账号注册/登录 ====================
    
    @staticmethod
    def register_user(username, password):
        """
        本地注册新用户
        
        Args:
            username: 用户名
            password: 密码（明文，会自动加密）
            
        Returns:
            tuple: (user, error_message)
        """
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return None, '用户名已存在'
        
        # 密码长度验证
        if len(password) < 6:
            return None, '密码长度不能少于6位'
        
        # 创建新用户
        user = User(
            username=username,
            gitee_id=None,  # 本地用户没有 gitee_id
            avatar_url='',
            preferences={}
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        current_app.logger.info(f"[AuthService] 本地用户注册: {username}")
        return user, None
    
    @staticmethod
    def authenticate_local(username, password):
        """
        本地用户名密码验证
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            tuple: (user, error_message)
        """
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return None, '用户不存在'
        
        if not user.password_hash:
            return None, '该账号未设置密码，请使用 Gitee 登录'
        
        if not user.check_password(password):
            return None, '密码错误'
        
        current_app.logger.info(f"[AuthService] 本地用户登录: {username}")
        return user, None
    
    # ==================== Gitee OAuth ====================
    
    @staticmethod
    def get_gitee_auth_url():
        """
        获取 Gitee 授权页面 URL
        
        Returns:
            str: 授权 URL
        """
        params = {
            'client_id': current_app.config['GITEE_CLIENT_ID'],
            'redirect_uri': current_app.config['GITEE_REDIRECT_URI'],
            'response_type': 'code',
            'scope': 'user_info'
        }
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f"{current_app.config['GITEE_AUTHORIZE_URL']}?{query_string}"
    
    @staticmethod
    def exchange_code_for_token(code):
        """
        用授权码换取 access_token
        
        Args:
            code: 授权码
            
        Returns:
            str: access_token，失败返回 None
        """
        try:
            response = requests.post(
                current_app.config['GITEE_TOKEN_URL'],
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'client_id': current_app.config['GITEE_CLIENT_ID'],
                    'client_secret': current_app.config['GITEE_CLIENT_SECRET'],
                    'redirect_uri': current_app.config['GITEE_REDIRECT_URI'],
                },
                headers={'Accept': 'application/json'}
            )
            data = response.json()
            return data.get('access_token')
        except Exception as e:
            current_app.logger.error(f"[AuthService] 换取 token 失败: {e}")
            return None
    
    @staticmethod
    def get_gitee_user_info(access_token):
        """
        获取 Gitee 用户信息
        
        Args:
            access_token: Gitee access_token
            
        Returns:
            dict: 用户信息，失败返回 None
        """
        try:
            response = requests.get(
                current_app.config['GITEE_USER_URL'],
                params={'access_token': access_token}
            )
            return response.json()
        except Exception as e:
            current_app.logger.error(f"[AuthService] 获取用户信息失败: {e}")
            return None
    
    @staticmethod
    def login_or_register_gitee(gitee_user_info):
        """
        Gitee 登录或注册用户（根据 gitee_id 判断）
        
        Args:
            gitee_user_info: Gitee 返回的用户信息
            
        Returns:
            tuple: (user, is_new_user)
        """
        gitee_id = str(gitee_user_info.get('id'))
        username = gitee_user_info.get('name') or gitee_user_info.get('login', 'Unknown')
        avatar_url = gitee_user_info.get('avatar_url', '')
        
        user = User.query.filter_by(gitee_id=gitee_id).first()
        is_new = False
        
        if user is None:
            # 检查用户名是否已被占用，如果是则添加后缀
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}_{counter}"
                counter += 1
            
            # 新用户注册
            user = User(
                gitee_id=gitee_id,
                username=username,
                avatar_url=avatar_url,
                preferences={}
            )
            db.session.add(user)
            is_new = True
            current_app.logger.info(f"[AuthService] Gitee 新用户注册: {username}")
        else:
            # 老用户更新信息
            user.avatar_url = avatar_url
            current_app.logger.info(f"[AuthService] Gitee 用户登录: {username}")
        
        db.session.commit()
        return user, is_new
    
    # ==================== JWT ====================
    
    @staticmethod
    def generate_jwt(user):
        """
        为用户生成 JWT Token（包含账号完整状态）
        
        Args:
            user: User 模型实例
            
        Returns:
            str: JWT Token
        """
        # 状态：complete 表示已设置密码，incomplete 表示未设置
        status = 'complete' if user.is_profile_complete else 'incomplete'
        return generate_token(user.id, user.username, status)

