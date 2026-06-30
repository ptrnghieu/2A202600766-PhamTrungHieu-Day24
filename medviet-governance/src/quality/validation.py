# src/quality/validation.py
import re
import pandas as pd
import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite

EMAIL_REGEX = r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$"


def build_patient_expectation_suite() -> ExpectationSuite:
    """
    Tạo expectation suite cho anonymized patient data.
    """
    context = gx.get_context()
    suite = context.add_expectation_suite("patient_data_suite")

    # Lấy validator
    df = pd.read_csv("data/raw/patients_raw.csv")
    validator = context.sources.pandas_default.read_dataframe(df)

    # --- Expectations ---

    # 1. patient_id không được null
    validator.expect_column_values_to_not_be_null("patient_id")

    # 2. cccd phải có đúng 12 ký tự
    validator.expect_column_value_lengths_to_equal(
        column="cccd",
        value=12
    )

    # 3. ket_qua_xet_nghiem phải trong khoảng [0, 50]
    validator.expect_column_values_to_be_between(
        column="ket_qua_xet_nghiem",
        min_value=0,
        max_value=50
    )

    # 4. benh phải thuộc danh sách hợp lệ
    valid_conditions = ["Tiểu đường", "Huyết áp cao", "Tim mạch", "Khỏe mạnh"]
    validator.expect_column_values_to_be_in_set(
        column="benh",
        value_set=valid_conditions
    )

    # 5. email phải match regex pattern
    validator.expect_column_values_to_match_regex(
        column="email",
        regex=EMAIL_REGEX
    )

    # 6. Không được có duplicate patient_id
    validator.expect_column_values_to_be_unique(column="patient_id")

    validator.save_expectation_suite()
    return suite


def validate_anonymized_data(filepath: str, original_row_count: int = None) -> dict:
    """
    Validate anonymized data.
    Trả về dict: {"success": bool, "failed_checks": list, "stats": dict}
    """
    df = pd.read_csv(filepath)
    results = {
        "success": True,
        "failed_checks": [],
        "stats": {
            "total_rows": len(df),
            "columns": list(df.columns)
        }
    }

    # Check 1: Không còn CCCD gốc dạng số thuần túy 12 chữ số đứng riêng lẻ
    # mà không khớp định dạng fake/masked/hashed mong đợi.
    if "cccd" in df.columns:
        invalid_cccd = df[~df["cccd"].astype(str).str.match(r"^\d{12}$")]
        if not invalid_cccd.empty:
            results["success"] = False
            results["failed_checks"].append(
                f"{len(invalid_cccd)} row(s) có cccd không đúng định dạng 12 chữ số"
            )

    # Check 2: Không có null values trong các cột quan trọng
    important_cols = [c for c in ("patient_id", "benh", "ket_qua_xet_nghiem") if c in df.columns]
    for col in important_cols:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            results["success"] = False
            results["failed_checks"].append(f"Cột '{col}' có {null_count} giá trị null")

    # Check 3: Số rows phải bằng original (nếu được cung cấp)
    if original_row_count is not None and len(df) != original_row_count:
        results["success"] = False
        results["failed_checks"].append(
            f"Số rows ({len(df)}) khác với original ({original_row_count})"
        )

    return results
