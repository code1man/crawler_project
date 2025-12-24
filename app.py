import io
import json
import os
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, Response
from spiders.xhs_spider import search_and_crawl_xhs
from spiders.zhihu_spider import search_and_crawl_zhihu
from utils.cleaner import clean_comments
from utils.ai_agent import analyze_sentiment_by_coze, batch_analyze_by_coze, batch_analyze_csv_by_coze, generate_csv_content
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_absolute_error, mean_squared_error, r2_score

app = Flask(__name__)

# 内存中临时存储数据
GLOBAL_DATA = []
GLOBAL_CRAWL_INFO = {
    'platform': '',
    'keywords': []
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download_template')
def download_template():
    """
    生成并下载标准的 CSV 模板
    格式与clean文件一致：keyword, url, user, comment_content
    """
    # 定义标准表头（与clean文件格式一致）
    headers = {
        "keyword": ["AI问诊", "智能医疗"],
        "url": ["https://example.com/post1", "https://example.com/post2"],
        "user": ["用户A", "用户B"],
        "comment_content": ["这是第一条评论内容", "这是第二条评论内容"]
    }
    df = pd.DataFrame(headers)
    
    # 写入内存 buffer
    buffer = io.BytesIO()
    # 使用 utf-8-sig 编码，防止 Excel 打开中文乱码
    df.to_csv(buffer, index=False, encoding='utf-8-sig')
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name='data_template.csv',
        mimetype='text/csv'
    )

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """
    处理 CSV 上传，解析并清洗
    """
    global GLOBAL_DATA
    
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"code": 400, "msg": "文件名为空"})

    # 获取过滤参数
    filter_keywords_str = request.form.get('filter_keywords', '')
    min_length = int(request.form.get('min_length', 4))
    
    # 解析过滤关键词列表
    filter_keywords = [k.strip() for k in filter_keywords_str.split(',') if k.strip()]

    try:
        # 读取 CSV
        df = pd.read_csv(file)
        
        # 1. 验证表头 - 支持新格式(keyword,url,user,comment_content)和旧格式
        new_format_columns = ['keyword', 'url', 'user', 'comment_content']
        old_format_columns = ['content', 'comments']
        
        is_new_format = all(col in df.columns for col in new_format_columns)
        is_old_format = all(col in df.columns for col in old_format_columns)
        
        if not is_new_format and not is_old_format:
            return jsonify({
                "code": 400, 
                "msg": f"CSV格式错误，需要列: {new_format_columns} 或 {old_format_columns}。请下载模板查看。"
            })
        
        # 2. 转换格式为系统内部结构
        raw_data = []
        
        if is_new_format:
            # 新格式：keyword, url, user, comment_content（与clean文件一致）
            for _, row in df.iterrows():
                comment = str(row.get('comment_content', ''))
                if pd.isna(row.get('comment_content')) or not comment.strip():
                    continue
                    
                item = {
                    "source": "用户上传",
                    "title": str(row.get('keyword', '')),
                    "author": str(row.get('user', '匿名')),
                    "content": comment,
                    "comments": [comment],
                    "url": str(row.get('url', '#'))
                }
                raw_data.append(item)
        else:
            # 旧格式：兼容处理
            for _, row in df.iterrows():
                comments_str = str(row.get('comments', ''))
                if pd.isna(row.get('comments')):
                    comments_list = []
                else:
                    comments_list = comments_str.split('|||')
                
                comments_list = [c.strip() for c in comments_list if c.strip()]

                item = {
                    "source": str(row.get('source', '用户上传')),
                    "title": str(row.get('title', '')),
                    "author": str(row.get('author', '匿名')),
                    "content": str(row.get('content', '')),
                    "comments": comments_list,
                    "url": "#"
                }
                raw_data.append(item)
            
        # 3. 进行数据清洗 (使用用户自定义的过滤参数)
        cleaned_data = clean_comments(raw_data, custom_keywords=filter_keywords, min_length=min_length)
        GLOBAL_DATA = cleaned_data
        
        return jsonify({
            "code": 200,
            "msg": f"上传成功！共解析 {len(raw_data)} 条，清洗后剩余 {len(cleaned_data)} 条有效数据",
            "data": cleaned_data
        })

    except Exception as e:
        print(f"Upload Error: {e}")
        return jsonify({"code": 500, "msg": f"文件解析失败: {str(e)}"})


