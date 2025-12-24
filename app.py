# -*- coding: utf-8 -*-
"""
舆情分析系统 - SOA 架构主入口
"""
import io
import zipfile
import json
import re
import pandas as pd
from flask import send_file
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_cors import CORS
from config import config
from models import db
from utils import ai_agent

# 创建应用
app = Flask(__name__)

# 加载配置
app.config.from_object(config['development'])

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
db.init_app(app)

from api import api
from api.auth_api import auth_ns
from api.user_api import user_ns
from api.crawler_api import crawler_ns
from api.audit_api import audit_ns
from api.watch_api import watch_ns

api.init_app(app)
api.add_namespace(auth_ns, path='/auth')
api.add_namespace(user_ns, path='/user')
api.add_namespace(crawler_ns, path='/crawler')
api.add_namespace(audit_ns, path='/audit')
api.add_namespace(watch_ns, path='/watch')

# ==================== 头像静态文件路由 ====================
import os
from flask import send_from_directory

@app.route('/avatars/<filename>')
def serve_avatar(filename):
    """提供头像文件访问"""
    avatar_folder = app.config.get('AVATAR_UPLOAD_FOLDER', 'static/avatars')
    return send_from_directory(avatar_folder, filename)


@app.route('/js/<path:filename>')
def serve_js(filename):
    """提供项目根目录下 js/ 文件夹中的静态文件（兼容模板中 /js/* 引用）"""
    js_folder = os.path.join(app.root_path, 'js')
    return send_from_directory(js_folder, filename)

# ==================== 页面路由 ====================
@app.route('/')
def index():
    """主页（需要登录）"""
    return render_template('index.html')


@app.route('/login')
def login():
    """登录页"""
    error = request.args.get('error')
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect('/login')


@app.route('/complete-profile')
def complete_profile():
    """完善信息页面（Gitee 用户设置密码）"""
    return render_template('complete_profile.html')


@app.route('/user-settings')
def user_settings():
    """用户设置页面"""
    return render_template('user_settings.html')


@app.route('/change-password')
def change_password_page():
    """修改密码页面"""
    return render_template('change_password.html')


# # ==================== 兼容 Gitee OAuth 回调（旧路径） ====================
# Gitee OAuth 应用配置的回调地址是 /auth/gitee/callback
@app.route('/auth/gitee/login')
def gitee_login():
    """跳转到 Gitee 授权页面"""
    from services.auth_service import AuthService
    auth_url = AuthService.get_gitee_auth_url()
    return redirect(auth_url)

@app.route('/auth/gitee/callback')
def gitee_callback():
    """处理 Gitee OAuth 回调"""
    from services.auth_service import AuthService
    from services.audit_service import AuditService
    
    code = request.args.get('code')
    
    if not code:
        return redirect('/login?error=no_code')
    
    # 1. 换取 access_token
    access_token = AuthService.exchange_code_for_token(code)
    if not access_token:
        return redirect('/login?error=token_exchange_failed')


    # 2. 获取用户信息
    gitee_user = AuthService.get_gitee_user_info(access_token)
    if not gitee_user:
        return redirect('/login?error=user_info_failed')
    
    # 3. 登录或注册（使用新方法名）
    user, is_new = AuthService.login_or_register_gitee(gitee_user)
    
    # 4. 记录登录日志
    AuditService.log_login(user.id, login_type='gitee')
    
    # 5. 生成 JWT（包含 status）
    jwt_token = AuthService.generate_jwt(user)
    
    # 6. 判断账号是否完整
    status = 'complete' if user.is_profile_complete else 'incomplete'
    
    # 7. 重定向到前端，携带 token 和 status
    from urllib.parse import quote
    return redirect(f'/?token={jwt_token}&username={quote(user.username)}&avatar_url={quote(user.avatar_url or "")}&status={status}')

# 全局数据存储
from services.in_memory_store import GLOBAL_DATA, GLOBAL_CRAWL_INFO

@app.route('/api/download_template')
def download_template():
    """下载 CSV 模板"""
    headers = {
        "keyword": ["AI问诊", "智能医疗"],
        "url": ["https://example.com/post1", "https://example.com/post2"],
        "user": ["用户A", "用户B"],
        "comment_content": ["这是第一条评论内容", "这是第二条评论内容"]
    }
    df = pd.DataFrame(headers)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8-sig')
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='data_template.csv', mimetype='text/csv')

