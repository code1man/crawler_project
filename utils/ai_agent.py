import os
import sys
import json
import tempfile
import io
import csv
from pathlib import Path
from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth

# 配置信息 — 尝试相对导入，若作为脚本直接运行则回退到项目根路径
try:
    from config import Config
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    from config import Config

COZE_API_TOKEN = Config.COZE_API_TOKEN
WORKFLOW_ID = Config.WORKFLOW_ID

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

        with open(tmp_path, "rb") as f:
            resp = coze.files.upload(file=f)

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


def analyze_csv_by_coze_fileid(file_id, keyword="", epoch=1, epoch_size=50):
    """
    用 Coze Workflow 直接调用 runs.create 获取最终 batch 分析结果
    返回 Python 列表 List[Dict]
    """
    if not keyword or not str(keyword).strip():
        raise ValueError("Missing required parameter: keyword")

    parameters = {
        "input": json.dumps({"file_id": file_id}),
        "epoch": epoch,
        "epoch_size": epoch_size,
        "keyword": keyword
    }

    try:
        result = coze.workflows.runs.create(
            workflow_id=WORKFLOW_ID,
            parameters=parameters
        )

        # result.data 是 Coze SDK 返回的对象，确保序列化成 Python dict/list
        def _to_serializable(obj):
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, (list, tuple)):
                return [_to_serializable(x) for x in obj]
            if isinstance(obj, dict):
                return {str(k): _to_serializable(v) for k, v in obj.items()}
            if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
                try:
                    return _to_serializable(obj.to_dict())
                except Exception:
                    pass
            if hasattr(obj, '__dict__'):
                try:
                    return {k: _to_serializable(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
                except Exception:
                    pass
            try:
                return str(obj)
            except Exception:
                return repr(obj)

        return _to_serializable(result.data)

    except Exception as e:
        msg = str(e)
        if 'access token expired' in msg.lower() or 'token expired' in msg.lower():
            raise RuntimeError('COZE access token expired; please update Config.COZE_API_TOKEN') from e
        raise
