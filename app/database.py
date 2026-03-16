import os
import pandas as pd
from sqlalchemy import create_engine, text

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fresenius.db")
EXCEL_PATH = os.path.join(BASE_DIR, "data", "Fresenius Data.xlsx")

engine = create_engine(f"sqlite:///{DB_PATH}")


def setup_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Check if table already exists and has data
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='fresenius'")
            )
            if result.fetchone():
                print("✓ Database already set up, skipping...")
                return
    except Exception:
        pass

    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(
            f"Fresenius Data Excel file not found at: {EXCEL_PATH}\n"
            f"Expected at: {os.path.abspath(EXCEL_PATH)}"
        )

    df = pd.read_excel(EXCEL_PATH, sheet_name=0)
    df.to_sql("fresenius", engine, index=False)
    print(f"✓ Database created with {len(df)} patient records ({len(df.columns)} columns)")


def get_patient(patient_id: int) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM fresenius WHERE PT = :pid"), {"pid": patient_id}
        )
        columns = list(result.keys())
        rows = result.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def get_patient_count() -> int:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM fresenius"))
        return result.scalar()