@app.route('/api/crawl_batch', methods=['POST'])
def crawl_batch():
    """分批爬取接口"""
    global GLOBAL_DATA, GLOBAL_CRAWL_INFO
    from spiders.xhs_spider import search_and_crawl_xhs
    from spiders.zhihu_spider import search_and_crawl_zhihu
    from utils.cleaner import clean_comments
    
    data = request.json
    keyword = data.get('keyword')
    platform = data.get('platform')
    user_cookie = data.get('cookie')
    batch_size = int(data.get('batch_size', 50))
    offset = int(data.get('offset', 0))
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入关键词"})
    
    GLOBAL_CRAWL_INFO['platform'] = platform
    if keyword not in GLOBAL_CRAWL_INFO['keywords']:
        GLOBAL_CRAWL_INFO['keywords'].append(keyword)
    
    print(f"分批爬取: {platform} - {keyword} - 批次大小: {batch_size}, 偏移: {offset}")
    
    raw_data = []
    if platform == 'xhs':
        raw_data = search_and_crawl_xhs(keyword, max_count=batch_size)
    elif platform == 'zhihu':
        raw_data = search_and_crawl_zhihu(keyword, max_count=batch_size, cookie_str=user_cookie, offset=offset)
    
    cleaned_data = clean_comments(raw_data)
    GLOBAL_DATA.extend(cleaned_data)
    
    return jsonify({"code": 200, "msg": f"本批次获取 {len(cleaned_data)} 条数据", "data": cleaned_data})

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """处理 CSV 上传"""
    global GLOBAL_DATA
    from utils.cleaner import clean_comments
    
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"code": 400, "msg": "文件名为空"})
    
    filter_keywords_str = request.form.get('filter_keywords', '')
    min_length = int(request.form.get('min_length', 4))
    filter_keywords = [k.strip() for k in filter_keywords_str.split(',') if k.strip()]
    
    try:
        df = pd.read_csv(file)
        new_format_columns = ['keyword', 'url', 'user', 'comment_content']
        is_new_format = all(col in df.columns for col in new_format_columns)
        
        raw_data = []
        if is_new_format:
            for _, row in df.iterrows():
                comment = str(row.get('comment_content', ''))
                if pd.isna(row.get('comment_content')) or not comment.strip():
                    continue
                raw_data.append({
                    "source": "用户上传", "title": str(row.get('keyword', '')),
                    "author": str(row.get('user', '匿名')), "content": comment,
                    "comments": [comment], "url": str(row.get('url', '#'))
                })
        
        cleaned_data = clean_comments(raw_data, custom_keywords=filter_keywords, min_length=min_length)
        GLOBAL_DATA = cleaned_data
        return jsonify({"code": 200, "msg": f"上传成功！共 {len(cleaned_data)} 条有效数据", "data": cleaned_data})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"文件解析失败: {str(e)}"})

