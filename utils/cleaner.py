import re

# 省份/地区列表
PROVINCES = '北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门|美国|英国|日本|韩国|澳大利亚|加拿大|新加坡|马来西亚|泰国|越南|印度|法国|德国|意大利|西班牙|俄罗斯|巴西'

def clean_text_content(text):
    """
    清理文本内容，去除HTML标签、日期、地区等冗余信息
    """
    if not text:
        return ""
    
    text = str(text).strip()
    
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 移除末尾的 "赞" 和 "回复" 标记
    text = re.sub(r'\s*赞\s*$', '', text)
    text = re.sub(r'\s*回复\s*$', '', text)
    
    # 移除末尾的地区信息
    text = re.sub(rf'\s*({PROVINCES})\s*$', '', text)
    
    # 移除末尾常见的日期格式 如 "11-12", "11-12 09:30"
    text = re.sub(r'\s*\d{1,2}-\d{1,2}(\s*\d{1,2}:\d{2})?\s*$', '', text)
    
    # 移除 "昨天 11:02", "今天 09:30" 等格式
    text = re.sub(r'\s*(昨天|今天|前天|刚刚|\d+分钟前|\d+小时前|\d+天前)\s*(\d{1,2}:\d{2})?\s*$', '', text)
    
    # 再次移除可能残留的地区信息
    text = re.sub(rf'\s*({PROVINCES})\s*$', '', text)
    
    # 移除多余空格和换行
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def clean_comments(data_list, custom_keywords=None, min_length=4, deduplicate=True):
    """
    清洗评论数据
    1. 去除过短的无效评论
    2. 去除官方账号评论
    3. 支持自定义过滤关键词
    4. 支持基于URL/内容的去重
    5. 清理评论中的日期、地区等冗余信息
    
    :param data_list: 数据列表
    :param custom_keywords: 用户自定义的过滤关键词列表
    :param min_length: 最短评论长度，默认4
    :param deduplicate: 是否进行去重，默认True
    """
    cleaned_data = []
    seen_keys = set()  # 用于去重
    
    # 官方关键词列表（默认）
    official_keywords = ['小助手', '官方', '客服', '团队', '从不胡说', '医生助理']
    
    # 合并用户自定义关键词
    if custom_keywords:
        official_keywords = official_keywords + custom_keywords
    
    for item in data_list:
        # 去重检查
        if deduplicate:
            # 使用URL或内容作为去重键
            dedup_key = item.get('url', '') or item.get('content', '') or str(item)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
        
        valid_comments = []
        author = item.get('author', '')
        
        # 检查作者是否官方
        is_official = any(k in author for k in official_keywords)
        if is_official:
            continue # 跳过整个帖子，或者只跳过评论看需求。这里假设如果是官方发的贴，可能就是广，跳过
            
        raw_comments = item.get('comments', [])
        if isinstance(raw_comments, str):
            raw_comments = [raw_comments]
        
        # 评论去重
        seen_comments = set()
        for c in raw_comments:
            if not c: continue
            
            # 先清理评论内容（去除日期、地区等）
            c_cleaned = clean_text_content(c)
            if not c_cleaned:
                continue
            
            # 评论去重（使用清理后的内容）
            if c_cleaned in seen_comments:
                continue
            seen_comments.add(c_cleaned)
            
            # 规则1: 长度过短视为无效（使用用户设置的最小长度）
            if len(c_cleaned) < min_length:
                continue
                
            # 规则2: 评论内容包含官方话术或自定义过滤词
            should_filter = False
            default_filter_words = ["私信", "联系我", "关注"]
            all_filter_words = default_filter_words + (custom_keywords or [])
            
            for word in all_filter_words:
                if word in c_cleaned:
                    should_filter = True
                    break
            
            if should_filter:
                continue
                
            valid_comments.append(c_cleaned)
            
        if valid_comments:
            # 重新组装，同时清理内容字段
            new_item = item.copy()
            new_item['comments'] = valid_comments
            # 清理content字段
            if new_item.get('content'):
                new_item['content'] = clean_text_content(new_item['content'])
            # 清理title字段
            if new_item.get('title'):
                new_item['title'] = clean_text_content(new_item['title'])
            cleaned_data.append(new_item)
            
    return cleaned_data