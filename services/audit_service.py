# -*- coding: utf-8 -*-
"""
审计服务 (Audit Service)
记录登录日志、API 调用日志
"""
from flask import request
from models import db, LoginLog, ApiCallLog
from datetime import datetime


class AuditService:
    """审计服务类"""
    
    @staticmethod
    def log_login(user_id, login_type='gitee'):
        """
        记录用户登录日志
        
        Args:
            user_id: 用户 ID
            login_type: 登录类型
            
        Returns:
            LoginLog: 日志对象
        """
        log = LoginLog(
            user_id=user_id,
            login_time=datetime.utcnow(),
            ip_address=AuditService._get_client_ip(),
            user_agent=request.headers.get('User-Agent', '')[:500],
            login_type=login_type
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    @staticmethod
    def log_api_call(user_id, endpoint, method, duration_ms, status_code):
        """
        记录 API 调用日志
        
        Args:
            user_id: 用户 ID（可为 None）
            endpoint: API 端点
            method: 请求方法
            duration_ms: 耗时（毫秒）
            status_code: 响应状态码
            
        Returns:
            ApiCallLog: 日志对象
        """
        log = ApiCallLog(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=status_code
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    @staticmethod
    def get_login_logs(user_id=None, limit=50):
        """
        获取登录日志
        
        Args:
            user_id: 用户 ID（可选，为空则获取全部）
            limit: 返回数量限制
            
        Returns:
            list: 登录日志列表
        """
        query = LoginLog.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        logs = query.order_by(LoginLog.login_time.desc()).limit(limit).all()
        return [log.to_dict() for log in logs]
    
    @staticmethod
    def get_api_call_stats(user_id=None, limit=100):
        """
        获取 API 调用统计
        
        Args:
            user_id: 用户 ID（可选）
            limit: 返回数量限制
            
        Returns:
            list: API 调用日志列表
        """
        query = ApiCallLog.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        logs = query.order_by(ApiCallLog.created_at.desc()).limit(limit).all()
        return [log.to_dict() for log in logs]
    
    @staticmethod
    def _get_client_ip():
        """获取客户端 IP 地址"""
        # 优先从代理头获取
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr or 'unknown'
