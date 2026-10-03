import psycopg2
import sys

conn_params = {
    "host": "104.248.155.6",
    "port": 5432,
    "dbname": "vna_wom_dev",
    "user": "vna_wom_dev",
    "password": "1d4ed4dd-d5df-4081-809f-884b7ca16cbd",
    "connect_timeout": 5
}

print("Connecting to PostgreSQL 104.248.155.6:5432/vna_wom_dev...")
try:
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    print("Connection successful!")

    tables = [
        "fact_report_criteria",
        "criteria",
        "report",
        "collection_form",
        "user_mission",
        '"user"',
        "office_mission",
        "mission",
        "deparment"
    ]

    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM dwh_internal.{t};")
            cnt = cur.fetchone()[0]
            print(f"Table dwh_internal.{t}: {cnt} rows")
        except Exception as e:
            print(f"Table dwh_internal.{t} error:", e)
            conn.rollback()

    # Check fact_report_criteria sample
    cur.execute("SELECT year_code, tenant_code, department_code, COUNT(*) FROM dwh_internal.fact_report_criteria GROUP BY year_code, tenant_code, department_code LIMIT 5;")
    for r in cur.fetchall():
        print(f"Fact breakdown: year_code={r[0]}, tenant={r[1]}, dept={r[2]}, count={r[3]}")

    cur.close()
    conn.close()
    print("DB checks finished successfully.")
except Exception as e:
    print("DB connection failed:", e)
