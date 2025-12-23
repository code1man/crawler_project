# -*- coding: utf-8 -*-
"""
舆情 API (Crawler API)
爬虫和数据分析接口
"""
import io
import re
import pandas as pd
from flask import request, send_file
from flask_restx import Namespace, Resource, fields
from services.crawler_service import CrawlerService
from utils.jwt_utils import token_required, get_current_user_id

# 创建命名空间
crawler_ns = Namespace('crawler', description='舆情爬虫相关接口')

# 定义模型
crawl_request = crawler_ns.model('CrawlRequest', {
    'keyword': fields.String(required=True, description='搜索关键词'),
    'platform': fields.String(required=True, description='平台: xhs/zhihu'),
    'cookie': fields.String(description='知乎 Cookie（可选）'),
    'batch_size': fields.Integer(default=50, description='批次大小'),
    'offset': fields.Integer(default=0, description='偏移量')
})

response_model = crawler_ns.model('Response', {
    'code': fields.Integer(description='状态码'),
    'message': fields.String(description='消息'),
    'data': fields.Raw(description='数据')
})

history_model = crawler_ns.model('AnalysisHistory', {
    'id': fields.Integer(description='ID'),
    'keyword': fields.String(description='关键词'),
    'platform': fields.String(description='平台'),
    'result_count': fields.Integer(description='结果数量'),
    'created_at': fields.String(description='创建时间')
})


@crawler_ns.route('/crawl')
class Crawl(Resource):
    @crawler_ns.doc('crawl', security='Bearer')
    @crawler_ns.expect(crawl_request)
    @crawler_ns.marshal_with(response_model)
    @token_required
    def post(self):
        """
        执行爬虫任务
        
        需要在 Header 中携带 JWT Token
        """
        user_id = get_current_user_id()
        data = request.json or {}
        
        keyword = data.get('keyword')
        platform = data.get('platform')
        cookie = data.get('cookie', '')
        batch_size = int(data.get('batch_size', 50))
        offset = int(data.get('offset', 0))
        
        if not keyword:
            return {'code': 400, 'message': '请输入关键词', 'data': None}, 400
        
        if platform not in ['xhs', 'zhihu']:
            return {'code': 400, 'message': '平台必须是 xhs 或 zhihu', 'data': None}, 400
        
        result = CrawlerService.crawl(
            user_id=user_id,
            keyword=keyword,
            platform=platform,
            cookie=cookie,
            max_count=batch_size,
            offset=offset
        )
        
        return {
            'code': 200,
            'message': f'本批次获取 {result["count"]} 条数据',
            'data': result['data']
        }


@crawler_ns.route('/data')
class CrawlerData(Resource):
    @crawler_ns.doc('get_data', security='Bearer')
    @crawler_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取当前用户的爬取数据"""
        user_id = get_current_user_id()
        data = CrawlerService.get_user_data(user_id)
        return {'code': 200, 'message': 'success', 'data': data}
    
    @crawler_ns.doc('clear_data', security='Bearer')
    @crawler_ns.marshal_with(response_model)
    @token_required
    def delete(self):
        """清空当前用户的爬取数据"""
        user_id = get_current_user_id()
        CrawlerService.clear_user_data(user_id)
        return {'code': 200, 'message': '数据已清空', 'data': None}


@crawler_ns.route('/download')
class DownloadData(Resource):
    @crawler_ns.doc('download_data', security='Bearer')
    @token_required
    def get(self):
        """下载爬取数据为 CSV 文件"""
        user_id = get_current_user_id()
        data = CrawlerService.get_user_data(user_id)
        
        if not data:
            return {'code': 400, 'message': '没有数据可下载'}, 400
        
        # 转换为 DataFrame
        rows = []
        for item in data:
            comments = item.get('comments', [])
            if comments:
                for comment in comments:
                    rows.append({
                        'keyword': item.get('title', ''),
                        'url': item.get('url', ''),
                        'user': item.get('author', ''),
                        'comment_content': comment
                    })
            else:
                rows.append({
                    'keyword': item.get('title', ''),
                    'url': item.get('url', ''),
                    'user': item.get('author', ''),
                    'comment_content': item.get('content', '')
                })
        
        df = pd.DataFrame(rows)
        
        # 生成文件名
        info = CrawlerService.get_crawl_info(user_id)
        platform_name = {'xhs': '小红书', 'zhihu': '知乎'}.get(info['platform'], 'unknown')
        keywords_str = '_'.join(info['keywords'][:3]) if info['keywords'] else '数据'
        keywords_str = re.sub(r'[\\/:*?"<>|]', '', keywords_str)
        filename = f"{platform_name}_{keywords_str}_result.csv"
        
        # 写入 buffer
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )


@crawler_ns.route('/history')
class AnalysisHistory(Resource):
    @crawler_ns.doc('get_history', security='Bearer')
    @crawler_ns.marshal_with(response_model)
    @token_required
    def get(self):
        """获取用户的分析历史"""
        user_id = get_current_user_id()
        limit = request.args.get('limit', 20, type=int)
        
        history = CrawlerService.get_analysis_history(user_id, limit)
        return {'code': 200, 'message': 'success', 'data': history}
