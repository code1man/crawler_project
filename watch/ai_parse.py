# watch/ai_parse.py
import json
from typing import Any, Dict, List

def _ensure_item(obj: Any) -> Dict[str, Any]:
    # 统一为 dict
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except:
            return {"is_valid": False, "keywords": [], "sentiment": "neutral"}
    return {"is_valid": False, "keywords": [], "sentiment": "neutral"}

def normalize_ai_output(batch_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    输入：batch_analyze_csv_by_coze 的返回（每批一个 dict: {batch_num, ..., result: xxx}）
    输出：展开后的 [{is_valid, keywords, sentiment}, ...]
    兼容你们 TXT 分析模块期望的字段。:contentReference[oaicite:6]{index=6}
    """
    all_items: List[Dict[str, Any]] = []

    for b in batch_results:
        raw = b.get("result")
        # Coze 返回可能是 list / dict / str
        if isinstance(raw, list):
            for x in raw:
                all_items.append(_ensure_item(x))
        elif isinstance(raw, dict):
            # 有些 workflow 会返回 {"data":[...]} 或 {"output":[...]} 之类
            if "data" in raw and isinstance(raw["data"], list):
                for x in raw["data"]:
                    all_items.append(_ensure_item(x))
            else:
                all_items.append(_ensure_item(raw))
        elif isinstance(raw, str):
            # 可能是 JSON 数组字符串
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    for x in parsed:
                        all_items.append(_ensure_item(x))
                else:
                    all_items.append(_ensure_item(parsed))
            except:
                # 实在解析不了就给一个占位
                all_items.append({"is_valid": False, "keywords": [], "sentiment": "neutral"})
        else:
            all_items.append({"is_valid": False, "keywords": [], "sentiment": "neutral"})

    # 兜底字段规范化
    normalized: List[Dict[str, Any]] = []
    for it in all_items:
        it = _ensure_item(it)
        normalized.append({
            "is_valid": bool(it.get("is_valid", False)),
            "keywords": it.get("keywords", []) if isinstance(it.get("keywords", []), list) else [],
            "sentiment": it.get("sentiment", "neutral") or "neutral",
        })
    return normalized
