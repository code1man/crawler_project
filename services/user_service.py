# -*- coding: utf-8 -*-
"""
用户服务 (User Service)
管理用户信息、偏好设置
"""
from models import db, User


class UserService:
    """用户服务类"""
    
    @staticmethod
    def get_user_by_id(user_id):
        """
        根据 ID 获取用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            User: 用户对象
        """
        return User.query.get(user_id)
    
    @staticmethod
    def get_user_profile(user_id):
        """
        获取用户资料
        
        Args:
            user_id: 用户 ID
            
        Returns:
            dict: 用户资料
        """
        user = User.query.get(user_id)
        if user:
            return user.to_dict()
        return None
    
    @staticmethod
    def get_preferences(user_id):
        """
        获取用户偏好设置
        
        Args:
            user_id: 用户 ID
            
        Returns:
            dict: 偏好设置
        """
        user = User.query.get(user_id)
        if user:
            return user.preferences or {}
        return {}
    
    @staticmethod
    def update_preferences(user_id, preferences):
        """
        更新用户偏好设置
        
        Args:
            user_id: 用户 ID
            preferences: 新的偏好设置 dict
            
        Returns:
            dict: 更新后的偏好设置
        """
        user = User.query.get(user_id)
        if user:
            # 合并更新偏好设置
            current_prefs = user.preferences or {}
            current_prefs.update(preferences)
            user.preferences = current_prefs
            db.session.commit()
            return user.preferences
        return None
    
    @staticmethod
    def update_profile(user_id, **kwargs):
        """
        更新用户资料
        
        Args:
            user_id: 用户 ID
            **kwargs: 要更新的字段
            
        Returns:
            User: 更新后的用户对象
        """
        user = User.query.get(user_id)
        if user:
            allowed_fields = ['username', 'avatar_url']
            for key, value in kwargs.items():
                if key in allowed_fields and value is not None:
                    setattr(user, key, value)
            db.session.commit()
            return user
        return None
    
    @staticmethod
    def set_user_password(user_id, new_password):
        """
        为用户设置密码（Gitee 用户补全信息）
        
        Args:
            user_id: 用户 ID
            new_password: 新密码
            
        Returns:
            tuple: (success, error_message)
        """
        if len(new_password) < 6:
            return False, '密码长度不能少于6位'
        
        user = User.query.get(user_id)
        if not user:
            return False, '用户不存在'
        
        user.set_password(new_password)
        db.session.commit()
        
        return True, None
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """
        修改密码（需验证旧密码）
        
        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            tuple: (success, error_message)
        """
        user = User.query.get(user_id)
        if not user:
            return False, '用户不存在'
        
        # 验证旧密码
        if not user.check_password(old_password):
            return False, '旧密码错误'
        
        # 验证新密码长度
        if len(new_password) < 6:
            return False, '新密码长度不能少于6位'
        
        user.set_password(new_password)
        db.session.commit()
        
        return True, None
    
    @staticmethod
    def update_username(user_id, new_username):
        """
        修改用户名
        
        Args:
            user_id: 用户 ID
            new_username: 新用户名
            
        Returns:
            tuple: (success, error_message)
        """
        if not new_username or len(new_username.strip()) == 0:
            return False, '用户名不能为空'
        
        new_username = new_username.strip()
        
        # 检查用户名是否已被占用
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != user_id:
            return False, '用户名已被占用'
        
        user = User.query.get(user_id)
        if not user:
            return False, '用户不存在'
        
        user.username = new_username
        db.session.commit()
        
        return True, None


