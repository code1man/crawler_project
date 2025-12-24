# services/in_memory_store.py
"""简单的进程内数据存储，用于临时替代 app.py 的 GLOBAL_DATA/CRAWL_INFO
适用于开发/演示环境；生产请用数据库或持久存储。
"""
from typing import List, Dict

GLOBAL_DATA: List[Dict] = []
GLOBAL_CRAWL_INFO: Dict = {'platform': '', 'keywords': []}


# 辅助操作
def get_data():
    return GLOBAL_DATA


def set_data(data: List[Dict]):
    GLOBAL_DATA.clear()
    GLOBAL_DATA.extend(data or [])


def extend_data(items: List[Dict]):
    GLOBAL_DATA.extend(items or [])


def clear_data():
    GLOBAL_DATA.clear()


def get_crawl_info():
    return GLOBAL_CRAWL_INFO


def set_crawl_info(info: Dict):
    GLOBAL_CRAWL_INFO.update(info or {})


def reset_crawl_info():
    GLOBAL_CRAWL_INFO.clear()
    GLOBAL_CRAWL_INFO.update({'platform': '', 'keywords': []})
