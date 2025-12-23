# -*- coding: utf-8 -*-
"""
审计 API (Audit API)
登录日志和 API 调用统计
"""
from flask import request
from flask_restx import Namespace, Resource, fields
from services.audit_service import AuditService
from utils.jwt_utils import token_required, get_current_user_id

# 创建命名空间
audit_ns = Namespace('audit', description='审计日志相关接口')

# 定义模型
login_log_model = audit_ns.model('LoginLog', {
    'id': fields.Integer(description='ID'),
    'user_id': fields.Integer(description='用户ID'),
    'login_time': fields.String(description='登录时间'),
    'ip_address': fields.String(description='IP地址'),
    'login_type': fields.String(description='登录类型')
})

response_model = audit_ns.model('Response', {
    'code': fields.Integer(description='状态码'),
    'message': fields.String(description='消息'),
    'data': fields.Raw(description='数据')
})


@audit_ns.route('/login-logs')
class LoginLogs(Resource):
    @audit_ns.doc('get_login_logs', security='Bearer',
                  params={'limit': '返回数量限制（默认50）'})
    @audit_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取当前用户的登录日志"""
        user_id = get_current_user_id()
        limit = request.args.get('limit', 50, type=int)
        
        logs = AuditService.get_login_logs(user_id, limit)
        return {'code': 200, 'message': 'success', 'data': logs}


@audit_ns.route('/api-stats')
class ApiStats(Resource):
    @audit_ns.doc('get_api_stats', security='Bearer',
                  params={'limit': '返回数量限制（默认100）'})
    @audit_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取 API 调用统计"""
        user_id = get_current_user_id()
        limit = request.args.get('limit', 100, type=int)
        
        stats = AuditService.get_api_call_stats(user_id, limit)
        return {'code': 200, 'message': 'success', 'data': stats}
