# -*- coding: utf-8 -*-
"""
舆情服务 (Crawler Service)
封装爬虫和 AI 情感分析逻辑
"""
from flask import current_app
from models import db, AnalysisHistory
from spiders.xhs_spider import search_and_crawl_xhs
from spiders.zhihu_spider import search_and_crawl_zhihu
from utils.cleaner import clean_comments


class CrawlerService:
    """舆情爬虫服务类"""
    
    # 内存中临时存储（生产环境应使用 Redis）
    _global_data = {}
    _crawl_info = {}
    
    @staticmethod
    def crawl(user_id, keyword, platform, cookie=None, max_count=50, offset=0):
        """
        执行爬虫任务
        
        Args:
            user_id: 用户 ID
            keyword: 搜索关键词
            platform: 平台 (xhs/zhihu)
            cookie: 知乎 Cookie（可选）
            max_count: 最大爬取数量
            offset: 偏移量
            
        Returns:
            dict: 爬取结果
        """
        current_app.logger.info(f"[CrawlerService] 用户 {user_id} 爬取: {platform} - {keyword}")
        
        raw_data = []
        if platform == 'xhs':
            raw_data = search_and_crawl_xhs(keyword, max_count=max_count)
        elif platform == 'zhihu':
            raw_data = search_and_crawl_zhihu(keyword, max_count=max_count, cookie_str=cookie, offset=offset)
        
        # 清洗数据
        cleaned_data = clean_comments(raw_data)
        
        # 存储到用户会话（以用户 ID 为 key）
        if user_id not in CrawlerService._global_data:
            CrawlerService._global_data[user_id] = []
        CrawlerService._global_data[user_id].extend(cleaned_data)
        
        # 记录爬取信息
        if user_id not in CrawlerService._crawl_info:
            CrawlerService._crawl_info[user_id] = {'platform': platform, 'keywords': []}
        CrawlerService._crawl_info[user_id]['platform'] = platform
        if keyword not in CrawlerService._crawl_info[user_id]['keywords']:
            CrawlerService._crawl_info[user_id]['keywords'].append(keyword)
        
        # 记录到数据库
        history = AnalysisHistory(
            user_id=user_id,
            keyword=keyword,
            platform=platform,
            result_count=len(cleaned_data),
            status='completed'
        )
        db.session.add(history)
        db.session.commit()
        
        return {
            'count': len(cleaned_data),
            'data': cleaned_data
        }
    
    @staticmethod
    def get_user_data(user_id):
        """
        获取用户的爬取数据
        
        Args:
            user_id: 用户 ID
            
        Returns:
            list: 爬取的数据列表
        """
        return CrawlerService._global_data.get(user_id, [])
    
    @staticmethod
    def get_crawl_info(user_id):
        """
        获取用户的爬取信息
        
        Args:
            user_id: 用户 ID
            
        Returns:
            dict: 爬取信息
        """
        return CrawlerService._crawl_info.get(user_id, {'platform': '', 'keywords': []})
    
    @staticmethod
    def clear_user_data(user_id):
        """
        清空用户的爬取数据
        
        Args:
            user_id: 用户 ID
        """
        if user_id in CrawlerService._global_data:
            CrawlerService._global_data[user_id] = []
        if user_id in CrawlerService._crawl_info:
            CrawlerService._crawl_info[user_id] = {'platform': '', 'keywords': []}
    
    @staticmethod
    def get_analysis_history(user_id, limit=20):
        """
        获取用户的分析历史
        
        Args:
            user_id: 用户 ID
            limit: 返回数量限制
            
        Returns:
            list: 分析历史列表
        """
        histories = AnalysisHistory.query.filter_by(user_id=user_id)\
            .order_by(AnalysisHistory.created_at.desc())\
            .limit(limit).all()
        return [h.to_dict() for h in histories]