@app.route('/api/download_data', methods=['GET', 'POST'])
def download_data():
    """下载爬取的数据"""
    global GLOBAL_DATA, GLOBAL_CRAWL_INFO
    # 支持通过 POST 传入数据（前端直接上传当前 tableData），优先使用 POST 的 JSON payload
    payload_rows = None
    if request.method == 'POST' and request.is_json:
        payload = request.get_json(silent=True) or {}
        payload_rows = payload.get('rows')

    source_data = payload_rows if payload_rows is not None else GLOBAL_DATA

    if not source_data:
        return jsonify({"code": 400, "msg": "没有数据可下载"})

    rows = []
    # 判断是否存在 ai_analysis 并选择输出列
    has_ai = any(item.get('ai_analysis') for item in source_data)

    for item in source_data:
        comments = item.get('comments', [])
        if comments:
            for comment in comments:
                base = {
                    "keyword": item.get('title', ''),
                    "url": item.get('url', ''),
                    "user": item.get('author', ''),
                    "comment_content": comment
                }

                ai = item.get('ai_analysis')
                if ai:
                    # 如果 ai_analysis 是 dict 且包含常见字段，则拆分到单独列
                    if isinstance(ai, dict) and ("is_valid" in ai or "keywords" in ai or "sentiment" in ai):
                        base['is_valid'] = ai.get('is_valid', False)
                        kws = ai.get('keywords', []) or ai.get('keyword', [])
                        # 关键词可能为字符串或数组
                        if isinstance(kws, str):
                            base['keywords'] = kws
                        else:
                            base['keywords'] = ','.join(kws)
                        base['sentiment'] = ai.get('sentiment', '')
                    else:
                        # 否则序列化整个 ai_analysis 放入 ai_analysis 列
                        base['ai_analysis'] = json.dumps(ai, ensure_ascii=False)

                rows.append(base)

    df = pd.DataFrame(rows)
    # 如果前端通过 POST 提供了 keywords/platform 信息，则尝试读取
    platform = GLOBAL_CRAWL_INFO.get('platform', 'unknown')
    keywords = GLOBAL_CRAWL_INFO.get('keywords', [])
    if payload_rows is not None:
        # 尝试从第一条推断 platform/keywords
        try:
            first = source_data[0] if len(source_data) > 0 else None
            if first and first.get('platform'):
                platform = first.get('platform')
        except Exception:
            pass
    platform_name = {'xhs': '小红书', 'zhihu': '知乎'}.get(platform, platform)
    keywords_str = '_'.join(keywords[:3]) if keywords else '数据'
    keywords_str = re.sub(r'[\\/:*?"<>|]', '', keywords_str)
    # 如果包含 AI 分析则在文件名中标记
    suffix = 'with_ai' if has_ai else 'spider_result'
    filename = f"{platform_name}_{keywords_str}_{suffix}.csv"

    # 如果请求需要同时包含 AI 文本，则打包为 ZIP 返回（CSV + ai_analysis.txt）
    want_with_ai = request.args.get('with_ai') in ('1', 'true', 'True')
    # 如果为 POST 并且前端传来了数据且包含 ai，则默认返回 zip
    if request.method == 'POST' and payload_rows is not None:
        want_with_ai = has_ai

    if want_with_ai and has_ai:
        # If client POSTed rows (current tableData) we will merge CSV with AI columns
        if request.method == 'POST' and payload_rows is not None:
            # Ensure keywords/is_valid/sentiment columns exist; rows were constructed above
            try:
                df_all = df
                if 'is_valid' in df_all.columns:
                    df_valid = df_all[df_all['is_valid'] == True].copy()
                else:
                    df_valid = df_all.copy()

                buffer = io.BytesIO()
                df_valid.to_csv(buffer, index=False, encoding='utf-8-sig')
                buffer.seek(0)
                merged_name = filename.rsplit('.', 1)[0] + '_merged.csv'
                return send_file(buffer, as_attachment=True, download_name=merged_name, mimetype='text/csv')
            except Exception as e:
                return jsonify({"code": 500, "msg": f"合并失败: {str(e)}"})

        # Fallback for GET: package CSV + ai_analysis.txt as zip
        csv_buf = io.BytesIO()
        df.to_csv(csv_buf, index=False, encoding='utf-8-sig')
        csv_buf.seek(0)

        analyses = []
        for item in source_data:
            a = item.get('ai_analysis')
            if a:
                analyses.append(a)

        ai_content = json.dumps(analyses, ensure_ascii=False, indent=2)
        ai_buf = io.BytesIO(ai_content.encode('utf-8'))
        ai_buf.seek(0)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode='w') as zf:
            zf.writestr(filename, csv_buf.getvalue())
            zf.writestr('ai_analysis.txt', ai_buf.getvalue())
        zip_buf.seek(0)
        zip_name = filename.rsplit('.', 1)[0] + '.zip'
        return send_file(zip_buf, as_attachment=True, download_name=zip_name, mimetype='application/zip')

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8-sig')
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/csv')

@app.route('/api/clear_data', methods=['POST'])
def clear_data():
    """清空全局数据"""
    global GLOBAL_DATA, GLOBAL_CRAWL_INFO
    GLOBAL_DATA = []
    GLOBAL_CRAWL_INFO = {"platform": "", "keywords": []}
    return jsonify({"code": 200, "msg": "数据已清空"})

