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

import config
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

    凭证字、币别、账簿、汇率类型均从 config / .env 读取，无需在此硬编码。
    voucher_group / currency / account_book / exchange_rate_type are all
    driven by config so only the .env file needs updating.

    账号编码必须是金蝶系统中实际存在的科目编码，否则 NumberSearch 会找不到科目。
    account_number values must exist in your Kingdee chart of accounts.
    """
    return Voucher(
        date=TODAY,
        # voucher_group / account_book read from config.VOUCHER_GROUP / ACCOUNT_BOOK
        entries=[
            VoucherEntry(
                account_number="1002",   # 请替换为系统中实际存在的借方科目编码
                explanation="收回货款",
                debit=5000.00,
                credit=0.00,
                # currency / exchange_rate_type read from config
            ),
            VoucherEntry(
                account_number="1122",   # 请替换为系统中实际存在的贷方科目编码
                explanation="核销应收账款",
                debit=0.00,
                credit=5000.00,
            ),
        ],
    )


def build_batch_vouchers() -> list[Voucher]:
    """
    构造批量测试凭证列表（使用今天日期）。
    Build multiple test vouchers using today's date.
    凭证字、币别、账簿、汇率类型均从 config / .env 读取。
    """
    return [
        # 批量凭证 1：应收账款回款
        Voucher(
            date=TODAY,
            entries=[
                VoucherEntry(
                    account_number="1002",   # 请替换为系统中实际存在的科目编码
                    explanation="收回货款",
                    debit=10000.00,
                    credit=0.00,
                ),
                VoucherEntry(
                    account_number="1122",   # 请替换为系统中实际存在的科目编码
                    explanation="核销应收账款",
                    debit=0.00,
                    credit=10000.00,
                ),
            ],
        ),
        # 批量凭证 2：成本结转
        Voucher(
            date=TODAY,
            entries=[
                VoucherEntry(
                    account_number="6401",   # 请替换为系统中实际存在的科目编码
                    explanation="结转销售成本",
                    debit=6000.00,
                    credit=0.00,
                ),
                VoucherEntry(
                    account_number="1405",   # 请替换为系统中实际存在的科目编码
                    explanation="减少库存",
                    debit=0.00,
                    credit=6000.00,
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

def _check_config() -> None:
    """在运行前检查必要配置项，给出明确提示。"""
    missing = []
    if not config.ACCOUNT_BOOK:
        missing.append("KINGDEE_ACCOUNT_BOOK  (账簿编码，如 '002')")
    if not config.EXCHANGE_RATE_TYPE:
        missing.append("KINGDEE_EXCHANGE_RATE_TYPE  (汇率类型，如 'HLTX01_SYS')")
    if missing:
        logger.warning(
            "以下必填配置项未设置，保存凭证可能失败。请在 .env 文件中添加：\n  %s",
            "\n  ".join(missing),
        )
    logger.info(
        "当前配置 → 账簿=%r  凭证字=%r  币别=%r  汇率类型=%r",
        config.ACCOUNT_BOOK,
        config.VOUCHER_GROUP,
        config.CURRENCY_CODE,
        config.EXCHANGE_RATE_TYPE,
    )


def main() -> int:
    _check_config()
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