@app.route('/api/crawl', methods=['POST'])
def crawl():
    global GLOBAL_DATA
    data = request.json
    keyword = data.get('keyword')
    platform = data.get('platform')
    # 获取前端传来的 cookie
    user_cookie = data.get('cookie')
    # 获取爬取数量，默认5
    max_count = int(data.get('max_count', 5))
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入关键词"})
    
    print(f"开始爬取: {platform} - {keyword} - 数量: {max_count}")
    
    raw_data = []
    if platform == 'xhs':
        # 小红书不需要传 cookie，它使用本地浏览器自动化
        raw_data = search_and_crawl_xhs(keyword, max_count=max_count)
    elif platform == 'zhihu':
        # 将 cookie 传递给知乎爬虫
        raw_data = search_and_crawl_zhihu(keyword, max_count=max_count, cookie_str=user_cookie)
    
    cleaned_data = clean_comments(raw_data)
    GLOBAL_DATA = cleaned_data
    
    return jsonify({
        "code": 200, 
        "msg": "爬取完成", 
        "data": cleaned_data
    })


@app.route('/api/crawl_batch', methods=['POST'])
def crawl_batch():
    """
    分批爬取接口 - 每次爬取一批数据，支持分页展示
    """
    global GLOBAL_DATA, GLOBAL_CRAWL_INFO
    data = request.json
    keyword = data.get('keyword')
    platform = data.get('platform')
    user_cookie = data.get('cookie')
    batch_size = int(data.get('batch_size', 50))
    offset = int(data.get('offset', 0))
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入关键词"})
    
    # 记录爬取信息
    GLOBAL_CRAWL_INFO['platform'] = platform
    if keyword not in GLOBAL_CRAWL_INFO['keywords']:
        GLOBAL_CRAWL_INFO['keywords'].append(keyword)
    
    print(f"分批爬取: {platform} - {keyword} - 批次大小: {batch_size}, 偏移: {offset}")
    
    raw_data = []
    if platform == 'xhs':
        raw_data = search_and_crawl_xhs(keyword, max_count=batch_size)
    elif platform == 'zhihu':
        raw_data = search_and_crawl_zhihu(keyword, max_count=batch_size, cookie_str=user_cookie, offset=offset)
    
    print(f"[DEBUG] 爬取完成: 原始数据 {len(raw_data)} 条")
    cleaned_data = clean_comments(raw_data)
    print(f"[DEBUG] 清洗完成: 清洗后 {len(cleaned_data)} 条")
    
    # 追加到全局数据（用于下载）
    GLOBAL_DATA.extend(cleaned_data)
    
    return jsonify({
        "code": 200, 
        "msg": f"本批次获取 {len(cleaned_data)} 条数据", 
        "data": cleaned_data
    })


@app.route('/api/download_data')
def download_data():
    """
    下载已爬取的数据为CSV（使用clean文件格式）
    """
    global GLOBAL_DATA
    
    if not GLOBAL_DATA:
        return jsonify({"code": 400, "msg": "没有数据可下载"})
    
    # 转换为DataFrame（使用clean文件格式：keyword, url, user, comment_content）
    rows = []
    for item in GLOBAL_DATA:
        # 每条评论生成一行（与clean文件格式一致）
        comments = item.get('comments', [])
        if comments:
            for comment in comments:
                rows.append({
                    "keyword": item.get('title', ''),  # title作为keyword
                    "url": item.get('url', ''),
                    "user": item.get('author', ''),
                    "comment_content": comment,
                    "ai_analysis": item.get('ai_analysis', '')  # 保留AI分析结果
                })
        else:
            # 没有评论时，用content作为comment_content
            rows.append({
                "keyword": item.get('title', ''),
                "url": item.get('url', ''),
                "user": item.get('author', ''),
                "comment_content": item.get('content', ''),
                "ai_analysis": item.get('ai_analysis', '')
            })
    
    df = pd.DataFrame(rows)
    
    # 生成文件名：平台+关键词_spider_result
    platform = GLOBAL_CRAWL_INFO.get('platform', 'unknown')
    keywords = GLOBAL_CRAWL_INFO.get('keywords', [])
    # 平台名称映射
    platform_name = {'xhs': '小红书', 'zhihu': '知乎'}.get(platform, platform)
    # 关键词拼接（最多取前3个，用下划线连接）
    keywords_str = '_'.join(keywords[:3]) if keywords else '数据'
    # 清理文件名中的非法字符
    import re
    keywords_str = re.sub(r'[\\/:*?"<>|]', '', keywords_str)
    filename = f"{platform_name}_{keywords_str}_spider_result.csv"
    
    # 写入内存buffer
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8-sig')
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )


