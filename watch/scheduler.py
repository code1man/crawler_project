# watch/scheduler.py
import time
from apscheduler.schedulers.background import BackgroundScheduler
from watch.store import list_watches, now_ts


_scheduler = None

def start_scheduler(app=None, runner=None, scan_seconds: int = 60) -> None:
    """
    runner: 可注入 run_watch_once（用于单测/演示），不传则默认从 watch.task 导入
    scan_seconds: 扫描频率（单测可设1秒）
    """
    global _scheduler
    if _scheduler:
        return

    scheduler = BackgroundScheduler(daemon=True)

    def tick():
        nonlocal runner
        if runner is None:
            from watch.task import run_watch_once  # 真实运行才需要 task/爬虫依赖
            runner = run_watch_once

        now = int(time.time())
        for w in list_watches():
            if not w.get("enabled", True):
                continue
            last_run = int(w.get("last_run", 0))
            interval = int(w.get("interval_seconds", 3600))

            if now - last_run >= interval:
                try:
                    summary = runner(w)   # ✅ 用注入的 runner
                    w["last_run"] = now_ts()
                    w["updated_at"] = now_ts()
                    print(f"[WATCH] ran {w['keyword']} -> {summary}")
                except Exception as e:
                    print(f"[WATCH][ERROR] {w.get('keyword')} failed: {e}")

    scheduler.add_job(tick, "interval", seconds=scan_seconds, id="watch_tick", replace_existing=True)
    scheduler.start()
    _scheduler = scheduler
    print("[WATCH] scheduler started")