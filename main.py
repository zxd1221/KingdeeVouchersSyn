"""
金蝶凭证同步 — 主入口 / 示例
Kingdee Voucher Sync — Main entry point / Usage example

Run:
    pip install -r requirements.txt
    python main.py
"""

import logging
import sys
from datetime import date

from kingdee_client import KingdeeClient, KingdeeAPIError
from models import Voucher, VoucherEntry
from sync_service import VoucherSyncService

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 今天的日期 — today's date
TODAY = date.today()


# ── Sample data builder ────────────────────────────────────────────────────────

def build_single_voucher() -> Voucher:
    """
    构造单条测试凭证（使用今天日期）。
    Build a single test voucher using today's date.

    必填字段 / Required fields:
      Header : FDate, FVoucherGroupID, FDocumentStatus, FPrepareID
      Entry  : FSeq, FAccountID, FExplanation, FDEBIT, FCREDIT,
               FCurrencyID, FExchangeRate, FLocalDebit, FLocalCredit
    """
    return Voucher(
        date=TODAY,
        voucher_group="记",           # 凭证字（必填）
        explanation="单条保存测试-银行存款收款",
        preparer="admin",             # 制单人（必填）
        entries=[
            VoucherEntry(
                account_number="1002",   # 银行存款（必填科目编码）
                explanation="收回货款",
                debit=5000.00,
                credit=0.00,
                currency="CNY",          # 币别（必填）
                exchange_rate=1.0,       # 汇率（必填）
            ),
            VoucherEntry(
                account_number="1122",   # 应收账款（必填科目编码）
                explanation="核销应收账款",
                debit=0.00,
                credit=5000.00,
                currency="CNY",
                exchange_rate=1.0,
            ),
        ],
    )


def build_batch_vouchers() -> list[Voucher]:
    """
    构造批量测试凭证列表（使用今天日期）。
    Build multiple test vouchers using today's date.

    必填字段 / Required fields:
      Header : FDate, FVoucherGroupID, FDocumentStatus, FPrepareID
      Entry  : FSeq, FAccountID, FExplanation, FDEBIT, FCREDIT,
               FCurrencyID, FExchangeRate, FLocalDebit, FLocalCredit
    """
    return [
        # 批量凭证 1：应收账款回款
        Voucher(
            date=TODAY,
            voucher_group="记",
            explanation="批量测试-应收账款回款",
            preparer="admin",
            entries=[
                VoucherEntry(
                    account_number="1002",   # 银行存款
                    explanation="收回货款",
                    debit=10000.00,
                    credit=0.00,
                    currency="CNY",
                    exchange_rate=1.0,
                ),
                VoucherEntry(
                    account_number="1122",   # 应收账款
                    explanation="核销应收账款",
                    debit=0.00,
                    credit=10000.00,
                    currency="CNY",
                    exchange_rate=1.0,
                ),
            ],
        ),
        # 批量凭证 2：成本结转
        Voucher(
            date=TODAY,
            voucher_group="记",
            explanation="批量测试-成本结转",
            preparer="admin",
            entries=[
                VoucherEntry(
                    account_number="6401",   # 主营业务成本
                    explanation="结转销售成本",
                    debit=6000.00,
                    credit=0.00,
                    currency="CNY",
                    exchange_rate=1.0,
                ),
                VoucherEntry(
                    account_number="1405",   # 库存商品
                    explanation="减少库存",
                    debit=0.00,
                    credit=6000.00,
                    currency="CNY",
                    exchange_rate=1.0,
                ),
            ],
        ),
    ]


# ── Demo operations ────────────────────────────────────────────────────────────

def demo_save(service: VoucherSyncService) -> None:
    """单条保存凭证示例 — Single save voucher demo."""
    logger.info("=" * 60)
    logger.info("单条保存凭证 (Save) Demo  [日期: %s]", TODAY)
    logger.info("=" * 60)

    voucher = build_single_voucher()
    logger.info("准备单条保存凭证（日期=%s，凭证字=%s）...", voucher.date, voucher.voucher_group)

    result = service.save_voucher(voucher, validate=True)
    logger.info("Save 完成，API 响应: %s", result)


def demo_batch_save(service: VoucherSyncService) -> None:
    """批量保存凭证示例 — Batch save vouchers demo."""
    logger.info("=" * 60)
    logger.info("批量保存凭证 (BatchSave) Demo  [日期: %s]", TODAY)
    logger.info("=" * 60)

    vouchers = build_batch_vouchers()
    logger.info("准备批量保存 %d 张凭证...", len(vouchers))

    result = service.batch_save_vouchers(vouchers, validate=True)
    logger.info("BatchSave 完成，API 响应: %s", result)


def demo_query(service: VoucherSyncService) -> None:
    """单据查询示例 — Query vouchers demo."""
    logger.info("=" * 60)
    logger.info("单据查询 (ExecuteBillQuery) Demo")
    logger.info("=" * 60)

    results = service.query_vouchers(
        date_from=date(TODAY.year, TODAY.month, 1),
        date_to=TODAY,
        limit=20,
    )

    if not results:
        logger.info("未查询到凭证记录")
        return

    logger.info("查询到 %d 条凭证:", len(results))
    for r in results:
        logger.info(
            "  ID=%-20s  日期=%-12s  凭证字=%s  号=%s  状态=%s  摘要=%s",
            r.voucher_id,
            r.date,
            r.voucher_group,
            r.number,
            r.document_status,
            r.explanation,
        )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        with VoucherSyncService() as service:
            demo_save(service)
            demo_batch_save(service)
            demo_query(service)
    except KingdeeAPIError as exc:
        logger.error("金蝶 API 错误: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("未预期的错误: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
