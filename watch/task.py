# watch/task.py
from typing import Dict, Any, List, Tuple
from utils.cleaner import clean_comments
from watch.ai_parse import normalize_ai_output

def notify_user(watch, subject, content, sms_params=None):
    """
    默认通知实现（无短信，仅打印）
    单元测试 / 未配置通知模块时使用
    """
    print("\n===== [NOTIFY - DEFAULT] =====")
    print("subject:", subject)
    print("content:\n", content)
    print("sms_params:", sms_params)
    print("===== [END] =====\n")



def _count_sentiment(items: List[Dict[str, Any]]) -> Tuple[int, int, int, int]:
    """
    returns: total, valid_count, pos, neg
    """
    total = len(items)
    valid = [x for x in items if x.get("is_valid")]
    pos = sum(1 for x in valid if x.get("sentiment") == "positive")
    neg = sum(1 for x in valid if x.get("sentiment") == "negative")
    return total, len(valid), pos, neg

def _format_email_content(watch: Dict[str, Any], total: int, valid: int, pos: int, neg: int, reasons: List[str]) -> str:
    return (
        f"【舆情监控告警】\n\n"
        f"关键词：{watch['keyword']}\n"
        f"平台：{watch['platform']}\n"
        f"本次抓取：{watch.get('max_count', 50)}（上限）\n\n"
        f"AI统计（有效数据 is_valid=true）：\n"
        f"- 总分析条数：{total}\n"
        f"- 有效条数：{valid}\n"
        f"- 正面：{pos}\n"
        f"- 负面：{neg}\n\n"
        f"触发原因：\n- " + "\n- ".join(reasons) + "\n"
    )

def run_watch_once(watch: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行一次订阅任务；返回运行摘要（用于 /api/watch/<id>/test 或日志）
    """
    keyword = watch["keyword"]
    platform = watch["platform"]
    max_count = int(watch.get("max_count", 50))

    # 1) 爬取（✅ 延迟导入，避免 import watch.task 时就拉起爬虫依赖）
    if platform == "xhs":
        crawler = globals().get("search_and_crawl_xhs")
        if crawler is None:
            from spiders.xhs_spider import search_and_crawl_xhs as crawler
        raw = crawler(keyword, max_count=max_count)

    elif platform == "zhihu":
        crawler = globals().get("search_and_crawl_zhihu")
        if crawler is None:
            from spiders.zhihu_spider import search_and_crawl_zhihu as crawler
        raw = crawler(keyword, max_count=max_count)

    else:
        return {"ok": False, "msg": f"未知平台: {platform}"}



    # 2) 清洗（你们 cleaner 已经做了去重、过滤等）:contentReference[oaicite:12]{index=12}
    cleaned = clean_comments(raw)
    if not cleaned:
        return {"ok": True, "msg": "本次无可用数据", "triggered": False}

    # 3) AI 批量分析（返回每批一个 result）:contentReference[oaicite:13]{index=13}
    ai_runner = globals().get("batch_analyze_csv_by_coze")
    if ai_runner is None:
        from utils.ai_agent import batch_analyze_csv_by_coze as ai_runner

    batch_results = ai_runner(cleaned, batch_size=50, delay=2.0)



    # 4) 解析成标准列表 is_valid/keywords/sentiment
    ai_items = normalize_ai_output(batch_results)

    total, valid, pos, neg = _count_sentiment(ai_items)

    # 5) 阈值判断
    reasons = []
    pos_th = watch.get("positive_threshold")
    neg_th = watch.get("negative_threshold")

    if isinstance(neg_th, int) and neg >= neg_th:
        reasons.append(f"负面条数 {neg} ≥ 阈值 {neg_th}")
    if isinstance(pos_th, int) and pos >= pos_th:
        reasons.append(f"正面条数 {pos} ≥ 阈值 {pos_th}")

    triggered = len(reasons) > 0

    # 6) 通知（邮件 + 短信）
    if triggered:
        subject = f"舆情告警：{keyword}（{platform}）"
        content = _format_email_content(watch, total, valid, pos, neg, reasons)
        sms_params = {
            "keyword": keyword,
            "platform": platform,
            "pos": pos,
            "neg": neg,
            "valid": valid
        }
        notify_user(watch.get("notify", {}), subject, content, sms_params)

    return {
        "ok": True,
        "triggered": triggered,
        "keyword": keyword,
        "platform": platform,
        "total": total,
        "valid": valid,
        "positive": pos,
        "negative": neg,
        "reasons": reasons
    }
