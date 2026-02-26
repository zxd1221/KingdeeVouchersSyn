"""
金蝶云星空 K3 Cloud WebAPI 客户端
Kingdee K3 Cloud WebAPI client

Implements:
  - Session-based authentication (ValidateUser / KDSESSIONID cookie)
  - 批量保存  (BatchSave)   — create / update multiple vouchers in one call
  - 单据查询  (ExecuteBillQuery) — query vouchers with filters
"""

import logging
from typing import Any, Dict, List, Optional

import requests

import config

logger = logging.getLogger(__name__)


class KingdeeAPIError(Exception):
    """Raised when the Kingdee API returns a business-level error."""


class KingdeeClient:
    """
    Kingdee K3 Cloud WebAPI client.

    Usage (context manager — recommended):
    ----------------------------------------
        with KingdeeClient.from_config() as client:
            result = client.batch_save_vouchers(data_list)

    Usage (manual login/logout):
    ----------------------------------------
        client = KingdeeClient.from_config()
        client.login()
        try:
            ...
        finally:
            client.logout()
    """

    # ── Constructor ────────────────────────────────────────────────────────────

    def __init__(
        self,
        base_url: str,
        acct_id: str,
        username: str,
        password: str,
        lcid: int = 2052,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.acct_id = acct_id
        self.username = username
        self.password = password
        self.lcid = lcid
        self._logged_in = False

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    @classmethod
    def from_config(cls) -> "KingdeeClient":
        """Create a client from config.py settings."""
        return cls(
            base_url=config.BASE_URL,
            acct_id=config.ACCT_ID,
            username=config.USERNAME,
            password=config.PASSWORD,
            lcid=config.LCID,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _url(self, endpoint_key: str) -> str:
        return f"{self.base_url}{config.ENDPOINTS[endpoint_key]}"

    def _post(self, endpoint_key: str, payload: dict, timeout: int = config.TIMEOUT_REQUEST) -> Any:
        url = self._url(endpoint_key)
        logger.debug("POST %s  payload=%s", url, payload)
        resp = self.session.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ── Authentication ─────────────────────────────────────────────────────────

    def login(self) -> None:
        """
        调用 ValidateUser 登录，获取 KDSESSIONID cookie。
        Login and obtain the KDSESSIONID session cookie.
        """
        payload = {
            "acctID": self.acct_id,
            "username": self.username,
            "password": self.password,
            "lcid": self.lcid,
        }
        result = self._post("login", payload, timeout=config.TIMEOUT_LOGIN)

        # LoginResultType: 1 = success, others = failure
        login_type = result.get("LoginResultType", 0)
        if login_type != 1:
            msg = result.get("Message") or result.get("message") or str(result)
            raise KingdeeAPIError(f"Login failed (LoginResultType={login_type}): {msg}")

        self._logged_in = True
        logger.info("Logged in to Kingdee K3 Cloud [acctID=%s, user=%s]", self.acct_id, self.username)

    def logout(self) -> None:
        """退出登录 — Logout."""
        if not self._logged_in:
            return
        try:
            self._post("logout", {})
        except Exception as exc:
            logger.warning("Logout error (ignored): %s", exc)
        finally:
            self._logged_in = False
            logger.info("Logged out from Kingdee K3 Cloud")

    def _ensure_logged_in(self) -> None:
        if not self._logged_in:
            self.login()

    # ── 批量保存 BatchSave ─────────────────────────────────────────────────────

    def batch_save(
        self,
        form_id: str,
        data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        批量保存单据 — Batch save bills.

        Args:
            form_id: 表单 ID，凭证为 "GL_VOUCHER"
            data:    凭证数据列表（每项为一张凭证的字段字典）

        Returns:
            原始 API 响应字典，包含 Result.ResponseStatus
        """
        self._ensure_logged_in()
        payload = {
            "formid": form_id,
            "data": data,
        }
        result = self._post("batch_save", payload)
        self._check_batch_save_result(result)
        return result

    @staticmethod
    def _check_batch_save_result(result: Any) -> None:
        """Log success/failure details from a BatchSave response."""
        try:
            resp_status = result["Result"]["ResponseStatus"]
        except (KeyError, TypeError):
            logger.warning("Unexpected BatchSave response structure: %s", result)
            return

        if resp_status.get("IsSuccess"):
            successes = resp_status.get("SuccessEntitys", [])
            logger.info("BatchSave succeeded: %d record(s) saved", len(successes))
            for s in successes:
                logger.debug("  Saved: ID=%s  Number=%s", s.get("Id"), s.get("Number"))
        else:
            errors = resp_status.get("Errors", [])
            err_msgs = "; ".join(
                e.get("Message", str(e)) for e in errors
            )
            raise KingdeeAPIError(f"BatchSave failed: {err_msgs}")

    # ── 单据查询 ExecuteBillQuery ─────────────────────────────────────────────

    def query(
        self,
        form_id: str,
        field_keys: str,
        filter_string: str = "",
        order_string: str = "",
        limit: int = 100,
        start_row: int = 0,
        top_row_count: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        单据查询 — Query bills.

        Args:
            form_id:       表单 ID，凭证为 "GL_VOUCHER"
            field_keys:    逗号分隔的字段名，例如
                           "FVoucherID,FDate,FVoucherGroupNo,FExplanation,FDocumentStatus"
            filter_string: 过滤条件，例如 "FDate>='2024-01-01' and FDate<='2024-12-31'"
            order_string:  排序字段，例如 "FDate desc"
            limit:         每页记录数（最大值视服务器配置而定）
            start_row:     起始行（用于分页）
            top_row_count: 返回最多 N 条（0 = 不限制）

        Returns:
            记录列表，每条记录为 {字段名: 值} 的字典
        """
        self._ensure_logged_in()
        payload = {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": filter_string,
            "OrderString": order_string,
            "TopRowCount": top_row_count,
            "StartRow": start_row,
            "Limit": limit,
        }
        raw = self._post("query", payload)
        return self._parse_query_result(raw)

    @staticmethod
    def _parse_query_result(raw: Any) -> List[Dict[str, Any]]:
        """
        解析查询结果。金蝶返回格式为二维数组：
          第 0 行 = 字段名列表
          第 1..N 行 = 数据行

        Parse Kingdee query result (first row = headers, rest = data rows).
        """
        if not raw or not isinstance(raw, list) or len(raw) < 1:
            return []

        headers: List[str] = raw[0]
        rows: List[Dict[str, Any]] = []
        for row in raw[1:]:
            rows.append(dict(zip(headers, row)))
        return rows

    # ── Context manager ────────────────────────────────────────────────────────

    def __enter__(self) -> "KingdeeClient":
        self.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.logout()
