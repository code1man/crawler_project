# -*- coding: utf-8 -*-
"""
Gitee OAuth 认证蓝图
处理第三方登录的授权和回调，使用 Session 存储用户状态
"""
import requests
from flask import Blueprint, redirect, request, session
from urllib.parse import urlencode, quote
from models import db, User

# 创建认证蓝图
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Gitee OAuth 配置
GITEE_CONFIG = {
    'client_id': '10ff318a50ae7b65c1b556217e2247ef754f8180e528ff3af5885d41bdac5d7b',
    'client_secret': '9f833bc7a590ffede493573d0a6951dc3a226f2714424e601bea552f9866c5e2',
    'redirect_uri': 'http://localhost:5000/auth/gitee/callback',
    'authorize_url': 'https://gitee.com/oauth/authorize',
    'token_url': 'https://gitee.com/oauth/token',
    'user_url': 'https://gitee.com/api/v5/user',
}


@auth_bp.route('/gitee/login')
def gitee_login():
    """
    重定向用户到 Gitee 授权页面
    """
    params = {
        'client_id': GITEE_CONFIG['client_id'],
        'redirect_uri': GITEE_CONFIG['redirect_uri'],
        'response_type': 'code',
        'scope': 'user_info',
    }
    auth_url = f"{GITEE_CONFIG['authorize_url']}?{urlencode(params)}"
    return redirect(auth_url)

@auth_bp.route('/gitee/callback')
def gitee_callback():
    """
    处理 Gitee OAuth 回调
    1. 用 code 换取 access_token
    2. 用 token 获取用户信息
    3. 在数据库中创建或更新用户
    4. 存入 Session 并重定向到主页
    """
    code = request.args.get('code')
    
    if not code:
        return redirect('/login?error=no_code')
    
    try:
        # Step 1: 用 code 换取 access_token
        token_response = requests.post(
            GITEE_CONFIG['token_url'],
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': GITEE_CONFIG['client_id'],
                'client_secret': GITEE_CONFIG['client_secret'],
                'redirect_uri': GITEE_CONFIG['redirect_uri'],
            },
            headers={'Accept': 'application/json'}
        )
        token_data = token_response.json()
        
        if 'access_token' not in token_data:
            error_msg = token_data.get('error_description', 'token_error')
            return redirect(f'/login?error={quote(error_msg)}')
        
        access_token = token_data['access_token']
        
        # Step 2: 用 token 获取用户信息
        user_response = requests.get(
            GITEE_CONFIG['user_url'],
            params={'access_token': access_token}
        )
        user_data = user_response.json()
        
        gitee_id = str(user_data.get('id'))
        username = user_data.get('name') or user_data.get('login', 'Unknown')
        avatar_url = user_data.get('avatar_url', '')
        
        # Step 3: 查询或创建用户
        user = User.query.filter_by(gitee_id=gitee_id).first()
        
        if user is None:
            # 新用户，创建记录
            user = User(
                gitee_id=gitee_id,
                username=username,
                avatar_url=avatar_url
            )
            db.session.add(user)
            print(f"[OAuth] 新用户注册: {username} (gitee_id: {gitee_id})")
        else:
            # 已存在用户，更新信息
            user.username = username
            user.avatar_url = avatar_url
            print(f"[OAuth] 用户登录: {username} (gitee_id: {gitee_id})")
        
        db.session.commit()
        
        # Step 4: 存入 Session
        session['user_id'] = user.id
        session['username'] = user.username
        session['avatar_url'] = user.avatar_url
        session['gitee_id'] = user.gitee_id
        
        print(f"[OAuth] Session 已创建: user_id={user.id}")
        
        # 重定向到主页
        return redirect('/')
        
    except Exception as e:
        print(f"[OAuth] 错误: {str(e)}")
        return redirect(f'/login?error={quote(str(e))}')