@app.route('/api/analyze', methods=['POST'])
def analyze():
    global GLOBAL_DATA
    if not GLOBAL_DATA:
        return jsonify({"code": 400, "msg": "没有数据可分析，请先爬取或上传CSV"})
    
    # 获取分析参数
    data = request.json or {}
    max_count = int(data.get('max_count', 0))  # 0表示全部
    
    # 确定分析数量
    items_to_analyze = GLOBAL_DATA if max_count == 0 else GLOBAL_DATA[:max_count]
    
    results = []
    for item in items_to_analyze: 
        # 如果已经分析过，跳过
        if 'ai_analysis' in item and item['ai_analysis']:
            results.append(item)
            continue

        full_text = f"标题：{item['title']}\n内容摘要：{item['content']}\n用户评论：{'; '.join(item['comments'])}"
        ai_result = analyze_sentiment_by_coze(full_text)
        item['ai_analysis'] = ai_result
        results.append(item)
        
    # 更新全局数据
    for i, result in enumerate(results):
        if i < len(GLOBAL_DATA):
            GLOBAL_DATA[i] = result
            
    return jsonify({
        "code": 200,
        "msg": f"分析完成，共处理 {len(results)} 条",
        "data": GLOBAL_DATA
    })


@app.route('/api/analyze_batch', methods=['POST'])
def analyze_batch():
    """
    批量AI分析接口 - 每50条生成CSV文件发送给AI
    使用Server-Sent Events (SSE) 实时返回进度
    """
    global GLOBAL_DATA
    if not GLOBAL_DATA:
        return jsonify({"code": 400, "msg": "没有数据可分析"})
    
    data = request.json or {}
    batch_size = int(data.get('batch_size', 50))  # 默认每批50条
    max_count = int(data.get('max_count', 0))  # 0表示全部
    
    # 确定分析数量
    items_to_analyze = GLOBAL_DATA if max_count == 0 else GLOBAL_DATA[:max_count]
    total = len(items_to_analyze)
    total_batches = (total + batch_size - 1) // batch_size  # 向上取整
    
    def generate():
        all_results = []
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total)
            batch_data = items_to_analyze[start_idx:end_idx]
            
            # 发送批次开始通知
            yield f"data: {json.dumps({'batch': batch_num + 1, 'total_batches': total_batches, 'status': 'processing', 'msg': f'正在处理第 {batch_num + 1}/{total_batches} 批（{start_idx + 1}-{end_idx} 条）'}, ensure_ascii=False)}\n\n"
            
            try:
                # 生成CSV内容并发送给AI
                csv_content = generate_csv_content(batch_data)
                
                from utils.ai_agent import analyze_csv_by_coze
                ai_result = analyze_csv_by_coze(csv_content)
                
                # 存储结果
                batch_result = {
                    'batch_num': batch_num + 1,
                    'start_idx': start_idx,
                    'end_idx': end_idx,
                    'count': len(batch_data),
                    'result': ai_result
                }
                all_results.append(batch_result)
                
                # 发送批次完成通知
                yield f"data: {json.dumps({'batch': batch_num + 1, 'total_batches': total_batches, 'status': 'batch_complete', 'result': ai_result, 'count': len(batch_data)}, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'batch': batch_num + 1, 'total_batches': total_batches, 'status': 'error', 'msg': f'批次 {batch_num + 1} 分析失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            
            # 批次间休息（避免API限流）
            if batch_num + 1 < total_batches:
                import time
                time.sleep(2)
        
        # 完成
        yield f"data: {json.dumps({'batch': total_batches, 'total_batches': total_batches, 'status': 'complete', 'msg': f'分析完成，共处理 {total_batches} 批 {total} 条数据', 'all_results': all_results}, ensure_ascii=False)}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/clear_data', methods=['POST'])
def clear_data():
    """清空全局数据"""
    global GLOBAL_DATA, CRAWL_INFO
    GLOBAL_DATA = []
    CRAWL_INFO = {"platform": "", "keywords": []}
    return jsonify({"code": 200, "msg": "数据已清空"})


# ==================== TXT分析 & 词云生成 ====================

