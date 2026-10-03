"""
Script: IPGov_Chatbot/scripts/restore_render_postgres.py
Chức năng: Nạp cấu trúc và dữ liệu kho DWH từ file SQL dump (vna_wom_dev_test.sql)
lên cơ sở dữ liệu Render PostgreSQL (External Database URL).

Cách dùng:
    python IPGov_Chatbot/scripts/restore_render_postgres.py --url "postgresql://vna_wom_dev:password@host.oregon-postgres.render.com/vna_wom_dev"
hoặc nếu đã set biến môi trường RENDER_EXTERNAL_DB_URL:
    python IPGov_Chatbot/scripts/restore_render_postgres.py
"""

import os
import sys
import argparse
import time
from pathlib import Path

# Thư mục gốc project
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
SQL_DUMP_FILE = WORKSPACE_DIR / "data" / "warehouse" / "vna_wom_dev_test.sql"

def restore_database(db_url: str):
    print("=" * 70)
    print("🚀 BẮT ĐẦU RESTORE KHO DỮ LIỆU DWH LÊN RENDER POSTGRESQL")
    print(f"📁 Tệp nguồn SQL: {SQL_DUMP_FILE}")
    print(f"🌐 Target URL: {db_url.split('@')[-1] if '@' in db_url else '***'}")
    print("=" * 70)

    if not SQL_DUMP_FILE.exists():
        print(f"❌ Không tìm thấy tệp {SQL_DUMP_FILE}!")
        sys.exit(1)

    import psycopg2

    # Clean URL format for psycopg2 (nếu có tiền tố postgresql+asyncpg:// thì sửa thành postgresql://)
    clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print("🔌 Đang kết nối tới PostgreSQL trên Render...")
    try:
        conn = psycopg2.connect(clean_url, sslmode="require")
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Kết nối PostgreSQL thành công!")
    except Exception as e:
        print(f"❌ Lỗi kết nối CSDL: {e}")
        sys.exit(1)

    print("📖 Đang đọc tệp SQL dump (65MB)...")
    t0 = time.time()
    with open(SQL_DUMP_FILE, "r", encoding="utf-8", errors="ignore") as f:
        sql_content = f.read()

    print(f"⚡ Đã nạp xong nội dung file SQL trong {time.time() - t0:.2f}s. Đang thực thi trên Render...")

    t1 = time.time()
    try:
        cursor.execute(sql_content)
        print(f"✅ Hoàn tất thực thi SQL dump trên Render trong {time.time() - t1:.2f}s!")
    except Exception as e:
        print(f"⚠️ Có lỗi trong quá trình thực thi: {e}")
    finally:
        cursor.close()
        conn.close()

    print("=" * 70)
    print("🎉 QUÁ TRÌNH KHỞI TẠO CSDL TRÊN RENDER HOÀN TẤT!")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore DWH to Render Postgres")
    parser.add_argument("--url", type=str, default=os.getenv("RENDER_EXTERNAL_DB_URL") or os.getenv("DWH_DATABASE_URL"), help="External Database Connection URL from Render")
    args = parser.parse_args()

    if not args.url:
        print("⚠️ Vui lòng cung cấp URL kết nối qua tham số --url hoặc set biến RENDER_EXTERNAL_DB_URL")
        print("Ví dụ:")
        print('  python IPGov_Chatbot/scripts/restore_render_postgres.py --url "postgresql://user:pass@host.oregon-postgres.render.com/dbname"')
        sys.exit(1)

    restore_database(args.url)