@app.route('/api/analyze_batch', methods=['POST'])
def analyze_batch_sync():
    """同步批量AI分析接口，每批50条，前端直接拿到 List[Dict]"""
    global GLOBAL_DATA

    if not GLOBAL_DATA:
        return jsonify({"code": 400, "msg": "没有数据可分析"})

    data = request.json or {}
    batch_size = int(data.get('batch_size', 50))
    max_count = int(data.get('max_count', 0))
    keyword = data.get('keyword', None)

    # 强制要求前端传入非空 keyword
    if not keyword or not str(keyword).strip():
        return jsonify({"code": 400, "msg": "前端必须提供非空的 keyword 参数以便进行 AI 分析"})

    items = GLOBAL_DATA if max_count == 0 else GLOBAL_DATA[:max_count]

    # 将前端传入的 keyword 写入每条数据，供 CSV 生成使用
    for item in items:
        item['keyword'] = keyword

    total = len(items)
    total_batches = (total + batch_size - 1) // batch_size
    all_results = []

    for bn in range(total_batches):
        start, end = bn * batch_size, min((bn + 1) * batch_size, total)
        batch = items[start:end]

        try:
            # 生成 CSV 并上传
            csv_content = ai_agent.generate_csv_content(batch)
            file_id = ai_agent.upload_csv_and_get_file_id(csv_content)
            if not file_id:
                all_results.append({
                    "batch": bn + 1,
                    "status": "error",
                    "msg": "文件上传失败"
                })
                continue
            print(f"批次 {bn + 1}/{total_batches} 文件上传成功，file_id: {file_id}")
            
            # 调用 Coze Workflow 同步获取分析结果
            batch_keyword = batch[0].get('keyword')
            raw_result = ai_agent.analyze_csv_by_coze_fileid(
                file_id=file_id,
                keyword=batch_keyword,
                epoch=bn,
                epoch_size=batch_size
            )
            print(f"批次 {bn + 1}/{total_batches} 分析完成，结果条数: {len(raw_result)}")

            # 规范化 Coze 返回的 envelope（如果存在嵌套 JSON 字符串则解析）
            def normalize_coze_result(raw):
                try:
                    if isinstance(raw, str):
                        env = json.loads(raw)
                        data_field = env.get('data')
                        if isinstance(data_field, str):
                            inner = json.loads(data_field)
                            parsed_inner = []
                            for item in inner:
                                if isinstance(item, str):
                                    try:
                                        parsed_inner.append(json.loads(item))
                                    except Exception:
                                        parsed_inner.append(item)
                                else:
                                    parsed_inner.append(item)
                            env['data'] = parsed_inner
                        return env
                    if isinstance(raw, list):
                        out = []
                        for r in raw:
                            out.append(normalize_coze_result(r) if isinstance(r, (str, dict, list)) else r)
                        return out
                    return raw
                except Exception:
                    return {'raw_result': raw}

            final_result = normalize_coze_result(raw_result)

            all_results.append({
                "batch": bn + 1,
                "total_batches": total_batches,
                "status": "batch_complete",
                "result": final_result
            })

        except Exception as e:
            all_results.append({
                "batch": bn + 1,
                "status": "error",
                "msg": str(e)
            })
            
    print(f"所有批次分析完成, 共 {total_batches} 批")
    print(all_results)
    return jsonify({
        "code": 200,
        "msg": f"完成 {total} 条数据分析，共 {total_batches} 批",
        "total_batches": total_batches,
        "results": all_results
    })

@app.route('/api/upload_analysis_txt', methods=['POST'])
def upload_analysis_txt():
    """上传AI分析结果TXT文件"""
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    file = request.files['file']
    try:
        content = file.read().decode('utf-8')
        data_list = json.loads(content)
        valid_data = [item if isinstance(item, dict) else json.loads(item) for item in data_list if (item if isinstance(item, dict) else json.loads(item)).get('is_valid', False)]
        
        keyword_count = {}
        sentiment_count = {'positive': 0, 'negative': 0, 'neutral': 0}
        for item in valid_data:
            for kw in item.get('keywords', []):
                keyword_count[kw] = keyword_count.get(kw, 0) + 1
            sentiment = item.get('sentiment', 'neutral')
            if sentiment in sentiment_count:
                sentiment_count[sentiment] += 1
        
        wordcloud_data = [{"name": k, "value": v} for k, v in sorted(keyword_count.items(), key=lambda x: -x[1])[:100]]
        sentiment_data = [{"name": "正面", "value": sentiment_count['positive']}, {"name": "负面", "value": sentiment_count['negative']}, {"name": "中性", "value": sentiment_count['neutral']}]
        
        return jsonify({"code": 200, "msg": f"解析成功，有效 {len(valid_data)} 条", "data": {"wordcloud": wordcloud_data, "sentiment": sentiment_data, "valid_data": valid_data}})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"处理失败: {str(e)}"})

