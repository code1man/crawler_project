from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CSVStorage(Base):
    __tablename__ = 'csv_storage'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cleaned_data = Column(String(512), nullable=False)
    final_data = Column(String(512), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


# -*- coding: utf-8 -*-
"""
数据库模型定义（SOA 架构扩展版）
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """用户模型 - 支持 Gitee OAuth 和本地账号登录"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    gitee_id = db.Column(db.String(50), unique=True, nullable=True, index=True, comment='Gitee 用户ID')
    username = db.Column(db.String(100), unique=True, nullable=False, comment='用户昵称')
    avatar_url = db.Column(db.String(500), comment='用户头像URL')
    password_hash = db.Column(db.String(256), nullable=True, comment='密码哈希（本地登录用）')
    preferences = db.Column(db.JSON, default=dict, comment='用户偏好设置')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    # 关联
    login_logs = db.relationship('LoginLog', backref='user', lazy='dynamic')
    analysis_histories = db.relationship('AnalysisHistory', backref='user', lazy='dynamic')
    crawl_histories = db.relationship('CrawlHistory', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """设置密码（加盐哈希）"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_profile_complete(self):
        """检查用户资料是否完整（是否设置了密码）"""
        return self.password_hash is not None
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'gitee_id': self.gitee_id,
            'username': self.username,
            'avatar_url': self.avatar_url,
            'preferences': self.preferences or {},
            'is_profile_complete': self.is_profile_complete,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class LoginLog(db.Model):
    """登录日志模型 - 审计用户登录行为"""
    __tablename__ = 'login_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True, comment='用户ID')
    login_time = db.Column(db.DateTime, default=datetime.utcnow, comment='登录时间')
    ip_address = db.Column(db.String(50), comment='IP地址')
    user_agent = db.Column(db.String(500), comment='用户代理')
    login_type = db.Column(db.String(20), default='gitee', comment='登录类型')
    
    def __repr__(self):
        return f'<LoginLog user_id={self.user_id} time={self.login_time}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'login_time': self.login_time.isoformat() if self.login_time else None,
            'ip_address': self.ip_address,
            'login_type': self.login_type
        }

class AnalysisHistory(db.Model):
    """分析历史模型 - 记录用户的舆情分析历史"""
    __tablename__ = 'analysis_histories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True, comment='用户ID')
    keyword = db.Column(db.String(200), nullable=False, comment='搜索关键词')
    platform = db.Column(db.String(50), nullable=False, comment='平台：xhs/zhihu')
    result_count = db.Column(db.Integer, default=0, comment='结果数量')
    status = db.Column(db.String(20), default='completed', comment='状态：completed/failed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    
    def __repr__(self):
        return f'<AnalysisHistory keyword={self.keyword}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'keyword': self.keyword,
            'platform': self.platform,
            'result_count': self.result_count,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ApiCallLog(db.Model):
    """API 调用日志 - 记录 API 调用耗时"""
    __tablename__ = 'api_call_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True, comment='用户ID')
    endpoint = db.Column(db.String(200), nullable=False, comment='API 端点')
    method = db.Column(db.String(10), nullable=False, comment='请求方法')
    duration_ms = db.Column(db.Integer, comment='耗时(毫秒)')
    status_code = db.Column(db.Integer, comment='响应状态码')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='调用时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'endpoint': self.endpoint,
            'method': self.method,
            'duration_ms': self.duration_ms,
            'status_code': self.status_code,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CrawlHistory(db.Model):
    """爬取历史模型"""
    __tablename__ = 'crawl_histories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True, comment='用户ID')
    keyword = db.Column(db.String(200), nullable=False, comment='搜索关键词')
    platform = db.Column(db.String(50), nullable=False, comment='平台：xhs/zhihu')
    # 使用 server_default 让数据库自动设置时间
    created_at = db.Column(db.DateTime,
                           server_default=db.text('CURRENT_TIMESTAMP'),
                           comment='创建时间')
    is_manual = db.Column(db.Boolean, default=True, comment='是否为手动爬取')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'keyword': self.keyword,
            'platform': self.platform,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_manual': self.is_manual
        }

