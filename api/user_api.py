# -*- coding: utf-8 -*-
"""
用户 API (User API)
用户资料和偏好设置管理
"""
from flask import request
from flask_restx import Namespace, Resource, fields
from services.user_service import UserService
from utils.jwt_utils import token_required, get_current_user_id

# 创建命名空间
user_ns = Namespace('user', description='用户相关接口')

# 定义模型
user_model = user_ns.model('User', {
    'id': fields.Integer(description='用户ID'),
    'gitee_id': fields.String(description='Gitee ID'),
    'username': fields.String(description='用户名'),
    'avatar_url': fields.String(description='头像URL'),
    'preferences': fields.Raw(description='偏好设置'),
    'created_at': fields.String(description='创建时间')
})

preferences_model = user_ns.model('Preferences', {
    'default_keywords': fields.List(fields.String, description='默认爬虫关键词'),
    'default_platform': fields.String(description='默认平台'),
    'page_size': fields.Integer(description='每页显示数量')
})

response_model = user_ns.model('Response', {
    'code': fields.Integer(description='状态码'),
    'message': fields.String(description='消息'),
    'data': fields.Raw(description='数据')
})


@user_ns.route('/profile')
class UserProfile(Resource):
    @user_ns.doc('get_profile', security='Bearer')
    @user_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取当前用户资料"""
        user_id = get_current_user_id()
        profile = UserService.get_user_profile(user_id)
        
        if profile:
            return {'code': 200, 'message': 'success', 'data': profile}
        return {'code': 404, 'message': '用户不存在', 'data': None}, 404


@user_ns.route('/preferences')
class UserPreferences(Resource):
    @user_ns.doc('get_preferences', security='Bearer')
    @user_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取用户偏好设置"""
        user_id = get_current_user_id()
        prefs = UserService.get_preferences(user_id)
        return {'code': 200, 'message': 'success', 'data': prefs}
    
    @user_ns.doc('update_preferences', security='Bearer')
    @user_ns.expect(preferences_model)
    @user_ns.marshal_with(response_model)
    @token_required
    def put(self):
        """更新用户偏好设置"""
        user_id = get_current_user_id()
        data = request.json or {}
        
        updated = UserService.update_preferences(user_id, data)
        if updated is not None:
            return {'code': 200, 'message': '偏好设置已更新', 'data': updated}
        return {'code': 404, 'message': '用户不存在', 'data': None}, 404


# 密码设置模型
password_model = user_ns.model('PasswordModel', {
    'password': fields.String(required=True, description='新密码（最少6位）')
})


@user_ns.route('/complete-profile')
class CompleteProfile(Resource):
    @user_ns.doc('complete_profile', security='Bearer')
    @user_ns.expect(password_model)
    @user_ns.marshal_with(response_model)
    @token_required
    def post(self):
        """
        完善用户信息（设置密码）
        
        Gitee 用户首次登录后需要设置密码
        """
        user_id = get_current_user_id()
        data = request.json or {}
        password = data.get('password', '')
        
        if not password:
            return {'code': 400, 'message': '密码不能为空', 'data': None}, 400
        
        success, error = UserService.set_user_password(user_id, password)
        
        if not success:
            return {'code': 400, 'message': error, 'data': None}, 400
        
        # 生成新的 JWT（状态更新为 complete）
        from services.auth_service import AuthService
        user = UserService.get_user_by_id(user_id)
        new_token = AuthService.generate_jwt(user)
        
        return {
            'code': 200,
            'message': '密码设置成功',
            'data': {
                'token': new_token,
                'user': user.to_dict()
            }
        }


# 修改密码模型
change_password_model = user_ns.model('ChangePasswordModel', {
    'old_password': fields.String(required=True, description='旧密码'),
    'new_password': fields.String(required=True, description='新密码（最少6位）')
})


@user_ns.route('/change-password')
class ChangePassword(Resource):
    @user_ns.doc('change_password', security='Bearer')
    @user_ns.expect(change_password_model)
    @user_ns.marshal_with(response_model)
    @token_required
    def post(self):
        """
        修改密码（需验证旧密码）
        """
        user_id = get_current_user_id()
        data = request.json or {}
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return {'code': 400, 'message': '请填写完整信息', 'data': None}, 400
        
        success, error = UserService.change_password(user_id, old_password, new_password)
        
        if not success:
            return {'code': 400, 'message': error, 'data': None}, 400
        
        return {'code': 200, 'message': '密码修改成功', 'data': None}


# 修改用户名模型
update_username_model = user_ns.model('UpdateUsernameModel', {
    'username': fields.String(required=True, description='新用户名')
})


@user_ns.route('/update-username')
class UpdateUsername(Resource):
    @user_ns.doc('update_username', security='Bearer')
    @user_ns.expect(update_username_model)
    @user_ns.marshal_with(response_model)
    @token_required
    def post(self):
        """
        修改用户名
        """
        user_id = get_current_user_id()
        data = request.json or {}
        new_username = data.get('username', '')
        
        if not new_username:
            return {'code': 400, 'message': '用户名不能为空', 'data': None}, 400
        
        success, error = UserService.update_username(user_id, new_username)
        
        if not success:
            return {'code': 400, 'message': error, 'data': None}, 400
        
        # 生成新 JWT（用户名更新）
        from services.auth_service import AuthService
        user = UserService.get_user_by_id(user_id)
        new_token = AuthService.generate_jwt(user)
        
        return {
            'code': 200,
            'message': '用户名修改成功',
            'data': {
                'token': new_token,
                'user': user.to_dict()
            }
        }