@app.route('/api/upload_analysis_txt', methods=['POST'])
def upload_analysis_txt():
    """
    上传AI分析结果TXT文件，解析并生成词云数据
    TXT格式为JSON数组，每项包含 is_valid, keywords, sentiment
    """
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"code": 400, "msg": "文件名为空"})
    
    try:
        # 读取文件内容
        content = file.read().decode('utf-8')
        
        # 解析JSON数组
        data_list = json.loads(content)
        
        # 过滤有效数据 (is_valid=true)
        valid_data = []
        for item in data_list:
            # 如果是字符串，先解析
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except:
                    continue
            
            if item.get('is_valid', False):
                valid_data.append(item)
        
        # 统计关键词频率
        keyword_count = {}
        for item in valid_data:
            keywords = item.get('keywords', [])
            for kw in keywords:
                if kw:
                    keyword_count[kw] = keyword_count.get(kw, 0) + 1
        
        # 统计情感分布
        sentiment_count = {'positive': 0, 'negative': 0, 'neutral': 0}
        for item in valid_data:
            sentiment = item.get('sentiment', 'neutral')
            if sentiment in sentiment_count:
                sentiment_count[sentiment] += 1
        
        # 转换为词云格式 [{name: "xx", value: 10}, ...]
        wordcloud_data = [{"name": k, "value": v} for k, v in keyword_count.items()]
        wordcloud_data.sort(key=lambda x: x['value'], reverse=True)
        
        # 情感分布饼图数据
        sentiment_data = [
            {"name": "正面 (Positive)", "value": sentiment_count['positive']},
            {"name": "负面 (Negative)", "value": sentiment_count['negative']},
            {"name": "中性 (Neutral)", "value": sentiment_count['neutral']}
        ]
        
        return jsonify({
            "code": 200,
            "msg": f"解析成功，有效数据 {len(valid_data)} 条，关键词 {len(keyword_count)} 个",
            "data": {
                "total": len(data_list),
                "valid_count": len(valid_data),
                "wordcloud": wordcloud_data[:100],  # 最多100个关键词
                "sentiment": sentiment_data,
                "valid_data": valid_data  # 返回有效数据用于后续合并
            }
        })
        
    except json.JSONDecodeError as e:
        return jsonify({"code": 400, "msg": f"JSON解析失败: {str(e)}"})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"处理失败: {str(e)}"})


@app.route('/api/merge_csv_with_analysis', methods=['POST'])
def merge_csv_with_analysis():
    """
    合并原始CSV和TXT分析结果，生成带分析结果的CSV
    """
    if 'csv_file' not in request.files or 'txt_file' not in request.files:
        return jsonify({"code": 400, "msg": "需要同时上传CSV和TXT文件"})
    
    csv_file = request.files['csv_file']
    txt_file = request.files['txt_file']
    
    try:
        # 读取CSV - 尝试多种编码
        csv_content = csv_file.read()
        df = None
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin1']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(io.BytesIO(csv_content), encoding=encoding)
                print(f"[INFO] CSV使用编码 {encoding} 解析成功")
                break
            except Exception as e:
                continue
        
        if df is None:
            return jsonify({"code": 400, "msg": "无法解析CSV文件，请检查文件编码"})
        
        # 读取TXT分析结果 - 尝试多种编码
        txt_bytes = txt_file.read()
        txt_content = None
        for encoding in encodings:
            try:
                txt_content = txt_bytes.decode(encoding)
                print(f"[INFO] TXT使用编码 {encoding} 解析成功")
                break
            except:
                continue
        
        if txt_content is None:
            return jsonify({"code": 400, "msg": "无法解析TXT文件，请检查文件编码"})
        
        analysis_list = json.loads(txt_content)
        
        # 解析分析结果
        parsed_analysis = []
        for item in analysis_list:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except:
                    item = {"is_valid": False, "keywords": [], "sentiment": "neutral"}
            parsed_analysis.append(item)
        
        # 确保长度匹配
        if len(df) != len(parsed_analysis):
            return jsonify({
                "code": 400, 
                "msg": f"数据长度不匹配: CSV有{len(df)}行，TXT有{len(parsed_analysis)}条分析结果"
            })
        
        # 添加分析结果列
        df['is_valid'] = [item.get('is_valid', False) for item in parsed_analysis]
        df['keywords'] = [','.join(item.get('keywords', [])) for item in parsed_analysis]
        df['sentiment'] = [item.get('sentiment', 'neutral') for item in parsed_analysis]
        
        # 过滤有效数据
        df_valid = df[df['is_valid'] == True].copy()
        
        # 写入内存buffer
        buffer = io.BytesIO()
        df_valid.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name='merged_analysis_result.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": f"合并失败: {str(e)}"})


