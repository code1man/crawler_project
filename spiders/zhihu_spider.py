# spiders/zhihu_spider.py
"""
知乎关键词搜索爬虫 - Web版本
基于 zhihu_spider_cmd.py 改造，适用于 Flask 后端调用
使用知乎的 search_v3 JSON API
增强版：支持多种搜索类型、时间范围筛选、代理IP池、速度控制
"""
import time
import random
import logging
from datetime import datetime
from urllib.parse import quote_plus, urljoin
import requests

# ------------------------- Config -------------------------
# 多个User-Agent轮换
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 知乎搜索API - 支持多种类型和筛选参数
API_SEARCH = "https://www.zhihu.com/api/v4/search_v3?t={search_type}&q={q}&offset={offset}&limit={limit}"
API_SEARCH_WITH_FILTER = "https://www.zhihu.com/api/v4/search_v3?t={search_type}&q={q}&offset={offset}&limit={limit}&time_interval={time_interval}&sort={sort}"

# 搜索策略组合 - 多维度获取更多结果
SEARCH_STRATEGIES = [
    # (search_type, time_interval, sort)
    ("general", "", ""),           # 综合-默认
    ("general", "", "upvoted_count"),  # 综合-按点赞
    ("general", "", "created_time"),   # 综合-按时间
    ("answer", "", ""),            # 回答-默认
    ("answer", "", "upvoted_count"),   # 回答-按点赞
    ("answer", "", "created_time"),    # 回答-按时间
    ("article", "", ""),           # 文章-默认
    ("article", "", "created_time"),   # 文章-按时间
    ("content", "", ""),           # 内容-默认
    ("general", "one_month", ""),      # 综合-近一月
    ("general", "three_months", ""),   # 综合-近三月
    ("general", "six_months", ""),     # 综合-近半年
    ("general", "one_year", ""),       # 综合-近一年
    ("answer", "one_month", ""),       # 回答-近一月
    ("answer", "three_months", ""),    # 回答-近三月
]

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3

# ==================== 速度控制配置 ====================
# 每次请求后的休息时间范围（秒）
PAGE_SLEEP_RANGE = (2.0, 4.0)      # 每页之间休息2-4秒
STRATEGY_SLEEP_RANGE = (3.0, 6.0)  # 切换策略时休息3-6秒
ERROR_SLEEP_RANGE = (5.0, 10.0)    # 出错后休息5-10秒

# ==================== 代理IP池配置 ====================
# 设置为True启用代理，需要配置PROXY_LIST或PROXY_API
USE_PROXY = False

# 方式1：静态代理列表（格式：http://ip:port 或 http://user:pass@ip:port）
PROXY_LIST = [
    # "http://127.0.0.1:7890",
    # "http://user:pass@192.168.1.1:8080",
]

# 方式2：代理API接口（每次调用返回一个可用代理）
# 常见代理服务商API格式，取消注释并填入你的API地址
PROXY_API = ""
# PROXY_API = "http://api.proxy.com/get?key=YOUR_KEY&num=1"

# 代理失败后的重试次数
PROXY_RETRY_COUNT = 3


class ProxyPool:
    """代理IP池管理器"""
    
    def __init__(self):
        self.proxies = list(PROXY_LIST) if PROXY_LIST else []
        self.current_index = 0
        self.failed_proxies = set()
    
    def get_proxy(self):
        """获取一个代理IP"""
        if not USE_PROXY:
            return None
        
        # 优先从API获取
        if PROXY_API:
            try:
                resp = requests.get(PROXY_API, timeout=5)
                if resp.status_code == 200:
                    proxy = resp.text.strip()
                    if proxy and ":" in proxy:
                        if not proxy.startswith("http"):
                            proxy = f"http://{proxy}"
                        print(f"[PROXY] 从API获取代理: {proxy}")
                        return {"http": proxy, "https": proxy}
            except Exception as e:
                print(f"[PROXY] API获取代理失败: {e}")
        
        # 从静态列表轮换
        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            # 重置失败列表，重新尝试
            self.failed_proxies.clear()
            available = self.proxies
        
        if available:
            proxy = available[self.current_index % len(available)]
            self.current_index += 1
            print(f"[PROXY] 使用代理: {proxy}")
            return {"http": proxy, "https": proxy}
        
        print("[PROXY] 无可用代理，使用直连")
        return None
    
    def mark_failed(self, proxy_dict):
        """标记代理失败"""
        if proxy_dict:
            proxy = proxy_dict.get("http", "")
            if proxy:
                self.failed_proxies.add(proxy)
                print(f"[PROXY] 标记代理失败: {proxy}")


