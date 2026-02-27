"""
凭证数据模型
Voucher data models for Kingdee K3 Cloud GL_VOUCHER
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

import config


@dataclass
class VoucherEntry:
    """
    凭证分录 — Voucher detail line

    Args:
        account_number: 科目编码，例如 "1001"
        explanation:    分录摘要
        debit:          借方金额
        credit:         贷方金额
        currency:       币别编码，默认 "CNY"
        exchange_rate:  汇率，默认 1.0
        local_debit:    本币借方金额（为 None 时自动计算）
        local_credit:   本币贷方金额（为 None 时自动计算）
    """
    account_number: str
    explanation: str
    debit: float = 0.0
    credit: float = 0.0
    currency: str = "CNY"
    exchange_rate: float = 1.0
    local_debit: Optional[float] = None
    local_credit: Optional[float] = None

    def __post_init__(self) -> None:
        if self.local_debit is None:
            self.local_debit = round(self.debit * self.exchange_rate, 2)
        if self.local_credit is None:
            self.local_credit = round(self.credit * self.exchange_rate, 2)

    def to_kingdee_row(self) -> dict:
        """Convert to Kingdee API row format (per official GL_VOUCHER docs)."""
        return {
            "FEntryID": 0,
            "FEXPLANATION": self.explanation,
            "FACCOUNTID": {"FNumber": self.account_number},
            "FCURRENCYID": {"FNumber": self.currency},
            "FEXCHANGERATETYPE": {"FNumber": ""},
            "FEXCHANGERATE": self.exchange_rate,
            "FAMOUNTFOR": self.debit if self.debit else self.credit,
            "FDEBIT": self.debit,
            "FCREDIT": self.credit,
        }


@dataclass
class Voucher:
    """
    凭证头 — Voucher header

    Args:
        date:          凭证日期
        entries:       分录列表
        voucher_group: 凭证字，默认 "记"
        voucher_no:    凭证号（0 = 系统自动编号）
        explanation:   凭证摘要
        account_book:  账簿编码（为空时使用默认账簿）
        preparer:      制单人用户名
    """
    date: date
    entries: List[VoucherEntry]
    voucher_group: str = "记"
    voucher_no: int = 0
    explanation: str = ""
    account_book: str = field(default_factory=lambda: config.ACCOUNT_BOOK)
    preparer: str = "admin"

    def validate(self) -> None:
        """Basic balance validation — debit total must equal credit total."""
        total_debit = round(sum(e.debit for e in self.entries), 2)
        total_credit = round(sum(e.credit for e in self.entries), 2)
        if total_debit != total_credit:
            raise ValueError(
                f"Voucher imbalanced: debit={total_debit}, credit={total_credit}"
            )
        if not self.entries:
            raise ValueError("Voucher must have at least one entry")

    def to_kingdee_data(self) -> dict:
        """Convert to Kingdee Save/BatchSave Model format for GL_VOUCHER.

        Field names strictly follow the official GL_VOUCHER API documentation.
        Required header fields: FAccountBookID, FDate, FVOUCHERGROUPID,
        FDocumentStatus, FVOUCHERGROUPNO.
        """
        date_str = self.date.strftime("%Y-%m-%d")
        rows = [e.to_kingdee_row() for e in self.entries]

        model: dict = {
            "FVOUCHERID": 0,
            "FDate": date_str,
            "FBUSDATE": date_str,
            "FVOUCHERGROUPID": {"FNumber": self.voucher_group},
            "FVOUCHERGROUPNO": str(self.voucher_no) if self.voucher_no else "",
            "FATTACHMENTS": 0,
            "FDocumentStatus": "A",
            "FEntity": rows,
        }
        # FAccountBookID is required by the API; include it only when a value is
        # configured so the server returns a clear "账簿是必填项" error instead of
        # silently ignoring a blank FNumber search.
        if self.account_book:
            model["FAccountBookID"] = {"FNumber": self.account_book}
        return model


@dataclass
class VoucherQueryResult:
    """单据查询结果 — Voucher query result row."""
    voucher_id: str = ""
    date: str = ""
    number: str = ""
    voucher_group: str = ""
    explanation: str = ""
    document_status: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict) -> "VoucherQueryResult":
        return cls(
            voucher_id=str(row.get("FVOUCHERID", "")),
            date=str(row.get("FDate", "")),
            number=str(row.get("FVOUCHERGROUPNO", "")),
            voucher_group=str(row.get("FVOUCHERGROUPID.FNumber", "")),
            explanation="",  # explanation is in FEntity entries, not the header
            document_status=str(row.get("FDocumentStatus", "")),
            raw=row,
        )