@app.route('/api/analyze_merged_csv', methods=['POST'])
def analyze_merged_csv():
    """
    分析已合并的CSV文件（包含keywords和sentiment列），生成词云和情感分布
    """
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    file = request.files['file']
    
    try:
        df = pd.read_csv(file)
        
        # 检查必要的列
        if 'keywords' not in df.columns or 'sentiment' not in df.columns:
            return jsonify({"code": 400, "msg": "CSV必须包含 keywords 和 sentiment 列"})
        
        # 统计关键词频率
        keyword_count = {}
        for keywords_str in df['keywords'].dropna():
            keywords = str(keywords_str).split(',')
            for kw in keywords:
                kw = kw.strip()
                if kw:
                    keyword_count[kw] = keyword_count.get(kw, 0) + 1
        
        # 统计情感分布
        sentiment_count = df['sentiment'].value_counts().to_dict()
        
        # 转换为词云格式
        wordcloud_data = [{"name": k, "value": v} for k, v in keyword_count.items()]
        wordcloud_data.sort(key=lambda x: x['value'], reverse=True)
        
        # 情感分布饼图数据
        sentiment_data = [
            {"name": "正面 (Positive)", "value": sentiment_count.get('positive', 0)},
            {"name": "负面 (Negative)", "value": sentiment_count.get('negative', 0)},
            {"name": "中性 (Neutral)", "value": sentiment_count.get('neutral', 0)}
        ]
        
        return jsonify({
            "code": 200,
            "msg": f"分析成功，共 {len(df)} 条数据",
            "data": {
                "total": len(df),
                "wordcloud": wordcloud_data[:100],
                "sentiment": sentiment_data
            }
        })
        
    except Exception as e:
        return jsonify({"code": 500, "msg": f"分析失败: {str(e)}"})


def read_csv_with_encoding(file_content):
    """尝试多种编码读取CSV"""
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin1']
    for encoding in encodings:
        try:
            return pd.read_csv(io.BytesIO(file_content), encoding=encoding)
        except:
            continue
    return None


def _read_csv_file(path):
    try:
        with open(path, 'rb') as f:
            content = f.read()
        return read_csv_with_encoding(content)
    except:
        return None


def _load_latest_analysis_df():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    result_dir = os.path.join(base_dir, 'resource', 'result')
    if not os.path.isdir(result_dir):
        return None, None, "未找到 resource/result 目录"

    candidates = []
    for name in os.listdir(result_dir):
        if not name.lower().endswith('.csv'):
            continue
        path = os.path.join(result_dir, name)
        df = _read_csv_file(path)
        if df is None:
            continue
        cols = set(df.columns)
        if 'comment_content' not in cols or 'sentiment' not in cols:
            continue
        if 'is_valid' in cols:
            df = df[df['is_valid'].astype(str).str.lower().isin(['true', '1', 'yes'])].copy()
        df['sentiment'] = df['sentiment'].astype(str).str.lower().str.strip()
        df['comment_content'] = df['comment_content'].astype(str)
        if len(df) == 0:
            continue
        candidates.append((len(df), name, df))

    if not candidates:
        return None, None, "没有可用的分析CSV（需包含 comment_content 和 sentiment 列）"

    candidates.sort(key=lambda x: x[0], reverse=True)
    rows, name, df = candidates[0]
    info = {"file": name, "rows": rows}
    return df, info, None


def _train_sentiment_classifier(df):
    allowed = {'positive', 'negative', 'neutral'}
    df = df[df['sentiment'].isin(allowed)].copy()
    if len(df) < 50:
        return {"status": "insufficient", "msg": "可用样本不足（<50）"}
    if df['sentiment'].nunique() < 2:
        return {"status": "insufficient", "msg": "类别数量不足，无法训练分类模型"}

    x_text = df['comment_content'].fillna('').astype(str)
    y = df['sentiment']
    stratify = y if y.nunique() > 1 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x_text, y, test_size=0.2, random_state=42, stratify=stratify
    )

    vectorizer = TfidfVectorizer(max_features=2000)
    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    model = LogisticRegression(max_iter=1000)
    model.fit(x_train_vec, y_train)

    preds = model.predict(x_test_vec)
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision_macro": float(precision_score(y_test, preds, average='macro', zero_division=0)),
        "recall_macro": float(recall_score(y_test, preds, average='macro', zero_division=0)),
        "f1_macro": float(f1_score(y_test, preds, average='macro', zero_division=0))
    }
    label_dist = y.value_counts().to_dict()
    return {
        "status": "ok",
        "metrics": metrics,
        "labels": label_dist,
        "sample_count": int(len(df))
    }