@app.route('/api/merge_csv_with_analysis', methods=['POST'])
def merge_csv_with_analysis():
    """合并CSV和TXT分析结果"""
    if 'csv_file' not in request.files or 'txt_file' not in request.files:
        return jsonify({"code": 400, "msg": "需要同时上传CSV和TXT文件"})
    
    try:
        csv_file, txt_file = request.files['csv_file'], request.files['txt_file']
        df = pd.read_csv(csv_file)
        analysis_list = json.loads(txt_file.read().decode('utf-8'))
        
        parsed = [item if isinstance(item, dict) else json.loads(item) for item in analysis_list]
        if len(df) != len(parsed):
            return jsonify({"code": 400, "msg": f"数据长度不匹配: CSV {len(df)} 行, TXT {len(parsed)} 条"})
        
        df['is_valid'] = [item.get('is_valid', False) for item in parsed]
        df['keywords'] = [','.join(item.get('keywords', [])) for item in parsed]
        df['sentiment'] = [item.get('sentiment', 'neutral') for item in parsed]
        df_valid = df[df['is_valid'] == True].copy()
        
        buffer = io.BytesIO()
        df_valid.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='merged_result.csv', mimetype='text/csv')
    except Exception as e:
        return jsonify({"code": 500, "msg": f"合并失败: {str(e)}"})

@app.route('/api/generate_wordcloud_from_ai', methods=['POST'])
def generate_wordcloud_from_ai():
    """根据已有 AI 分析结果生成词云和情感统计。
    接受可选 JSON body: { "analysis": [ ... ] }
    如果不提供，则使用 GLOBAL_DATA 中的 ai_analysis 字段。
    返回格式与其他分析接口一致。
    """
    try:
        payload = request.json or {}
        # 支持两种 POST 形式：{ analyses: [...] } 或 { rows: [...] }
        analysis_list = None
        if payload.get('analysis') is not None:
            analysis_list = payload.get('analysis')
        elif payload.get('analyses') is not None:
            analysis_list = payload.get('analyses')
        elif payload.get('rows') is not None:
            # 从 rows 中提取 ai_analysis
            analysis_list = [r.get('ai_analysis') for r in payload.get('rows') if r.get('ai_analysis')]

        if analysis_list is None:
            # 从 GLOBAL_DATA 提取 ai_analysis
            analysis_list = [item.get('ai_analysis') for item in GLOBAL_DATA if item.get('ai_analysis')]

        # 标准化每项为 dict
        parsed = []
        for a in analysis_list:
            if a is None:
                continue
            if isinstance(a, str):
                try:
                    parsed.append(json.loads(a))
                except Exception:
                    continue
            elif isinstance(a, dict):
                parsed.append(a)

        # 统计关键词与情感
        keyword_count = {}
        sentiment_count = {'positive': 0, 'negative': 0, 'neutral': 0}
        for item in parsed:
            if not item.get('is_valid', True):
                continue
            kws = item.get('keywords') or item.get('keyword') or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(',') if k.strip()]
            for kw in kws:
                keyword_count[kw] = keyword_count.get(kw, 0) + 1
            s = (item.get('sentiment') or 'neutral').lower()
            if s in sentiment_count:
                sentiment_count[s] += 1

        wordcloud_data = [{"name": k, "value": v} for k, v in sorted(keyword_count.items(), key=lambda x: -x[1])[:100]]
        sentiment_data = [{"name": "正面", "value": sentiment_count['positive']}, {"name": "负面", "value": sentiment_count['negative']}, {"name": "中性", "value": sentiment_count['neutral']}]

        return jsonify({"code": 200, "msg": f"生成成功，共 {len(parsed)} 条分析数据", "data": {"wordcloud": wordcloud_data, "sentiment": sentiment_data}})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"生成失败: {str(e)}"})

@app.route('/api/download_ai_analysis', methods=['GET', 'POST'])
def download_ai_analysis():
    """下载全局或传入的 AI 分析结果为 TXT（JSON 数组）。
    可选 query 参数 `as` to name file.
    """
    try:
        analyses = None
        # 支持 POST body: { analyses: [...] }
        if request.method == 'POST' and request.is_json:
            body = request.get_json(silent=True) or {}
            analyses = body.get('analyses')

        if analyses is None:
            analyses = [item.get('ai_analysis') for item in GLOBAL_DATA if item.get('ai_analysis')]

        if not analyses:
            return jsonify({"code": 400, "msg": "没有可下载的 AI 分析结果"})

        content = json.dumps(analyses, ensure_ascii=False, indent=2)
        buffer = io.BytesIO(content.encode('utf-8'))
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='ai_analysis.txt', mimetype='text/plain')
    except Exception as e:
        return jsonify({"code": 500, "msg": f"下载失败: {str(e)}"})

