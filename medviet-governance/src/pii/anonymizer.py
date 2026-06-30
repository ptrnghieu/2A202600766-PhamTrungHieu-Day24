# src/pii/anonymizer.py
import hashlib
import random
import re

import pandas as pd
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from faker import Faker
from .detector import build_vietnamese_analyzer, detect_pii

fake = Faker("vi_VN")


def _fake_cccd() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(12))


def _fake_phone() -> str:
    return f"0{random.choice([3, 5, 7, 8, 9])}" + "".join(
        str(random.randint(0, 9)) for _ in range(8)
    )


def _mask_value(value: str) -> str:
    """Mask mỗi từ, giữ lại ký tự đầu: 'Nguyen Van A' -> 'N****** V** A'."""
    def mask_word(word: str) -> str:
        return word[0] + "*" * (len(word) - 1) if len(word) > 1 else word

    return " ".join(mask_word(w) if w else w for w in value.split(" "))


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class MedVietAnonymizer:

    def __init__(self):
        self.analyzer = build_vietnamese_analyzer()
        self.anonymizer = AnonymizerEngine()

    def anonymize_text(self, text: str, strategy: str = "replace") -> str:
        """
        Anonymize text với strategy được chọn.

        Strategies:
        - "mask"    : Nguyen Van A → N****** V** A
        - "replace" : thay bằng fake data (dùng Faker)
        - "hash"    : SHA-256 one-way hash
        - "generalize": chỉ dùng cho tuổi/năm sinh
        """
        results = detect_pii(text, self.analyzer)
        if not results:
            return text

        if strategy == "mask":
            chars = list(text)
            for r in sorted(results, key=lambda r: r.start, reverse=True):
                masked = _mask_value(text[r.start:r.end])
                chars[r.start:r.end] = list(masked)
            return "".join(chars)

        if strategy == "hash":
            chars = list(text)
            for r in sorted(results, key=lambda r: r.start, reverse=True):
                hashed = _hash_value(text[r.start:r.end])
                chars[r.start:r.end] = list(hashed)
            return "".join(chars)

        if strategy == "generalize":
            return re.sub(r"\b(\d{3})\d\b", r"\g<1>0s", text)

        operators = {
            "PERSON": OperatorConfig("replace",
                      {"new_value": fake.name()}),
            "EMAIL_ADDRESS": OperatorConfig("replace",
                             {"new_value": fake.email()}),
            "VN_CCCD": OperatorConfig("replace",
                       {"new_value": _fake_cccd()}),
            "VN_PHONE": OperatorConfig("replace",
                        {"new_value": _fake_phone()}),
        }

        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators
        )
        return anonymized.text

    def anonymize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymize toàn bộ DataFrame.
        - Cột text (ho_ten, dia_chi, email): dùng anonymize_text()
        - Cột cccd, so_dien_thoai: replace trực tiếp bằng fake data
        - Cột benh, ket_qua_xet_nghiem: GIỮ NGUYÊN (cần cho model training)
        - Cột patient_id: GIỮ NGUYÊN (pseudonym đã đủ an toàn)
        """
        df_anon = df.copy()

        for col in ("ho_ten", "dia_chi", "email"):
            if col in df_anon.columns:
                df_anon[col] = df_anon[col].astype(str).apply(
                    lambda v: self.anonymize_text(v, strategy="replace")
                )

        if "cccd" in df_anon.columns:
            df_anon["cccd"] = [_fake_cccd() for _ in range(len(df_anon))]

        if "so_dien_thoai" in df_anon.columns:
            df_anon["so_dien_thoai"] = [_fake_phone() for _ in range(len(df_anon))]

        if "bac_si_phu_trach" in df_anon.columns:
            df_anon["bac_si_phu_trach"] = df_anon["bac_si_phu_trach"].astype(str).apply(
                lambda v: self.anonymize_text(v, strategy="replace")
            )

        return df_anon

    def calculate_detection_rate(self,
                                  original_df: pd.DataFrame,
                                  pii_columns: list) -> float:
        """
        Tính % PII được detect thành công.
        Mục tiêu: > 95%

        Logic: với mỗi ô trong pii_columns,
               kiểm tra xem detect_pii() có tìm thấy ít nhất 1 entity không.
        """
        total = 0
        detected = 0

        for col in pii_columns:
            for value in original_df[col].astype(str):
                total += 1
                results = detect_pii(value, self.analyzer)
                if len(results) > 0:
                    detected += 1

        return detected / total if total > 0 else 0.0