def _train_trend_model(df):
    sentiment_map = {'positive': 1.0, 'neutral': 0.0, 'negative': -1.0}
    scores = [sentiment_map.get(s) for s in df['sentiment'] if sentiment_map.get(s) is not None]
    if len(scores) < 30:
        return {"status": "insufficient", "msg": "可用样本不足（<30）"}

    window = max(5, min(20, len(scores) // 5))
    history = []
    for i in range(window - 1, len(scores)):
        history.append(float(np.mean(scores[i - window + 1:i + 1])))

    lag = 3
    if len(history) <= lag + 5:
        return {"status": "insufficient", "msg": "趋势序列过短，无法训练"}

    x = []
    y = []
    for i in range(lag, len(history)):
        x.append(history[i - lag:i])
        y.append(history[i])
    x = np.array(x)
    y = np.array(y)

    split_idx = int(len(x) * 0.8) if len(x) >= 10 else len(x)
    x_train = x[:split_idx]
    y_train = y[:split_idx]
    model = LinearRegression()
    model.fit(x_train, y_train)

    metrics = None
    if len(x) - split_idx >= 1:
        preds = model.predict(x[split_idx:])
        metrics = {
            "mae": float(mean_absolute_error(y[split_idx:], preds)),
            "rmse": float(np.sqrt(mean_squared_error(y[split_idx:], preds))),
            "r2": float(r2_score(y[split_idx:], preds))
        }

    horizon = 7
    recent = list(history[-lag:])
    forecast = []
    for _ in range(horizon):
        pred = float(model.predict(np.array(recent).reshape(1, -1))[0])
        forecast.append(pred)
        recent = recent[1:] + [pred]

    return {
        "status": "ok",
        "history": history,
        "forecast": forecast,
        "window": int(window),
        "lag": int(lag),
        "horizon": int(horizon),
        "metrics": metrics
    }


def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_trend_forecast(path, history, forecast):
    rows = []
    for i, v in enumerate(history, start=1):
        rows.append({"index": i, "value": v, "type": "history"})
    start = len(history) + 1
    for i, v in enumerate(forecast, start=start):
        rows.append({"index": i, "value": v, "type": "forecast"})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding='utf-8-sig')


@app.route('/api/merge_multiple_csv', methods=['POST'])
def merge_multiple_csv():
    """
    合并多个CSV文件为一个
    """
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    if len(files) < 2:
        return jsonify({"code": 400, "msg": "请至少上传2个CSV文件进行合并"})
    
    try:
        all_dfs = []
        file_info = []
        
        for i, file in enumerate(files):
            content = file.read()
            df = read_csv_with_encoding(content)
            
            if df is None:
                return jsonify({"code": 400, "msg": f"文件 {file.filename} 编码无法识别"})
            
            # 添加来源列
            df['source_file'] = file.filename
            all_dfs.append(df)
            file_info.append({"name": file.filename, "rows": len(df)})
        
        # 合并所有DataFrame
        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        # 写入内存buffer
        buffer = io.BytesIO()
        merged_df.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name='merged_all_csv.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": f"合并失败: {str(e)}"})


@app.route('/api/analyze_multiple_csv', methods=['POST'])
def analyze_multiple_csv():
    """
    分析多个CSV文件，统一生成词云和情感分布
    支持两种格式：
    1. 包含 keywords 和 sentiment 列的已分析CSV
    2. 原始格式CSV（会统计评论词频）
    """
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    try:
        all_dfs = []
        file_info = []
        total_rows = 0
        
        for file in files:
            content = file.read()
            df = read_csv_with_encoding(content)
            
            if df is None:
                return jsonify({"code": 400, "msg": f"文件 {file.filename} 编码无法识别"})
            
            df['source_file'] = file.filename
            all_dfs.append(df)
            file_info.append({"name": file.filename, "rows": len(df)})
            total_rows += len(df)
        
        # 合并所有DataFrame
        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        # 判断是否包含分析结果列
        has_analysis = 'keywords' in merged_df.columns and 'sentiment' in merged_df.columns
        
        keyword_count = {}
        sentiment_count = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        if has_analysis:
            # 模式1：已分析的CSV，统计keywords和sentiment
            for keywords_str in merged_df['keywords'].dropna():
                keywords = str(keywords_str).split(',')
                for kw in keywords:
                    kw = kw.strip()
                    if kw:
                        keyword_count[kw] = keyword_count.get(kw, 0) + 1
            
            for sentiment in merged_df['sentiment'].dropna():
                sentiment = str(sentiment).lower().strip()
                if sentiment in sentiment_count:
                    sentiment_count[sentiment] += 1
        else:
            # 模式2：原始CSV，统计评论内容词频
            # 查找可能的评论列
            comment_cols = ['comment_content', 'content', 'comments', 'text', '评论']
            comment_col = None
            for col in comment_cols:
                if col in merged_df.columns:
                    comment_col = col
                    break
            
            if comment_col:
                import re
                for text in merged_df[comment_col].dropna():
                    text = str(text)
                    # 简单分词：按标点和空格分割
                    words = re.split(r'[，。！？、；：\s,.!?;:\n]+', text)
                    for word in words:
                        word = word.strip()
                        if len(word) >= 2:  # 至少2个字符
                            keyword_count[word] = keyword_count.get(word, 0) + 1
            
            # 无情感数据时标记为未知
            sentiment_count = {'positive': 0, 'negative': 0, 'neutral': total_rows}
        
        # 转换为词云格式
        wordcloud_data = [{"name": k, "value": v} for k, v in keyword_count.items()]
        wordcloud_data.sort(key=lambda x: x['value'], reverse=True)
        
        # 情感分布饼图数据
        sentiment_data = [
            {"name": "正面 (Positive)", "value": sentiment_count.get('positive', 0)},
            {"name": "负面 (Negative)", "value": sentiment_count.get('negative', 0)},
            {"name": "中性 (Neutral)", "value": sentiment_count.get('neutral', 0)}
        ]
        
        # 各文件统计
        per_file_stats = []
        for df in all_dfs:
            file_name = df['source_file'].iloc[0] if len(df) > 0 else 'unknown'
            file_stat = {
                "name": file_name,
                "total": len(df),
                "positive": 0,
                "negative": 0,
                "neutral": 0
            }
            if has_analysis and 'sentiment' in df.columns:
                for s in df['sentiment'].dropna():
                    s = str(s).lower().strip()
                    if s in file_stat:
                        file_stat[s] += 1
            per_file_stats.append(file_stat)
        
        return jsonify({
            "code": 200,
            "msg": f"分析成功，共 {len(files)} 个文件，{total_rows} 条数据",
            "data": {
                "total": total_rows,
                "file_count": len(files),
                "files": file_info,
                "has_analysis": has_analysis,
                "wordcloud": wordcloud_data[:100],
                "sentiment": sentiment_data,
                "per_file_stats": per_file_stats
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": f"分析失败: {str(e)}"})


@app.route('/api/ml/train_predict', methods=['POST'])
def ml_train_predict():
    df, info, err = _load_latest_analysis_df()
    if err:
        return jsonify({"code": 400, "msg": err})

    classification = _train_sentiment_classifier(df)
    trend = _train_trend_model(df)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    result_dir = os.path.join(base_dir, 'resource', 'result')
    os.makedirs(result_dir, exist_ok=True)

    if classification.get("status") == "ok":
        _save_json(os.path.join(result_dir, 'ml_classification_metrics.json'), {
            "data_info": info,
            "metrics": classification.get("metrics"),
            "labels": classification.get("labels"),
            "sample_count": classification.get("sample_count")
        })

    if trend.get("status") == "ok":
        _save_json(os.path.join(result_dir, 'ml_trend_metrics.json'), {
            "data_info": info,
            "metrics": trend.get("metrics"),
            "window": trend.get("window"),
            "lag": trend.get("lag"),
            "horizon": trend.get("horizon")
        })
        _save_trend_forecast(
            os.path.join(result_dir, 'ml_trend_forecast.csv'),
            trend.get("history", []),
            trend.get("forecast", [])
        )

    return jsonify({
        "code": 200,
        "msg": "预测完成",
        "data": {
            "data_info": info,
            "classification": classification,
            "trend": trend
        }
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
