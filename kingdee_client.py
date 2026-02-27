"""
金蝶云星空 K3 Cloud WebAPI 客户端
Kingdee K3 Cloud WebAPI client

Implements:
  - Session-based authentication (ValidateUser / KDSESSIONID cookie)
  - 批量保存  (BatchSave)   — create / update multiple vouchers in one call
  - 单据查询  (ExecuteBillQuery) — query vouchers with filters
"""

import json
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

    # ── 单条保存 Save ──────────────────────────────────────────────────────────

    def save(
        self,
        form_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        单条保存单据 — Save a single bill.

        Args:
            form_id: 表单 ID，凭证为 "GL_VOUCHER"
            data:    单张凭证的字段字典

        Returns:
            原始 API 响应字典，包含 Result.ResponseStatus
        """
        self._ensure_logged_in()
        # The HTTP API expects data as a JSON object (not a double-encoded string).
        # The C# SDK docs show a JSON string *parameter*, but the SDK parses it
        # internally before POSTing, so the actual HTTP body has data as an object.
        payload = {
            "formid": form_id,
            "data": {
                "NeedUpDateFields": [],
                "NeedReturnFields": [],
                "IsDeleteEntry": "true",
                "SubSystemId": "",
                "IsVerifyBaseDataField": "false",
                "IsEntryBatchFill": "true",
                "ValidateFlag": "true",
                "NumberSearch": "true",
                "IsAutoAdjustField": "true",
                "InterationFlags": "",
                "IgnoreInterationFlag": "",
                "IsControlPrecision": "false",
                "ValidateRepeatJson": "false",
                "Model": data,
            },
        }
        logger.debug("Save payload: %s", payload)
        result = self._post("save", payload)
        self._check_save_result(result)
        return result

    @staticmethod
    def _check_save_result(result: Any) -> None:
        """Log success/failure details from a Save response."""
        try:
            resp_status = result["Result"]["ResponseStatus"]
        except (KeyError, TypeError):
            logger.warning("Unexpected Save response structure: %s", result)
            return

        if resp_status.get("IsSuccess"):
            successes = resp_status.get("SuccessEntitys", [])
            for s in successes:
                logger.info("Save succeeded: ID=%s  Number=%s", s.get("Id"), s.get("Number"))
        else:
            errors = resp_status.get("Errors", [])
            err_msgs = "; ".join(
                e.get("Message", str(e)) for e in errors
            )
            raise KingdeeAPIError(f"Save failed: {err_msgs}")

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
        # Same as save(): data must be a JSON object, not a double-encoded string.
        payload = {
            "formid": form_id,
            "data": {
                "NumberSearch": "true",
                "ValidateFlag": "true",
                "IsDeleteEntry": "true",
                "IsEntryBatchFill": "true",
                "NeedUpDateFields": [],
                "NeedReturnFields": [],
                "SubSystemId": "",
                "InterationFlags": "",
                "Model": data,
                "BatchCount": 0,
                "IsVerifyBaseDataField": "false",
                "IsAutoAdjustField": "true",
                "IgnoreInterationFlag": "false",
                "IsControlPrecision": "false",
                "ValidateRepeatJson": "false",
            },
        }
        logger.debug("BatchSave payload: %s", payload)
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
        filter_string: Any = "",
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
                           "FVOUCHERID,FDate,FVOUCHERGROUPNO,FEXPLANATION,FDEBIT,FCREDIT"
            filter_string: 过滤条件，支持两种格式：
                           - str: SQL 风格，如 "FDate>='2024-01-01'"
                           - list: 数组对象，如 [{"FieldName":"FYEAR","Compare":"76",
                             "Value":"2026","Left":"","Right":"","Logic":"0"}]
            order_string:  排序字段，例如 "FDate desc"
            limit:         每页记录数（最大值视服务器配置而定）
            start_row:     起始行（用于分页）
            top_row_count: 返回最多 N 条（0 = 不限制）

        Returns:
            记录列表，每条记录为 {字段名: 值} 的字典
        """
        self._ensure_logged_in()
        # ExecuteBillQuery requires data to be a JSON-encoded *string*,
        # matching the SDK signature: client.ExecuteBillQuery("{...json...}")
        # The WebAPI tester also stringifies the user input before posting.
        query_params = {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": filter_string,
            "OrderString": order_string,
            "TopRowCount": top_row_count,
            "StartRow": start_row,
            "Limit": limit,
            "SubSystemId": "",
        }
        payload = {"data": json.dumps(query_params, ensure_ascii=False)}
        logger.debug("Query payload data string: %s", payload["data"])
        raw = self._post("query", payload)
        logger.info("Query raw response: %s", str(raw)[:500])
        return self._parse_query_result(raw, field_keys)

    @staticmethod
    def _parse_query_result(raw: Any, field_keys: str = "") -> List[Dict[str, Any]]:
        """
        解析查询结果。金蝶返回格式有两种：

        格式 A（含表头行）：
          第 0 行 = 字段名列表（字符串）
          第 1..N 行 = 数据行

        格式 B（无表头行，直接数据）：
          第 0..N 行 = 数据行（第一个元素为非字符串类型）
          此时用传入的 field_keys 拆分后作为列名。

        错误情况有两种：
          - 顶层 dict：{"Result":{"ResponseStatus":...}}
          - 二维数组但第一行是错误对象：[[{"Result":...}]]
        两种都会 raise KingdeeAPIError。
        """
        def _extract_error(obj: Any) -> Optional[str]:
            """Return error message string if obj is a Kingdee error dict, else None."""
            if not isinstance(obj, dict):
                return None
            try:
                resp_status = obj["Result"]["ResponseStatus"]
                if not resp_status.get("IsSuccess", True):
                    errors = resp_status.get("Errors", [])
                    return "; ".join(e.get("Message", str(e)) for e in errors) or str(obj)
            except (KeyError, TypeError):
                pass
            return None

        # Case 1: top-level error dict
        if isinstance(raw, dict):
            msg = _extract_error(raw) or str(raw)
            raise KingdeeAPIError(f"Query failed: {msg}")

        if not raw or not isinstance(raw, list) or len(raw) < 1:
            return []

        # Case 2: error object embedded in first row of 2-D array  [[{Result:...}]]
        # The error dict may be the only element OR mixed with other elements.
        first_row = raw[0]
        if isinstance(first_row, list):
            for item in first_row:
                msg = _extract_error(item)
                if msg is not None:
                    raise KingdeeAPIError(f"Query failed: {msg}")

        if not isinstance(first_row, list):
            return []

        # Format A: first row contains string field names (header row)
        if first_row and isinstance(first_row[0], str):
            headers: List[str] = first_row
            rows: List[Dict[str, Any]] = []
            for row in raw[1:]:
                rows.append(dict(zip(headers, row)))
            return rows

        # Format B: no header row — API returns data rows directly.
        # Use field_keys (comma-separated) as column names.
        if field_keys:
            headers = [f.strip() for f in field_keys.split(",")]
            rows = []
            for row in raw:
                rows.append(dict(zip(headers, row)))
            return rows

        return []

    # ── Context manager ────────────────────────────────────────────────────────

    def __enter__(self) -> "KingdeeClient":
        self.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.logout()
