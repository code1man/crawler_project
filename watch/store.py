# watch/store.py
import time
import uuid
from typing import Any, Dict, List, Optional

# 课程项目建议先用内存；需要持久化再换 SQLite/Redis
WATCH_LIST: List[Dict[str, Any]] = []

def now_ts() -> int:
    return int(time.time())

def create_watch(data: Dict[str, Any], user_id: str = "demo_user") -> Dict[str, Any]:
    watch = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,

        "keyword": data["keyword"].strip(),
        "platform": data.get("platform", "xhs").strip(),   # xhs / zhihu
        "max_count": int(data.get("max_count", 50)),       # 每次爬取最多多少条

        "interval_seconds": int(data.get("interval_minutes", 60)) * 60,
        "positive_threshold": data.get("positive_threshold"),  # int or None
        "negative_threshold": data.get("negative_threshold"),  # int or None

        # notify: {"email": "...", "phone": "..."}
        "notify": data.get("notify", {}),

        "enabled": bool(data.get("enabled", True)),
        "last_run": 0,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    WATCH_LIST.append(watch)
    return watch

def list_watches(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if user_id is None:
        return WATCH_LIST
    return [w for w in WATCH_LIST if w["user_id"] == user_id]

def get_watch(watch_id: str) -> Optional[Dict[str, Any]]:
    for w in WATCH_LIST:
        if w["id"] == watch_id:
            return w
    return None

def delete_watch(watch_id: str) -> bool:
    global WATCH_LIST
    before = len(WATCH_LIST)
    WATCH_LIST = [w for w in WATCH_LIST if w["id"] != watch_id]
    return len(WATCH_LIST) < before

def set_enabled(watch_id: str, enabled: bool) -> bool:
    w = get_watch(watch_id)
    if not w:
        return False
    w["enabled"] = enabled
    w["updated_at"] = now_ts()
    return True
