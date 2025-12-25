import os
import sys
import json
import tempfile
import io
import csv
import datetime
from pathlib import Path
from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth, WorkflowEventType
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 后处理导入
try:
    from utils.ai_postprocess import process_ai_results
except Exception:
    # 兼容作为脚本运行的相对导入
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    from utils.ai_postprocess import process_ai_results

# 配置信息 — 尝试相对导入，若作为脚本直接运行则回退到项目根路径
try:
    from config import Config
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    from config import Config

COZE_API_TOKEN = Config.COZE_API_TOKEN
WORKFLOW_ID = Config.WORKFLOW_ID
COZE_TIMEOUT_SECONDS = getattr(Config, 'COZE_TIMEOUT_SECONDS', 300)

coze = Coze(auth=TokenAuth(token=COZE_API_TOKEN), base_url=COZE_CN_BASE_URL)

def generate_csv_content(data_list):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['keyword', 'url', 'user', 'comment_content'])
    for item in data_list:
        keyword = item.get('title', '')
        url = item.get('url', '')
        user = item.get('author', '匿名')
        comments = item.get('comments', [])
        comment_content = comments[0] if comments else item.get('content', '')
        writer.writerow([keyword, url, user, comment_content])
    return output.getvalue()


def upload_csv_and_get_file_id(csv_content):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8") as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        print(f"[ai_agent] uploading tmp csv: {tmp_path}", flush=True)
        with open(tmp_path, "rb") as f:
            resp = coze.files.upload(file=f)
        print(f"[ai_agent] upload response: {type(resp)} {getattr(resp, 'file_id', getattr(resp, 'id', getattr(resp, 'data', None)))}", flush=True)

        if hasattr(resp, "file_id"):
            return resp.file_id
        if hasattr(resp, "data") and "file_id" in resp.data:
            return resp.data["file_id"]
        if hasattr(resp, "id"):
            return resp.id
        if isinstance(resp, dict):
            if "file_id" in resp:
                return resp["file_id"]
            if "id" in resp:
                return resp["id"]
        raise RuntimeError(f"未知上传返回结构: {resp}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def analyze_csv_by_coze_fileid(file_id, keyword="", epoch=0, epoch_size=50):
    """
    使用 Coze workflow stream 接口
    自动等待 workflow 完成
    自动收敛最终 batch 结果
    返回 Python List / Dict（不返回 SDK 对象）
    """
    if not keyword or not str(keyword).strip():
        raise ValueError("Missing required parameter: keyword")

    parameters = {
        "input": json.dumps({"file_id": file_id}),
        "epoch": epoch,
        "epoch_size": epoch_size,
        "keyword": keyword
    }

    final_payload = None   # 真正的最终结果
    last_message_raw = None

    stream = coze.workflows.runs.stream(
        workflow_id=WORKFLOW_ID,
        parameters=parameters
    )
    print(f"[ai_agent] starting workflow stream: workflow_id={WORKFLOW_ID}, params={parameters}", flush=True)

    for event in stream:
        # 只关心 MESSAGE / ERROR
        if event.event == WorkflowEventType.MESSAGE:
            msg = event.message

            # message 通常是 WorkflowEventMessage
            # 真正的结果一般在 End 节点
            if hasattr(msg, "node_is_finish") and msg.node_is_finish:
                last_message_raw = msg.content

        elif event.event == WorkflowEventType.ERROR:
            raise RuntimeError(f"Coze workflow error: {event.error}")

        elif event.event == WorkflowEventType.INTERRUPT:
            interrupt_data = event.interrupt.interrupt_data
            stream = coze.workflows.runs.resume(
                workflow_id=WORKFLOW_ID,
                event_id=interrupt_data.event_id,
                resume_data="continue",
                interrupt_type=interrupt_data.type,
            )

    # stream 结束，开始收敛结果
    if last_message_raw is None:
        return []

    # 尝试解析 result，支持直接 JSON 或 wrapper 包裹
    result_list = []
    try:
        parsed = json.loads(last_message_raw)
        # 如果直接是列表
        if isinstance(parsed, list):
            result_list = parsed
        elif isinstance(parsed, dict):
            # 常见 wrapper: {"data": "[...]"}
            if "data" in parsed and isinstance(parsed["data"], str):
                try:
                    inner = json.loads(parsed["data"])
                    if isinstance(inner, list):
                        result_list = inner
                    else:
                        result_list = [inner]
                except Exception:
                    result_list = [parsed]
            elif "items" in parsed and isinstance(parsed["items"], list):
                result_list = parsed["items"]
            else:
                result_list = [parsed]
        else:
            result_list = []
    except Exception:
        # 有些 workflow 会再包一层
        try:
            wrapper = json.loads(last_message_raw)
            if isinstance(wrapper, dict) and "data" in wrapper:
                return json.loads(wrapper["data"])
        except Exception:
            pass

    # 最坏兜底
    return result_list