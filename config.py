"""全流程智慧课堂系统 - 全局配置"""
import os
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _load_dotenv(path: Path = BASE_DIR / ".env") -> None:
    """轻量加载 .env（仅当缺失时才写回 os.environ），无第三方依赖。
    .env 被 gitignore 排除，真实密钥只存在于本地，绝不进入仓库。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

# 运行实例 ID：每次进程启动时生成新值。
# 前端登录时将其与凭证一同保存，各端页面加载时同步校验：
# 后端重启 → INSTANCE_ID 变化 → 旧凭证不匹配 → 强制回登录页。
# 用于对抗浏览器"继续上次会话"恢复 sessionStorage 的行为。
INSTANCE_ID = uuid.uuid4().hex[:12]

# 数据库（从 .env 读取；未配置时使用占位，避免真实机密进入仓库）
DB_URL = os.environ.get("DB_URL", "mysql+pymysql://root:CHANGE_ME@localhost:3306/smart_classroom?charset=utf8mb4")

# JWT
SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME-please-set-in-.env")
TOKEN_EXPIRE_HOURS = 12

# 签到核心参数
FACE_SIM_THRESHOLD = 0.40      # InsightFace 余弦相似度阈值
GEOFENCE_DEFAULT_M = 200       # 默认签到范围（米）
LATE_MINUTES = 10              # 超过此分钟数签到记为迟到

# AI（阿里百炼 OpenAI 兼容接口；Key 从 .env/env 读取，绝不硬编码）
AI_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
AI_MODEL = "deepseek-v4-pro-0813"

# 文件存储
UPLOAD_DIR = BASE_DIR / "uploads"
