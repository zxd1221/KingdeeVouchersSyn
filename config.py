"""
金蝶云星空 K3 Cloud API 配置
Kingdee K3 Cloud API Configuration

Credentials are loaded from environment variables (.env file) with hardcoded defaults.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── 连接配置 ─────────────────────────────────────────────────────────────────
BASE_URL: str = os.getenv("KINGDEE_BASE_URL", "https://gljwl.ik3cloud.com")
ACCT_ID: str = os.getenv("KINGDEE_ACCT_ID", "20210324173947733")
USERNAME: str = os.getenv("KINGDEE_USERNAME", "admin")
# 密钥 / API 密码
PASSWORD: str = os.getenv("KINGDEE_PASSWORD", "ca058a5dfe9b4d90813b9590bc646590")
APP_ID: str = os.getenv("KINGDEE_APP_ID", "454962_WdbB3dhuTpH/7YUFRYxo3YzM0MX90BMo")
# 语言 ID: 2052 = 简体中文
LCID: int = int(os.getenv("KINGDEE_LCID", "2052"))

# ── 请求超时（秒） ────────────────────────────────────────────────────────────
TIMEOUT_LOGIN: int = 30
TIMEOUT_REQUEST: int = 60

# ── API 路径 ──────────────────────────────────────────────────────────────────
_BASE_PATH = "/k3cloud/Kingdee.BOS.WebApi.ServicesStub"
ENDPOINTS = {
    "login":      f"{_BASE_PATH}.AuthService.ValidateUser.common.kdsvc",
    "logout":     f"{_BASE_PATH}.AuthService.Logout.common.kdsvc",
    "save":       f"{_BASE_PATH}.DynamicFormService.Save.common.kdsvc",
    "batch_save": f"{_BASE_PATH}.DynamicFormService.BatchSave.common.kdsvc",
    "query":      f"{_BASE_PATH}.DynamicFormService.ExecuteBillQuery.common.kdsvc",
    "view":       f"{_BASE_PATH}.DynamicFormService.View.common.kdsvc",
}

# ── 凭证表单 ID ───────────────────────────────────────────────────────────────
VOUCHER_FORM_ID = "GL_VOUCHER"
