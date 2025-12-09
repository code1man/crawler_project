from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth, WorkflowEventType
import time
import io
import csv
import json

# 配置信息
COZE_API_TOKEN = 'cztei_lVpTPQ2jzXnqPuhRG7x9tjDLDdZGtAHWvs8QN5l2lGRQHiV9NYZKO1LFFhMPbT4Mh'
WORKFLOW_ID = '7581414272291733544'

# 每批发送的数据条数
BATCH_SIZE = 50

coze = Coze(auth=TokenAuth(token=COZE_API_TOKEN), base_url=COZE_CN_BASE_URL)


def generate_csv_content(data_list):
    """
    将数据列表转换为CSV文件内容字符串
    :param data_list: 数据列表
    :return: CSV格式的字符串
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['keyword', 'url', 'user', 'comment_content'])
    
    # 写入数据
    for item in data_list:
        keyword = item.get('title', '')
        url = item.get('url', '')
        user = item.get('author', '匿名')
        # 评论内容：优先使用comments列表的第一项，否则使用content
        comments = item.get('comments', [])
        comment_content = comments[0] if comments else item.get('content', '')
        
        writer.writerow([keyword, url, user, comment_content])
    
    return output.getvalue()


def analyze_csv_by_coze(csv_content):
    """
    调用 Coze Workflow 分析CSV文件内容
    :param csv_content: CSV格式的字符串
    :return: AI分析结果
    """
    if not csv_content:
        return "无内容"
        
    try:
        parameters = {
            "input_text": csv_content 
        }
        
        result = coze.workflows.runs.create(
            workflow_id=WORKFLOW_ID,
            parameters=parameters
        )
        
        return result.data
        
    except Exception as e:
        print(f"AI Error: {e}")
        return f"AI分析失败: {str(e)}"


def analyze_sentiment_by_coze(text):
    """
    调用 Coze Workflow 进行情感分析（单条文本）
    保留此函数以兼容旧代码
    """
    if not text:
        return "无内容"
        
    try:
        parameters = {
            "input_text": text 
        }
        
        result = coze.workflows.runs.create(
            workflow_id=WORKFLOW_ID,
            parameters=parameters
        )
        
        return result.data
        
    except Exception as e:
        print(f"AI Error: {e}")
        return "AI分析失败"


def batch_analyze_csv_by_coze(data_list, batch_size=50, delay=2.0, callback=None):
    """
    批量调用 Coze Workflow 进行分析 - 每50条生成一个CSV文件发送
    
    :param data_list: 数据列表
    :param batch_size: 每批处理的数量（默认50条）
    :param delay: 每批之间的延时（秒），避免API限流
    :param callback: 进度回调函数 callback(batch_num, total_batches, batch_result)
    :return: 所有批次的分析结果列表
    """
    results = []
    total = len(data_list)
    total_batches = (total + batch_size - 1) // batch_size  # 向上取整
    
    print(f"[AI] 开始批量分析，共 {total} 条数据，分 {total_batches} 批处理（每批 {batch_size} 条）")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total)
        batch_data = data_list[start_idx:end_idx]
        
        print(f"[AI] 处理第 {batch_num + 1}/{total_batches} 批，数据范围: {start_idx + 1}-{end_idx}")
        
        # 生成CSV内容
        csv_content = generate_csv_content(batch_data)
        
        # 调用AI分析
        batch_result = analyze_csv_by_coze(csv_content)
        
        results.append({
            "batch_num": batch_num + 1,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "count": len(batch_data),
            "result": batch_result
        })
        
        # 进度回调
        if callback:
            callback(batch_num + 1, total_batches, batch_result)
        
        # 批次间延时（避免API限流）
        if batch_num + 1 < total_batches:
            print(f"[AI] 休息 {delay} 秒...")
            time.sleep(delay)
    
    print(f"[AI] 批量分析完成，共处理 {total_batches} 批")
    return results


def batch_analyze_by_coze(data_list, batch_size=5, delay=1.0, callback=None):
    """
    批量调用 Coze Workflow 进行情感分析（逐条处理，保留兼容）
    
    :param data_list: 数据列表，每项包含需要分析的数据
    :param batch_size: 每批处理的数量
    :param delay: 每批之间的延时（秒），避免API限流
    :param callback: 进度回调函数 callback(current, total, item)
    :return: 处理后的数据列表
    """
    results = []
    total = len(data_list)
    
    for i, item in enumerate(data_list):
        # 如果已经分析过，跳过
        if item.get('ai_analysis'):
            results.append(item)
            if callback:
                callback(i + 1, total, item)
            continue
        
        # 构建分析文本
        full_text = f"标题：{item.get('title', '无标题')}\n内容摘要：{item.get('content', '')}\n用户评论：{'; '.join(item.get('comments', []))}"
        
        # 调用AI分析
        ai_result = analyze_sentiment_by_coze(full_text)
        item['ai_analysis'] = ai_result
        results.append(item)
        
        # 进度回调
        if callback:
            callback(i + 1, total, item)
        
        # 批次延时（避免API限流）
        if (i + 1) % batch_size == 0 and i + 1 < total:
            time.sleep(delay)
    
    return results