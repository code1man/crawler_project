"""
AI 结果后处理：规则聚类、优先级计算与热力图数据生成

提供函数:
- `process_ai_results(items)` : 主函数，输入 AI 返回的 items 列表（dict），返回聚类、排行榜和热力图数据。

示例用法见模块末尾的 `__main__`。
"""
from collections import defaultdict, Counter
from typing import List, Dict, Any


ALLOWED_TOPICS = [
    "usability",
    "performance",
    "reliability",
    "service",
    "content",
    "price_value",
    "policy_process",
    "other",
]


ALLOWED_ISSUE_TYPES = [
    "problem",
    "suggestion",
    "praise",
    "other",
]


ALLOWED_SEVERITIES = ["low", "medium", "high"]


ALLOWED_SENTIMENTS = ["positive", "neutral", "negative"]


SEVERITY_WEIGHT = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

SENTIMENT_WEIGHT = {
    "positive": 0.5,
    "neutral": 1.0,
    "negative": 1.5,
}


KEYWORD_RULES = [
    ("performance", ["慢", "卡", "性能", "速度", "崩溃", "lag"]),
    ("usability", ["操作", "难用", "界面", "易用", "体验", "使用"]),
    ("service", ["客服", "售后", "响应", "服务", "支持"]),
    ("content", ["内容", "信息", "答案", "错误信息", "质量"]),
    ("price_value", ["价格", "贵", "性价比", "收费"]),
    ("policy_process", ["规则", "流程", "制度", "审核", "合规"]),
    ("reliability", ["不信任", "担心", "不稳定", "不准确", "可靠性", "准确性"]),
]


def map_topic_from_fields(item: Dict[str, Any]) -> str:
    """基于已有的 `issue_topic`、`issue_type`、`keywords` 进行规则映射，返回 ALLOWED_TOPICS 中的值。"""
    # 1) 如果 AI 已经给出且合法，直接采用
    t = item.get("issue_topic")
    if isinstance(t, str) and t.strip():
        t_low = t.strip().lower()
        if t_low in ALLOWED_TOPICS:
            return t_low

    # 2) 从 keywords 或 issue_type 中匹配规则
    keywords = item.get("keywords") or []
    if isinstance(keywords, str):
        # 处理逗号分隔的字符串
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    # 合并所有文本到一个小写字符串
    texts = []
    for k in keywords:
        if k:
            texts.append(str(k))
    itype = item.get("issue_type")
    if itype:
        texts.append(str(itype))
    content = "|".join(texts).lower()

    for topic, kw_list in KEYWORD_RULES:
        for kw in kw_list:
            if kw.lower() in content:
                return topic

    # 3) 处理 sentiment 作为弱提示：负面情绪且包含担心/不信任字样 -> reliability
    sentiment = (item.get("sentiment") or "").lower()
    if sentiment == "negative" and ("担心" in content or "不信任" in content):
        return "reliability"

    return "other"


def normalize_issue_type(val: Any) -> str:
    if not val:
        return None
    s = str(val).strip().lower()
    # Accept common synonyms
    if s in ("problem", "issue", "bug", "complaint", "抱怨"):
        return "problem"
    if s in ("suggestion", "suggest", "建议"):
        return "suggestion"
    if s in ("praise", "赞", "好评", "推荐"):
        return "praise"
    if s in ALLOWED_ISSUE_TYPES:
        return s
    return "other"


def normalize_severity(val: Any) -> str:
    if not val:
        return None
    s = str(val).strip().lower()
    # numeric mapping
    try:
        num = float(s)
        if num <= 1:
            return "low"
        if num <= 2:
            return "medium"
        return "high"
    except Exception:
        pass
    if s in ("low", "轻微", "minor"):
        return "low"
    if s in ("medium", "中等", "moderate"):
        return "medium"
    if s in ("high", "严重", "major"):
        return "high"
    return None


def normalize_sentiment(val: Any) -> str:
    if not val:
        return None
    s = str(val).strip().lower()
    if s in ("positive", "pos", "正面", "good", "好"):
        return "positive"
    if s in ("negative", "neg", "负面", "bad", "差"):
        return "negative"
    if s in ("neutral", "中性", "none"):
        return "neutral"
    # fallback: try to infer from words
    if any(w in s for w in ("不", "没", "差", "失望", "担心", "不信任", "失误", "错误")):
        return "negative"
    if any(w in s for w in ("好", "满意", "喜欢", "推荐")):
        return "positive"
    return "neutral"


