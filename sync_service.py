"""
凭证同步服务
Voucher synchronization service

Bridges your internal voucher data with the Kingdee K3 Cloud API.
Supports batch creation and querying of GL_VOUCHER entries.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import config
from kingdee_client import KingdeeClient, KingdeeAPIError
from models import Voucher, VoucherQueryResult

logger = logging.getLogger(__name__)

# Default fields returned by query_vouchers
DEFAULT_QUERY_FIELDS = (
    "FVoucherID"
    ",FDate"
    ",FVoucherGroupID.FNumber"
    ",FVoucherGroupNo"
    ",FExplanation"
    ",FDocumentStatus"
    ",FCreatorID.FName"
    ",FCreateDate"
)


class VoucherSyncService:
    """
    凭证同步服务

    Wraps KingdeeClient to provide high-level methods:
      - batch_save_vouchers : 批量保存凭证
      - query_vouchers      : 单据查询（支持日期范围、状态过滤）
    """

    def __init__(self, client: Optional[KingdeeClient] = None) -> None:
        self.client = client or KingdeeClient.from_config()

    # ── 单条保存凭证 ────────────────────────────────────────────────────────────

    def save_voucher(
        self,
        voucher: Voucher,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        单条保存凭证 — Save a single voucher to Kingdee.

        Args:
            voucher:  Voucher 对象
            validate: 是否在提交前校验借贷平衡（默认开启）

        Returns:
            原始 API 响应
        """
        if validate:
            voucher.validate()

        self.client._ensure_logged_in()
        data = voucher.to_kingdee_data()
        logger.info("Saving single voucher (date=%s, group=%s)...", voucher.date, voucher.voucher_group)
        result = self.client.save(config.VOUCHER_FORM_ID, data)
        return result

    # ── 批量保存凭证 ────────────────────────────────────────────────────────────

    def batch_save_vouchers(
        self,
        vouchers: List[Voucher],
        validate: bool = True,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        批量保存凭证 — Batch-create vouchers in Kingdee.

        Args:
            vouchers:   Voucher 对象列表
            validate:   是否在提交前校验借贷平衡（默认开启）
            batch_size: 每批次提交的最大凭证数（默认 50）

        Returns:
            最后一批的原始 API 响应
        """
        if not vouchers:
            logger.warning("batch_save_vouchers called with empty list")
            return {}

        if validate:
            for i, v in enumerate(vouchers):
                try:
                    v.validate()
                except ValueError as exc:
                    raise ValueError(f"Voucher[{i}] validation failed: {exc}") from exc

        # Split into chunks to avoid oversized requests
        chunks = [vouchers[i: i + batch_size] for i in range(0, len(vouchers), batch_size)]
        last_result: Dict[str, Any] = {}

        logger.info(
            "Saving %d voucher(s) in %d batch(es)...",
            len(vouchers),
            len(chunks),
        )

        self.client._ensure_logged_in()

        for idx, chunk in enumerate(chunks, start=1):
            data_list = [v.to_kingdee_data() for v in chunk]
            logger.info("Submitting batch %d/%d (%d voucher(s))...", idx, len(chunks), len(chunk))
            last_result = self.client.batch_save(config.VOUCHER_FORM_ID, data_list)

        return last_result

    # ── 单据查询 ────────────────────────────────────────────────────────────────

    def query_vouchers(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        document_status: Optional[str] = None,
        voucher_group: Optional[str] = None,
        field_keys: str = DEFAULT_QUERY_FIELDS,
        order_string: str = "FDate desc,FVoucherGroupNo desc",
        limit: int = 100,
        start_row: int = 0,
    ) -> List[VoucherQueryResult]:
        """
        单据查询 — Query existing vouchers from Kingdee.

        Args:
            date_from:       开始日期（含）
            date_to:         结束日期（含）
            document_status: 单据状态过滤，例如 "A"（暂存）、"C"（已审核）
            voucher_group:   凭证字过滤，例如 "记"
            field_keys:      返回字段列表（逗号分隔）
            order_string:    排序字段
            limit:           返回条数限制
            start_row:       分页起始行

        Returns:
            VoucherQueryResult 列表
        """
        filters: List[str] = []

        if date_from:
            filters.append(f"FDate>='{date_from.strftime('%Y-%m-%d')}'")
        if date_to:
            filters.append(f"FDate<='{date_to.strftime('%Y-%m-%d')}'")
        if document_status:
            filters.append(f"FDocumentStatus='{document_status}'")
        if voucher_group:
            filters.append(f"FVoucherGroupID.FNumber='{voucher_group}'")

        filter_string = " and ".join(filters)

        logger.info(
            "Querying GL_VOUCHER | filter=%r | limit=%d | start=%d",
            filter_string,
            limit,
            start_row,
        )

        rows = self.client.query(
            form_id=config.VOUCHER_FORM_ID,
            field_keys=field_keys,
            filter_string=filter_string,
            order_string=order_string,
            limit=limit,
            start_row=start_row,
        )

        results = [VoucherQueryResult.from_row(r) for r in rows]
        logger.info("Query returned %d record(s)", len(results))
        return results

    def query_vouchers_raw(
        self,
        field_keys: str = DEFAULT_QUERY_FIELDS,
        filter_string: str = "",
        order_string: str = "FDate desc",
        limit: int = 100,
        start_row: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        原始查询，返回字典列表（不转换为 VoucherQueryResult）。
        Raw query — returns plain dicts, useful for custom field sets.
        """
        return self.client.query(
            form_id=config.VOUCHER_FORM_ID,
            field_keys=field_keys,
            filter_string=filter_string,
            order_string=order_string,
            limit=limit,
            start_row=start_row,
        )

    # ── Context manager passthrough ─────────────────────────────────────────────

    def __enter__(self) -> "VoucherSyncService":
        self.client.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.client.logout()
