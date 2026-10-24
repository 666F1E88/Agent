import sqlite3
from mcp.server.mcpserver import MCPServer

DB_PATH = "todos.db"
mcp = MCPServer("todo-assistant")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

@mcp.tool()
def add_todo(title: str) -> str:
    """添加一条待办事项。title 是任务标题，必填。"""
    conn = get_conn()
    conn.execute("INSERT INTO todos (title) VALUES (?)", (title,))
    conn.commit()
    return f"已添加待办：{title}"

@mcp.tool()
def list_todos(status: str = "all") -> str:
    """列出待办事项。status 可选 all / pending / done。"""
    sql = "SELECT id, title, done FROM todos"
    if status == "pending":
        sql += " WHERE done = 0"
    elif status == "done":
        sql += " WHERE done = 1"
    rows = get_conn().execute(sql).fetchall()
    if not rows:
        return "当前没有符合条件的待办。"
    return "\n".join(f"{'✅' if d else '⬜'} [{i}] {t}" for i, t, d in rows)

@mcp.tool()
def complete_todo(todo_id: int) -> str:
    """将指定 id 的待办标记为已完成。"""
    conn = get_conn()
    conn.execute("UPDATE todos SET done = 1 WHERE id = ?", (todo_id,))
    conn.commit()
    return f"已将第 {todo_id} 条标记为完成。"

@mcp.tool()
def delete_todo(todo_id: int) -> str:
    """删除指定 id 的待办事项。"""
    conn = get_conn()
    conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    return f"已删除第 {todo_id} 条待办。"

if __name__ == "__main__":
    mcp.run()