def normalize_keywords(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        # split by common separators
        parts = [p.strip() for p in re.split(r"[,;，；|\\n\\t]+", val) if p.strip()]
        return parts
    return [str(val)]

import re



def severity_to_weight(sev: Any) -> int:
    if not sev:
        return SEVERITY_WEIGHT.get("medium")
    s = str(sev).strip().lower()
    return SEVERITY_WEIGHT.get(s, SEVERITY_WEIGHT.get("medium"))


def sentiment_to_weight(sent: Any) -> float:
    if not sent:
        return SENTIMENT_WEIGHT.get("neutral")
    s = str(sent).strip().lower()
    return SENTIMENT_WEIGHT.get(s, SENTIMENT_WEIGHT.get("neutral"))


def process_ai_results(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """主处理函数。

    入参: AI 返回的 items 列表，每项为 dict（包含至少 `is_valid`, `sentiment`, `severity`, `keywords`）
    返回: 包含 augmented items, topic 聚合统计, 排行榜及热力图数据的 dict
    """
    # 规范化每条记录，确保枚举值
    normalized_items = []
    for it in items:
        is_valid = bool(it.get("is_valid"))
        if not is_valid:
            normalized_items.append({
                "is_valid": False,
                "sentiment": "neutral",
                "issue_type": None,
                "severity": None,
                "issue_topic": None,
                "keywords": [],
            })
            continue
        sent = normalize_sentiment(it.get("sentiment")) or "neutral"
        itype = normalize_issue_type(it.get("issue_type"))
        sev = normalize_severity(it.get("severity"))
        topic = None
        # prefer provided valid topic
        raw_topic = it.get("issue_topic")
        if isinstance(raw_topic, str) and raw_topic.strip().lower() in ALLOWED_TOPICS:
            topic = raw_topic.strip().lower()
        else:
            topic = map_topic_from_fields(it)
        kws = normalize_keywords(it.get("keywords"))
        normalized_items.append({
            "is_valid": True,
            "sentiment": sent,
            "issue_type": itype,
            "severity": sev,
            "issue_topic": topic,
            "keywords": kws,
        })

    # 过滤有效项用于后续指标计算
    valid_items = [it for it in normalized_items if it.get("is_valid")]

    # 为每条记录映射 topic / 权重 / per-item priority
    augmented = []
    # Ensure we align each normalized item with its original input by index.
    for idx, norm in enumerate(normalized_items):
        if not norm.get("is_valid"):
            continue
        # original raw item (may be shorter/longer than normalized list)
        try:
            it_raw = items[idx]
        except Exception:
            it_raw = {}
        assigned = map_topic_from_fields(it_raw) if (norm.get("issue_topic") == "other") else norm.get("issue_topic")
        if not assigned:
            assigned = "other"
        sev_w = severity_to_weight(norm.get("severity"))
        sent_w = sentiment_to_weight(norm.get("sentiment"))
        per_priority = sev_w * sent_w  # 单条影响度 * 情绪强度
        aug = dict(it_raw) if isinstance(it_raw, dict) else {"raw": it_raw}
        aug.update({
            "assigned_topic": assigned,
            "severity_weight": sev_w,
            "sentiment_weight": sent_w,
            "per_item_priority": per_priority,
        })
        augmented.append(aug)

    # 统计频次与聚合指标
    topic_buckets = defaultdict(list)
    for a in augmented:
        topic_buckets[a["assigned_topic"]].append(a)

    topic_stats = {}
    for topic in ALLOWED_TOPICS:
        bucket = topic_buckets.get(topic, [])
        count = len(bucket)
        if count == 0:
            topic_stats[topic] = {
                "count": 0,
                "avg_severity_weight": 0,
                "avg_sentiment_weight": 0,
                "priority_score": 0,
            }
            continue
        avg_sev = sum(b["severity_weight"] for b in bucket) / count
        avg_sent = sum(b["sentiment_weight"] for b in bucket) / count
        # 按你的公式: 优先级 = 影响程度(avg) * 发生频次(count) * 用户情绪强度(avg)
        priority_score = avg_sev * count * avg_sent
        topic_stats[topic] = {
            "count": count,
            "avg_severity_weight": round(avg_sev, 3),
            "avg_sentiment_weight": round(avg_sent, 3),
            "priority_score": round(priority_score, 3),
        }

    # 排行榜: 按 priority_score 降序
    ranked = sorted(
        [
            {"topic": t, **s}
            for t, s in topic_stats.items()
            if s["count"] > 0
        ],
        key=lambda x: x["priority_score"],
        reverse=True,
    )

    # 热力图：topic vs severity counts
    severities = ["low", "medium", "high"]
    heatmap = []
    for topic in ALLOWED_TOPICS:
        bucket = topic_buckets.get(topic, [])
        cnts = Counter([str(b.get("severity_weight")) for b in bucket])
        # 转换为 severity 名称计数
        row = {"topic": topic}
        for sev_name in severities:
            w = SEVERITY_WEIGHT[sev_name]
            row[sev_name] = cnts.get(str(w), 0)
        row["total"] = len(bucket)
        heatmap.append(row)

    return {
        "augmented_items": augmented,
        "normalized_items": normalized_items,
        "topic_stats": topic_stats,
        "ranked_topics": ranked,
        "heatmap": heatmap,
    }


if __name__ == "__main__":
    # 简单示例：使用用户提供的样例数据
    sample = [
        {
            "is_valid": True,
            "sentiment": "negative",
            "issue_type": "problem",
            "severity": "high",
            "issue_topic": "reliability",
            "keywords": ["不信任", "担心", "不稳定"],
        },
        {
            "is_valid": False,
            "sentiment": "neutral",
            "issue_type": None,
            "severity": None,
            "issue_topic": None,
            "keywords": [],
        },
    ]

    out = process_ai_results(sample)
    import json

    print(json.dumps(out, ensure_ascii=False, indent=2))
