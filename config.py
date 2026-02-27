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
PASSWORD: str = os.getenv("KINGDEE_PASSWORD", "dell@123")
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

# ── 账簿编码 (必填) ────────────────────────────────────────────────────────────
# 必须填写金蝶系统中实际的账簿 FNumber，否则保存凭证时会报"账簿是必填项"。
# 查找方式：金蝶系统 → 总账 → 初始设置 → 账簿，查看账簿编码列。
# Must be set to the real account book FNumber in your Kingdee instance.
ACCOUNT_BOOK: str = os.getenv("KINGDEE_ACCOUNT_BOOK", "")

# ── 汇率类型 (必填) ────────────────────────────────────────────────────────────
# 必须填写金蝶系统中实际使用的汇率类型 FNumber（如 "HLTX01_SYS"）。
# 查找方式：金蝶系统 → 基础设置 → 汇率管理 → 汇率类型，查看编码列。
# Must be set to the exchange rate type FNumber used in your Kingdee instance.
EXCHANGE_RATE_TYPE: str = os.getenv("KINGDEE_EXCHANGE_RATE_TYPE", "")

# ── 默认凭证字 (必填) ─────────────────────────────────────────────────────────
# 金蝶系统中的凭证字 FNumber（如 "PRE001"，标准系统常见值为 "记"）。
# 查找方式：金蝶系统 → 总账 → 初始设置 → 凭证字，查看编码列。
# Set to the voucher group FNumber used in your Kingdee instance.
VOUCHER_GROUP: str = os.getenv("KINGDEE_VOUCHER_GROUP", "记")

# ── 默认币别 (必填) ───────────────────────────────────────────────────────────
# 金蝶系统中人民币的 FNumber（标准值 "CNY"，部分系统用其他编码如 "PRE001"）。
# 查找方式：金蝶系统 → 基础设置 → 币别，查看编码列。
# Set to the RMB currency FNumber used in your Kingdee instance.
CURRENCY_CODE: str = os.getenv("KINGDEE_CURRENCY", "CNY")
