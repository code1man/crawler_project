# spiders/xhs_spider.py
"""
小红书关键词搜索爬虫 - Web版本
基于 xhs_spider_cmd.py 改造，适用于 Flask 后端调用
"""
import time
import random
from urllib.parse import quote
from DrissionPage import ChromiumPage


def search_and_crawl_xhs(keyword, max_count=5):
    """
    小红书爬虫封装函数（Web版本）
    :param keyword: 搜索关键词
    :param max_count: 限制爬取的笔记数量
    :return: 结果列表
    """
    results = []
    page = None
    
    try:
        # 初始化浏览器
        page = ChromiumPage()
        
        # 1. 搜索关键词
        keyword_encode = quote(keyword)
        url = f'https://www.xiaohongshu.com/search_result?keyword={keyword_encode}&source=web_search_result_notes'
        print(f"[INFO] 正在搜索: {keyword}")
        page.get(url)
        time.sleep(3)  # 等待页面加载
        
        # 2. 获取笔记列表
        processed_notes = set()
        crawled_count = 0
        scroll_count = 0
        # 动态计算最大滚动次数：每次滚动大约能获取5-10个笔记，所以至少滚动 max_count/5 次
        max_scroll = max(20, (max_count // 5) + 10)
        
        while crawled_count < max_count and scroll_count < max_scroll:
            # 尝试多种方式获取笔记元素
            note_elements = _get_note_elements(page)
            
            if not note_elements:
                print("[WARN] 未找到笔记元素，尝试滚动...")
                page.scroll.down(500)
                scroll_count += 1
                time.sleep(1)
                continue
            
            print(f"[INFO] 当前页面有 {len(note_elements)} 个笔记元素")
            
            # 遍历笔记元素
            found_new = False
            for note_ele in note_elements:
                if crawled_count >= max_count:
                    break
                
                try:
                    # 获取笔记唯一标识
                    note_id = _get_note_id(note_ele, scroll_count)
                    
                    # 去重检查
                    if note_id in processed_notes:
                        continue
                    
                    processed_notes.add(note_id)
                    found_new = True
                    
                    # 获取笔记详情
                    note_data = _click_and_get_detail(page, note_ele, keyword, crawled_count + 1)
                    
                    if note_data:
                        results.append(note_data)
                        crawled_count += 1
                        print(f"[进度] 已爬取 {crawled_count}/{max_count} 篇笔记")
                    
                    # 随机延时
                    time.sleep(random.uniform(0.5, 1.0))
                    break  # 处理完一个就重新获取元素列表
                    
                except Exception as e:
                    print(f"[ERROR] 处理笔记失败: {e}")
                    _close_detail_page(page)
                    continue
            
            # 如果没有找到新元素，滚动加载更多
            if not found_new:
                print("******** 滚动加载更多 ********")
                page.scroll.down(600)
                scroll_count += 1
                time.sleep(random.uniform(1, 1.5))
        
        print(f"[DONE] 共爬取 {len(results)} 篇笔记")
        
    except Exception as e:
        print(f"[ERROR] XHS Crawler Error: {e}")
    finally:
        if page:
            try:
                page.quit()
            except:
                pass
    
    return results


def _get_note_elements(page):
    """获取笔记元素列表"""
    note_elements = None
    
    # 方式1: 通过feeds-page容器
    container = page.ele('.feeds-page', timeout=2)
    if container:
        note_elements = container.eles('.note-item', timeout=1)
    
    # 方式2: 直接获取所有笔记卡片
    if not note_elements or len(note_elements) == 0:
        note_elements = page.eles('.note-item', timeout=2)
    
    # 方式3: 尝试其他可能的选择器
    if not note_elements or len(note_elements) == 0:
        note_elements = page.eles('xpath://section[contains(@class,"note")]', timeout=2)
    
    return note_elements


def _get_note_id(note_ele, scroll_count):
    """获取笔记的唯一标识"""
    note_id = ""
    try:
        link_ele = note_ele.ele('tag:a', timeout=0)
        if link_ele:
            href = link_ele.attr('href') or ""
            if '/explore/' in href:
                note_id = href.split('/explore/')[-1].split('?')[0]
    except:
        pass
    
    if not note_id:
        note_id = note_ele.attr('data-id') or note_ele.attr('id') or f"note_{scroll_count}_{random.randint(1000,9999)}"
    
    return note_id


def _click_and_get_detail(page, note_element, keyword, index):
    """
    点击笔记卡片进入详情页，获取内容和评论
    """
    try:
        # 获取笔记基本信息（在列表页获取）
        note_info = _get_note_basic_info(note_element)
        
        print(f"\n[{index}] 点击进入笔记: {note_info.get('title', '无标题')[:30]}...")
        
        # 滚动到元素可见
        try:
            note_element.scroll.to_see()
            time.sleep(0.5)
        except:
            pass
        
        # 点击笔记卡片
        _click_note(page, note_element)
        time.sleep(2.5)  # 等待详情页加载
        
        # 获取当前URL
        note_url = page.url
        
        # 获取笔记正文
        note_content = _get_note_content(page)
        
        # 获取发布时间
        publish_time = _get_publish_time(page)
        
        # 滚动加载评论
        print("  [INFO] 滚动加载评论...")
        for _ in range(3):
            time.sleep(random.uniform(0.2, 0.4))
            page.scroll.down(300)
        
        # 获取评论
        comments = _get_comments(page)
        
        print(f"  [INFO] 共获取 {len(comments)} 条评论")
        
        # 关闭详情页
        _close_detail_page(page)
        
        # 返回统一格式的数据
        return {
            "source": "小红书",
            "title": note_info.get('title', '无标题'),
            "author": note_info.get('author', '未知作者'),
            "content": note_content,
            "url": note_url,
            "publish_time": publish_time,
            "likes": note_info.get('like', '0'),
            "comments": comments
        }
        
    except Exception as e:
        print(f"  [ERROR] 获取笔记详情失败: {e}")
        _close_detail_page(page)
        return None


def _get_note_basic_info(note_element):
    """从列表页获取笔记基本信息"""
    info = {'title': '', 'author': '', 'like': '0'}
    try:
        footer = note_element.ele('.footer', timeout=0)
        if footer:
            title_ele = footer.ele('.title', timeout=0)
            if title_ele:
                info['title'] = title_ele.text or ""
            
            author_wrapper = footer.ele('.author-wrapper', timeout=0)
            if author_wrapper:
                author_ele = author_wrapper.ele('.author', timeout=0)
                if author_ele:
                    info['author'] = author_ele.text or ""
            
            like_ele = footer.ele('.like-wrapper', timeout=0)
            if like_ele:
                info['like'] = like_ele.text.strip() if like_ele.text else "0"
    except:
        pass
    return info


def _click_note(page, note_element):
    """点击笔记卡片"""
    try:
        note_element.click()
    except Exception:
        # 如果普通点击失败，尝试其他方式
        try:
            page.run_js('arguments[0].click()', note_element)
        except:
            link = note_element.ele('tag:a', timeout=0)
            if link:
                link.click()


def _get_note_content(page):
    """获取笔记正文内容"""
    content = ""
    selectors = [
        '#detail-desc .note-text',
        '#detail-desc .desc',
        '.note-scroller .desc',
        '.note-content',
        '.desc',
        'xpath://div[contains(@class,"desc")]//span',
        'xpath://div[@id="detail-desc"]',
    ]
    for selector in selectors:
        try:
            content_ele = page.ele(selector, timeout=1)
            if content_ele:
                text = content_ele.text
                if text and len(text) > 3:
                    content = text.strip()
                    print(f"  [+] 正文: {content[:60]}...")
                    break
        except:
            continue
    return content


def _get_publish_time(page):
    """获取发布时间"""
    publish_time = ""
    selectors = ['.date', '.bottom-container .date', 'xpath://span[contains(@class,"date")]']
    for selector in selectors:
        try:
            time_ele = page.ele(selector, timeout=1)
            if time_ele and time_ele.text:
                publish_time = time_ele.text.strip()
                break
        except:
            continue
    return publish_time


def _get_comments(page):
    """获取评论列表"""
    comments = []
    selectors = [
        '.comment-item',
        '.parent-comment',
        '.comments-container .comment',
        'xpath://div[contains(@class,"comment-item")]',
        'xpath://div[contains(@class,"commentItem")]',
    ]
    
    for selector in selectors:
        try:
            comment_eles = page.eles(selector, timeout=2)
            if comment_eles and len(comment_eles) > 0:
                print(f"  [INFO] 找到 {len(comment_eles)} 条评论元素")
                for ce in comment_eles[:10]:  # 最多取10条评论
                    try:
                        comment_text = ce.text.strip() if ce.text else ""
                        if comment_text and len(comment_text) > 2:
                            # 处理评论文本，提取实际内容
                            lines = comment_text.split('\n')
                            if len(lines) >= 2:
                                content = '\n'.join(lines[1:]).strip()
                            else:
                                content = comment_text
                            
                            # 去重
                            if content and content not in comments:
                                comments.append(content)
                                print(f"    [+] 评论: {content[:40]}...")
                    except:
                        continue
                if comments:
                    break
        except:
            continue
    
    return comments


def _close_detail_page(page):
    """关闭详情页弹窗，返回搜索列表"""
    try:
        close_selectors = [
            '.close-circle',
            '.close',
            'xpath://div[contains(@class,"close")]',
            'xpath://*[contains(@class,"close")]',
        ]
        for selector in close_selectors:
            try:
                close_btn = page.ele(selector, timeout=1)
                if close_btn:
                    close_btn.click()
                    time.sleep(0.5)
                    return
            except:
                continue
        
        # 尝试按ESC键
        page.actions.key_down('ESCAPE').key_up('ESCAPE')
        time.sleep(0.5)
        
        # 点击遮罩层
        try:
            mask = page.ele('.mask', timeout=0.5)
            if mask:
                mask.click()
                time.sleep(0.5)
        except:
            pass
            
    except Exception as e:
        print(f"  [WARN] 关闭详情页失败: {e}")