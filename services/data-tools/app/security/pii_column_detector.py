from typing import Dict, Iterable, List, Optional


PII_KEYWORDS = (
    "email",
    "mail",
    "phone",
    "mobile",
    "name",
    "full_name",
    "fio",
    "address",
    "passport",
    "inn",
    "snils",
    "card",
    "account",
)


def pii_kind(column_name: str) -> Optional[str]:
    normalized = column_name.lower().replace(" ", "_")
    if "email" in normalized or "mail" in normalized:
        return "email"
    if "phone" in normalized or "mobile" in normalized:
        return "phone"
    if any(keyword in normalized for keyword in PII_KEYWORDS):
        return "pii"
    return None


def has_pii_hint(column_name: str) -> bool:
    return pii_kind(column_name) is not None


def detect_pii_columns(columns: Iterable[str]) -> List[str]:
    return [column for column in columns if has_pii_hint(column)]


def mask_value(column_name: str, value):
    if value is None:
        return None
    kind = pii_kind(column_name)
    if kind == "email":
        return "[EMAIL]"
    if kind == "phone":
        return "[PHONE]"
    if kind == "pii":
        return "[PII]"
    return value


def mask_records(records: List[Dict], pii_columns: Iterable[str]) -> List[Dict]:
    pii_set = set(pii_columns)
    masked = []
    for record in records:
        masked.append(
            {
                key: mask_value(key, value) if key in pii_set else value
                for key, value in record.items()
            }
        )
    return masked
