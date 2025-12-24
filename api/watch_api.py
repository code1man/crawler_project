# -*- coding: utf-8 -*-
"""
Watch (订阅) API
提供简单的 GET/POST/enable/test/delete 接口，供前端使用
"""
from flask import request
from flask_restx import Namespace, Resource, fields
from watch.store import create_watch, list_watches, get_watch, delete_watch, set_enabled
from watch.task import run_watch_once
from utils.jwt_utils import token_required, get_current_user_id

watch_ns = Namespace('watch', description='订阅管理')

watch_model = watch_ns.model('Watch', {
    'keyword': fields.String(required=True, description='关键词'),
    'platform': fields.String(description='平台: xhs/zhihu', default='xhs'),
    'interval_minutes': fields.Integer(description='间隔(分钟)', default=60),
    'negative_threshold': fields.Integer(description='负面阈值'),
    'positive_threshold': fields.Integer(description='正面阈值'),
    'email': fields.String(description='通知邮箱')
})

@watch_ns.route('')
class WatchList(Resource):
    @watch_ns.doc('list_watches')
    @token_required
    def get(self):
        user_id = get_current_user_id()
        data = list_watches(user_id)
        return {'code': 200, 'msg': 'ok', 'data': data}

    @watch_ns.expect(watch_model)
    @token_required
    def post(self):
        data = request.json or {}
        user_id = get_current_user_id() or 'demo_user'
        w = create_watch(data, user_id=user_id)
        return {'code': 200, 'msg': 'created', 'data': w}

@watch_ns.route('/<string:watch_id>/enable')
class WatchEnable(Resource):
    @token_required
    def post(self, watch_id):
        data = request.json or {}
        enabled = data.get('enabled', True)
        ok = set_enabled(watch_id, enabled)
        if ok:
            return {'code': 200, 'msg': 'ok'}
        return {'code': 404, 'msg': 'not found'}, 404

@watch_ns.route('/<string:watch_id>/test')
class WatchTest(Resource):
    @token_required
    def post(self, watch_id):
        w = get_watch(watch_id)
        if not w:
            return {'code': 404, 'msg': 'not found'}, 404
        # 运行一次订阅任务并返回摘要
        result = run_watch_once(w)
        return {'code': 200, 'msg': 'ok', 'data': result}

@watch_ns.route('/<string:watch_id>')
class WatchItem(Resource):
    @token_required
    def delete(self, watch_id):
        ok = delete_watch(watch_id)
        if ok:
            return {'code': 200, 'msg': 'deleted'}
        return {'code': 404, 'msg': 'not found'}, 404
