"""
凭证数据模型
Voucher data models for Kingdee K3 Cloud GL_VOUCHER
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


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

    def to_kingdee_row(self, seq: int = 1) -> dict:
        """Convert to Kingdee API row format."""
        return {
            "FEntryID": 0,
            "FSeq": seq,
            "FAccountID": {"FNumber": self.account_number},
            "FExplanation": self.explanation,
            "FDEBIT": self.debit,
            "FCREDIT": self.credit,
            "FCurrencyID": {"FNumber": self.currency},
            "FExchangeRate": self.exchange_rate,
            "FLocalDebit": self.local_debit,
            "FLocalCredit": self.local_credit,
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
    account_book: str = ""
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
        """Convert to Kingdee BatchSave data format for GL_VOUCHER."""
        date_str = self.date.strftime("%Y-%m-%dT00:00:00")
        rows = [e.to_kingdee_row(seq=i + 1) for i, e in enumerate(self.entries)]

        data: dict = {
            "FDate": date_str,
            "FVoucherGroupID": {"FNumber": self.voucher_group},
            "FExplanation": self.explanation,
            "FDocumentStatus": "A",
            "FAttachments": 0,
            "FPrepareID": {"FUserName": self.preparer},
            "FEntity": {
                "FEntityKey": "FEntity",
                "Row": rows,
            },
        }

        if self.voucher_no:
            data["FVoucherGroupNo"] = self.voucher_no

        if self.account_book:
            data["FAccountBookID"] = {"FNumber": self.account_book}

        return data


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
            voucher_id=str(row.get("FVoucherID", "")),
            date=str(row.get("FDate", "")),
            number=str(row.get("FVoucherGroupNo", "")),
            voucher_group=str(row.get("FVoucherGroupID", "")),
            explanation=str(row.get("FExplanation", "")),
            document_status=str(row.get("FDocumentStatus", "")),
            raw=row,
        )