@app.route('/api/analyze_merged_csv', methods=['POST'])
def analyze_merged_csv():
    """分析已合并的CSV文件"""
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    try:
        df = pd.read_csv(request.files['file'])
        if 'keywords' not in df.columns or 'sentiment' not in df.columns:
            return jsonify({"code": 400, "msg": "CSV必须包含 keywords 和 sentiment 列"})
        
        keyword_count = {}
        for kw_str in df['keywords'].dropna():
            for kw in str(kw_str).split(','):
                kw = kw.strip()
                if kw:
                    keyword_count[kw] = keyword_count.get(kw, 0) + 1
        
        sentiment_count = df['sentiment'].value_counts().to_dict()
        wordcloud_data = [{"name": k, "value": v} for k, v in sorted(keyword_count.items(), key=lambda x: -x[1])[:100]]
        sentiment_data = [{"name": "正面", "value": sentiment_count.get('positive', 0)}, {"name": "负面", "value": sentiment_count.get('negative', 0)}, {"name": "中性", "value": sentiment_count.get('neutral', 0)}]
        
        return jsonify({"code": 200, "msg": f"分析成功，共 {len(df)} 条", "data": {"wordcloud": wordcloud_data, "sentiment": sentiment_data}})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"分析失败: {str(e)}"})

def read_csv_with_encoding(content):
    for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except:
            continue
    return None

@app.route('/api/merge_multiple_csv', methods=['POST'])
def merge_multiple_csv():
    """合并多个CSV文件"""
    files = request.files.getlist('files')
    if len(files) < 2:
        return jsonify({"code": 400, "msg": "请至少上传2个CSV文件"})
    
    try:
        all_dfs = []
        for f in files:
            df = read_csv_with_encoding(f.read())
            if df is None:
                return jsonify({"code": 400, "msg": f"文件 {f.filename} 编码无法识别"})
            df['source_file'] = f.filename
            all_dfs.append(df)
        
        merged = pd.concat(all_dfs, ignore_index=True)
        buffer = io.BytesIO()
        merged.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='merged_all.csv', mimetype='text/csv')
    except Exception as e:
        return jsonify({"code": 500, "msg": f"合并失败: {str(e)}"})

@app.route('/api/analyze_multiple_csv', methods=['POST'])
def analyze_multiple_csv():
    """分析多个CSV文件"""
    files = request.files.getlist('files')
    if not files:
        return jsonify({"code": 400, "msg": "未上传文件"})
    
    try:
        all_dfs = []
        for f in files:
            df = read_csv_with_encoding(f.read())
            if df is None:
                return jsonify({"code": 400, "msg": f"文件 {f.filename} 无法解析"})
            all_dfs.append(df)
        
        merged = pd.concat(all_dfs, ignore_index=True)
        has_analysis = 'keywords' in merged.columns and 'sentiment' in merged.columns
        
        keyword_count, sentiment_count = {}, {'positive': 0, 'negative': 0, 'neutral': 0}
        if has_analysis:
            for kw_str in merged['keywords'].dropna():
                for kw in str(kw_str).split(','):
                    kw = kw.strip()
                    if kw:
                        keyword_count[kw] = keyword_count.get(kw, 0) + 1
            for s in merged['sentiment'].dropna():
                s = str(s).lower().strip()
                if s in sentiment_count:
                    sentiment_count[s] += 1
        
        wordcloud_data = [{"name": k, "value": v} for k, v in sorted(keyword_count.items(), key=lambda x: -x[1])[:100]]
        sentiment_data = [{"name": "正面", "value": sentiment_count['positive']}, {"name": "负面", "value": sentiment_count['negative']}, {"name": "中性", "value": sentiment_count['neutral']}]
        
        return jsonify({"code": 200, "msg": f"分析成功，共 {len(merged)} 条", "data": {"wordcloud": wordcloud_data, "sentiment": sentiment_data}})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"分析失败: {str(e)}"})

# ==================== 应用启动 ====================
if __name__ == '__main__':
    with app.app_context():
        # 创建数据库表
        db.create_all()
        print("\n" + "=" * 50)
        print("[INFO] 数据库表初始化完成")
        print("[INFO] 登录页地址: http://localhost:5000/login")
        print("[INFO] Swagger 文档: http://localhost:5000/api/docs")
        print("=" * 50 + "\n")
    
    app.run(debug=True, port=5000, use_reloader=False)