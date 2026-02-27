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

def _build_exact_test_model() -> dict:
    """
    直接复现官方 WebAPI 测试中可以成功保存的 Model 数据，原样传给 client.save()。
    Reproduces the exact Model dict from the known-working WebAPI test payload.
    系统相关编码（账簿/凭证字/币别/汇率类型）来自 config/.env；
    科目编码使用官方测试数据中真实存在的编码。
    """
    date_str = TODAY.strftime("%Y-%m-%d 00:00:00")
    cx = config.CURRENCY_CODE          # e.g. "PRE001"
    rt = config.EXCHANGE_RATE_TYPE     # e.g. "HLTX01_SYS"

    def entry(explanation, account, debit, credit, detail_id=None):
        row = {
            "FEXPLANATION": explanation,
            "FACCOUNTID": {"FNumber": account},
            "FCURRENCYID": {"FNumber": cx},
            "FEXCHANGERATETYPE": {"FNumber": rt},
            "FEXCHANGERATE": 1.0,
            "FPrice": 0.0,
            "FQty": 0.0,
            "FAMOUNTFOR": debit if debit else credit,
            "FDEBIT": debit,
            "FCREDIT": credit,
            "FEXPORTENTRYID": 0,
        }
        if detail_id:
            row["FDetailID"] = detail_id
        return row

    flex6_113 = {"FDETAILID__FFLEX6": {"FNumber": "113"}}
    flex6_7_113 = {"FDETAILID__FFLEX6": {"FNumber": "113"}, "FDETAILID__FFLEX7": {"FNumber": "113"}}

    return {
        "FVOUCHERID": 0,
        "FAccountBookID": {"FNumber": config.ACCOUNT_BOOK},
        "FDate": date_str,
        "FBUSDATE": date_str,
        "FYEAR": TODAY.year,
        "FPERIOD": TODAY.month,
        "FVOUCHERGROUPID": {"FNumber": config.VOUCHER_GROUP},
        "FVOUCHERGROUPNO": "",        # 空 = 系统自动分配凭证号
        "FATTACHMENTS": 0,
        "FISADJUSTVOUCHER": False,
        "FDocumentStatus": "Z",
        "FEntity": [
            entry("361度运动生活京东自营-销售收入",       "1122.01", 41932.50,     0.0,      flex6_113),
            entry("361度运动生活京东自营-销售收入(瑜伽)", "6001.11", 0.0,      29921.76, flex6_113),
            entry("361度运动生活京东自营-销售收入(内衣)", "6001.14", 0.0,       7186.65, flex6_113),
            entry("361度运动生活京东自营-销售收入(税费)", "6001.09", 0.0,       4824.09, flex6_113),
            entry("361度运动生活京东自营-销售成本(库存商品)", "1405.24", 0.0,  14872.44),
            entry("361度运动生活京东自营-销售成本(库存商品)", "1405.24", 0.0,   3610.10),
            entry("361度运动生活京东自营-销售成本(瑜伽)", "6401.11", 14872.44,     0.0,  flex6_7_113),
            entry("361度运动生活京东自营-销售成本(内衣)", "6401.14",  3610.10,     0.0,  flex6_7_113),
            entry("361度运动生活京东自营-授权金成本(瑜伽防晒)", "1801.06", 0.0, 1487.24, flex6_7_113),
            entry("361度运动生活京东自营-授权金成本(内衣保暖)", "1801.10", 0.0,  361.01, flex6_7_113),
            entry("361度运动生活京东自营-授权金成本",         "6401.09",  1848.25,    0.0,  flex6_7_113),
        ],
    }


def demo_save(service: VoucherSyncService) -> None:
    """
    单条保存凭证 — 直接使用 WebAPI 可成功保存的精确 Model 数据。
    Bypasses Voucher/VoucherEntry mapping and calls client.save() with the
    raw model dict that is known to work in the official WebAPI test tool.
    """
    logger.info("=" * 60)
    logger.info("单条保存凭证 (Save) Demo  [日期: %s]", TODAY)
    logger.info("=" * 60)

    model = _build_exact_test_model()
    logger.info("准备保存凭证（账簿=%s  凭证字=%s  分录数=%d）...",
                config.ACCOUNT_BOOK, config.VOUCHER_GROUP, len(model["FEntity"]))
    result = service.client.save(config.VOUCHER_FORM_ID, model)
    logger.info("Save 完成，API 响应: %s", result)


def demo_batch_save(service: VoucherSyncService) -> None:
    """
    批量保存凭证 — 使用两份与 WebAPI 精确测试一致的 Model 数据。
    Uses two copies of the known-working model dict for batch save verification.
    """
    logger.info("=" * 60)
    logger.info("批量保存凭证 (BatchSave) Demo  [日期: %s]", TODAY)
    logger.info("=" * 60)

    model1 = _build_exact_test_model()
    model2 = _build_exact_test_model()
    models = [model1, model2]
    logger.info("准备批量保存 %d 张凭证（各 %d 条分录）...",
                len(models), len(model1["FEntity"]))
    result = service.client.batch_save(config.VOUCHER_FORM_ID, models)
    logger.info("BatchSave 完成，API 响应: %s", result)


def _print_query_results(results, label: str) -> None:
    if not results:
        logger.info("[%s] 未查询到凭证记录", label)
        return
    logger.info("[%s] 查询到 %d 条分录:", label, len(results))
    for r in results:
        logger.info(
            "  ID=%-10s  %s年%s期  号=%-6s  科目=%-12s %s  借=%-12.2f  贷=%-12.2f  摘要=%s",
            r.voucher_id,
            r.year,
            r.period,
            r.number,
            r.account_id,
            r.account_name,
            r.debit,
            r.credit,
            r.explanation,
        )


def demo_query(service: VoucherSyncService) -> None:
    """单据查询示例 — Query vouchers demo.

    Tests three scenarios to isolate any format vs data issue:
      1. No filter  — should return the first 10 records across all years
      2. FYEAR=2024 — exact match to the known-working WebAPI tester JSON
      3. FYEAR=TODAY.year — query for the current year
    """
    logger.info("=" * 60)
    logger.info("单据查询 (ExecuteBillQuery) Demo")
    logger.info("=" * 60)

    # ── 场景 1：无过滤条件，取前 10 条（验证 API 连通性与格式）─────────────────
    logger.info("--- 场景 1：无过滤条件（前 10 条） ---")
    _print_query_results(
        service.query_vouchers(limit=10),
        "无过滤",
    )

    # ── 场景 2：FYEAR=2024（与官方 WebAPI 测试完全一致）──────────────────────────
    logger.info("--- 场景 2：FYEAR=2024（与 WebAPI 测试一致） ---")
    _print_query_results(
        service.query_vouchers(year=2024, limit=10),
        "FYEAR=2024",
    )

    # ── 场景 3：当前年度 ────────────────────────────────────────────────────────
    logger.info("--- 场景 3：FYEAR=%d（当前年度） ---", TODAY.year)
    _print_query_results(
        service.query_vouchers(year=TODAY.year, limit=10),
        f"FYEAR={TODAY.year}",
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