# 全局代理池实例
proxy_pool = ProxyPool()


def search_and_crawl_zhihu(keyword, max_count=5, cookie_str=None, offset=0):
    """
    知乎爬虫封装函数（Web版本）- 增强版
    使用多种搜索策略组合（类型+时间范围+排序方式）突破API限制
    :param keyword: 搜索关键词
    :param max_count: 限制爬取的数量（会内部分页获取直到达到此数量）
    :param cookie_str: 知乎Cookie字符串（由前端传入，必填）
    :param offset: 起始偏移量，用于分批爬取
    :return: 结果列表
    """
    print(f"[DEBUG] search_and_crawl_zhihu called: keyword={keyword}, max_count={max_count}, offset={offset}")
    results = []
    seen_urls = set()  # 用于URL去重
    seen_titles = set()  # 用于标题去重（处理不同URL但相同内容的情况）
    
    # 构建请求头
    headers = _make_headers(cookie_str)
    
    # 检查Cookie
    if not cookie_str or len(cookie_str) < 10:
        print("[ERROR] 未检测到有效Cookie，知乎爬取需要Cookie！")
        return results
    
    # 创建Session
    session = requests.Session()
    session.headers.update(headers)
    
    print(f"[INFO] 开始爬取知乎: {keyword}, 目标数量: {max_count}")
    print(f"[INFO] 共有 {len(SEARCH_STRATEGIES)} 种搜索策略")
    
    # 遍历不同的搜索策略以获取更多结果
    for strategy_idx, (search_type, time_interval, sort) in enumerate(SEARCH_STRATEGIES):
        if len(results) >= max_count:
            break
        
        strategy_desc = f"{search_type}"
        if time_interval:
            strategy_desc += f"+{time_interval}"
        if sort:
            strategy_desc += f"+{sort}"
        print(f"[INFO] 策略 {strategy_idx+1}/{len(SEARCH_STRATEGIES)}: {strategy_desc}")
        
        # 分页爬取
        current_offset = offset if strategy_idx == 0 else 0
        limit = 20  # 知乎API每页最多20条
        page = 1
        empty_pages = 0  # 连续空页计数
        max_empty_pages = 2  # 连续2页无新数据则切换策略
        strategy_fetched = 0
        strategy_new = 0  # 该策略获取的新数据数量
        
        while len(results) < max_count and empty_pages < max_empty_pages:
            q = quote_plus(keyword)
            
            # 构建URL
            if time_interval or sort:
                url = API_SEARCH_WITH_FILTER.format(
                    search_type=search_type, q=q, offset=current_offset, limit=limit,
                    time_interval=time_interval, sort=sort
                )
            else:
                url = API_SEARCH.format(search_type=search_type, q=q, offset=current_offset, limit=limit)
            
            # 获取JSON数据
            json_data = _fetch_json(session, url)
            
            if not json_data:
                print(f"[WARN] 第 {page} 页获取失败")
                break
            
            # 解析数据
            items = _parse_search_json(json_data)
            
            # 检查API分页结束标志
            paging = json_data.get("paging", {})
            is_end = paging.get("is_end", False)
            
            if not items:
                empty_pages += 1
                if empty_pages >= max_empty_pages or is_end:
                    print(f"[INFO] [{strategy_desc}] 无更多数据")
                    break
                current_offset += limit
                page += 1
                continue
            
            # 处理每条数据
            new_items = 0
            for item in items:
                if len(results) >= max_count:
                    break
                
                # URL去重
                item_url = item.get("url", "")
                if item_url and item_url in seen_urls:
                    continue
                
                # 标题去重（处理相同内容不同URL的情况）
                item_title = item.get("title", "").strip()
                title_key = item_title[:50] if item_title else ""  # 用前50字符作为key
                if title_key and title_key in seen_titles:
                    continue
                
                if item_url:
                    seen_urls.add(item_url)
                if title_key:
                    seen_titles.add(title_key)
                
                results.append({
                    "source": "知乎",
                    "title": item.get("title", "无标题"),
                    "author": item.get("author_name", "匿名用户"),
                    "content": item.get("content", ""),
                    "url": item_url,
                    "publish_time": item.get("publish_time", ""),
                    "likes": item.get("likes", ""),
                    "comments": [item.get("content", "")] if item.get("content") else []
                })
                new_items += 1
                strategy_new += 1
            
            strategy_fetched += len(items)
            
            if new_items == 0:
                empty_pages += 1
            else:
                empty_pages = 0
            
            print(f"[INFO] [{strategy_desc}] 第{page}页: 获取{len(items)}条, 新增{new_items}条, 累计{len(results)}条")
            
            # 检查是否是最后一页
            if is_end:
                break
            
            # 下一页
            current_offset += limit
            page += 1
            
            # 页间随机延时（降低速度）
            if len(results) < max_count:
                sleep_time = random.uniform(*PAGE_SLEEP_RANGE)
                print(f"[SLEEP] 页间休息 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
        
        print(f"[INFO] 策略 {strategy_desc} 完成: 遍历{strategy_fetched}条, 新增{strategy_new}条")
        
        # 策略间较长休息
        if len(results) < max_count and strategy_idx < len(SEARCH_STRATEGIES) - 1:
            sleep_time = random.uniform(*STRATEGY_SLEEP_RANGE)
            print(f"[SLEEP] 策略切换休息 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
    
    print(f"[DONE] 共获取 {len(results)} 条不重复数据")
    return results


def _make_headers(cookie_str):
    """构建请求头，使用随机User-Agent"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://www.zhihu.com/search",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",  # 移除 br，requests 不支持 Brotli 自动解压
        "Origin": "https://www.zhihu.com",
        "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not=A?Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-requested-with": "fetch",
    }
    if cookie_str:
        # 去除前后空白字符
        cookie_str = cookie_str.strip()
        # 处理可能的 "cookie=" 前缀
        if cookie_str.lower().startswith("cookie:"):
            cookie_str = cookie_str.split(":", 1)[1].strip()
        elif cookie_str.lower().startswith("cookie="):
            cookie_str = cookie_str.split("=", 1)[1].strip()
        headers["Cookie"] = cookie_str
        print(f"[DEBUG] Cookie长度: {len(cookie_str)}, 前30字符: {cookie_str[:30]}...")
    else:
        print("[WARN] 未提供Cookie!")
    return headers


def _fetch_json(session, url):
    """获取JSON数据，支持代理池和重试"""
    import urllib3
    import ssl
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    last_exc = None
    current_proxy = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 每次请求更新User-Agent增加随机性
            session.headers["User-Agent"] = random.choice(USER_AGENTS)
            
            # 获取代理（如果启用）
            if USE_PROXY:
                current_proxy = proxy_pool.get_proxy()
                r = session.get(url, timeout=REQUEST_TIMEOUT, verify=False, proxies=current_proxy)
            else:
                # 不使用代理，禁用系统代理直连
                r = session.get(url, timeout=REQUEST_TIMEOUT, verify=False, proxies={'http': None, 'https': None})
            
            print(f"[DEBUG] 请求状态码: {r.status_code}")
            
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception as e:
                    print(f"[WARN] JSON解析失败: {e}")
                    print(f"[DEBUG] 响应长度: {len(r.text)} 字符")
                    print(f"[DEBUG] 响应内容前500字符: {r.text[:500] if r.text else '(空)'}")
                    return None
            elif r.status_code == 400:
                print(f"[DEBUG] 400响应内容: {r.text[:200] if r.text else 'empty'}")
            elif r.status_code == 403 or r.status_code == 429:
                # 被限制，标记代理失败并等待
                if current_proxy:
                    proxy_pool.mark_failed(current_proxy)
                print(f"[WARN] 请求被限制 {r.status_code}，休息后重试...")
                time.sleep(random.uniform(*ERROR_SLEEP_RANGE))
            else:
                print(f"[WARN] 请求返回 {r.status_code} (尝试 {attempt})")
        except Exception as e:
            last_exc = e
            # 标记代理失败
            if current_proxy:
                proxy_pool.mark_failed(current_proxy)
            print(f"[WARN] 请求失败 (尝试 {attempt}): {e}")
        
        # 重试前休息
        sleep_time = random.uniform(*ERROR_SLEEP_RANGE)
        print(f"[SLEEP] 错误后休息 {sleep_time:.1f} 秒...")
        time.sleep(sleep_time)
    
    print(f"[ERROR] 重试后仍然失败: {last_exc}")
    return None


def _full_url(href):
    """将相对URL转换为完整URL"""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return urljoin("https://www.zhihu.com", href)


def _parse_search_json(data):
    """
    解析知乎搜索API返回的JSON数据
    返回格式统一的数据列表
    """
    rows = []
    if not data or "data" not in data:
        return rows
    
    for obj in data.get("data", []):
        try:
            # 很多条目有 'object' 子字段
            o = obj.get("object") or obj
            
            # ID和URL
            weibo_id = o.get("id") or o.get("objectId") or ""
            url = o.get("url") or o.get("target_url") or o.get("share_url") or ""
            if not url and weibo_id:
                url = f"https://www.zhihu.com/question/{weibo_id}"
            
            # 标题和内容
            title = o.get("title") or o.get("question", {}).get("name") or ""
            # 清理HTML标签
            title = title.replace("<em>", "").replace("</em>", "")
            
            excerpt = o.get("excerpt") or o.get("abstract") or ""
            excerpt = excerpt.replace("<em>", "").replace("</em>", "")
            
            content = (title + " " + excerpt).strip() if excerpt else title
            
            # 作者信息
            author_name = ""
            author_home = ""
            if "author" in o and isinstance(o.get("author"), dict):
                author = o.get("author")
                author_name = author.get("name") or author.get("member", {}).get("name", "")
                author_home = _full_url(author.get("url") or author.get("member", {}).get("url", ""))
            
            if not author_name and "member" in o and isinstance(o.get("member"), dict):
                m = o.get("member")
                author_name = m.get("name") or ""
                author_home = _full_url(m.get("url") or "")
            
            # 发布时间
            publish_time = ""
            if o.get("created_time"):
                try:
                    ts = int(o.get("created_time"))
                    publish_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    publish_time = str(o.get("created_time"))
            elif o.get("published_time"):
                publish_time = str(o.get("published_time"))
            
            # 点赞数等
            likes = str(o.get("voteup_count", "") or o.get("likes_count", "") or "")
            comments_count = str(o.get("comment_count", "") or o.get("comments_count", "") or "")
            
            rows.append({
                "id": weibo_id,
                "url": _full_url(url),
                "title": title,
                "content": excerpt,
                "author_name": author_name,
                "author_home": author_home,
                "publish_time": publish_time,
                "likes": likes,
                "comments_count": comments_count,
            })
        except Exception as e:
            print(f"[WARN] 解析条目失败: {e}")
            continue
    
    return rows