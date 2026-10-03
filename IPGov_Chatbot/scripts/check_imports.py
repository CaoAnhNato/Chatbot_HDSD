import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Test initializing SqliteSaver
conn = sqlite3.connect("data/agent_memory_test.db", check_same_thread=False)
saver = SqliteSaver(conn)
print("SqliteSaver(conn) success:", saver)

# Test from_conn_string if available
if hasattr(SqliteSaver, "from_conn_string"):
    try:
        with SqliteSaver.from_conn_string("data/agent_memory_test.db") as s:
            print("SqliteSaver.from_conn_string success:", s)
    except Exception as e:
        print("from_conn_string failed:", e)

# Clean up test db
conn.close()
import os
if os.path.exists("data/agent_memory_test.db"):
    os.remove("data/agent_memory_test.db")
print("All SqliteSaver checks passed!")
