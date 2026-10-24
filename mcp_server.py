import sqlite3
import json
import os
from mcp.server.mcpserver import MCPServer

DB_PATH = "todos.db"
MEMORY_PATH = "user_memory.json"
mcp = MCPServer("todo-assistant")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            priority TEXT DEFAULT '中',
            duration TEXT DEFAULT '未知',
            deadline TEXT DEFAULT '无',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

@mcp.tool()
def add_todo(title: str, priority: str = "中", duration: str = "未知", deadline: str = "无") -> str:
    """添加待办事项，自动填入优先级、耗时、截止时间。"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO todos (title, priority, duration, deadline) VALUES (?, ?, ?, ?)", 
        (title, priority, duration, deadline)
    )
    conn.commit()
    return f"已添加待办：{title} [优先级:{priority}, 耗时:{duration}, 截止:{deadline}]"

@mcp.tool()
def list_todos(status: str = "all") -> str:
    """列出待办事项。status 可选 all / pending / done。"""
    sql = "SELECT id, title, done, priority, duration, deadline FROM todos"
    if status == "pending":
        sql += " WHERE done = 0"
    elif status == "done":
        sql += " WHERE done = 1"
    
    # 核心排序逻辑：
    # 把deadline为'无'的排到最后
    # 按截止时间升序
    # 如果时间一样，按优先级高->中->低排序
    sql += """ 
        ORDER BY 
            CASE WHEN deadline = '无' THEN 1 ELSE 0 END ASC,
            deadline ASC,
            CASE priority WHEN '高' THEN 1 WHEN '中' THEN 2 WHEN '低' THEN 3 ELSE 4 END ASC
    """
    
    rows = get_conn().execute(sql).fetchall()
    if not rows:
        return "当前没有符合条件的待办。"
    
    result = ["以下是查到的所有待办（请全部原样展示给用户，千万不要遗漏）："]
    for index, r in enumerate(rows, start=1):
        icon = "✅" if r[2] else "⬜"
        result.append(f"{index}. {icon} {r[1]} | 优先级:{r[3]} | 耗时:{r[4]} | 截止:{r[5]} (内部ID:{r[0]})")
    return "\n".join(result)

@mcp.tool()
def complete_todo(id: int) -> str:
    """将指定 id 的待办标记为已完成。"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET done = 1 WHERE id = ?", (id,))
    conn.commit()
    if cursor.rowcount == 0:
        return f"操作失败：没有找到编号为 {id} 的待办事项。"
    return f"已将第 {id} 条待办事项标记为完成。"

@mcp.tool()
def delete_todo(id: int) -> str:
    """删除指定 id 的待办事项。"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (id,))
    conn.commit()
    if cursor.rowcount == 0:
        return f"操作失败：没有找到编号为 {id} 的待办事项。"
    return f"已成功删除第 {id} 条待办事项。"

@mcp.tool()
def export_markdown() -> str:
    """一键将当前所有未完成的待办导出为真实的 Markdown 文件。"""
    # 导出应用同样的排序规则
    sql = """
        SELECT id, title, priority, deadline FROM todos 
        WHERE done = 0 
        ORDER BY 
            CASE WHEN deadline = '无' THEN 1 ELSE 0 END ASC,
            deadline ASC,
            CASE priority WHEN '高' THEN 1 WHEN '中' THEN 2 WHEN '低' THEN 3 ELSE 4 END ASC
    """
    rows = get_conn().execute(sql).fetchall()
    if not rows:
        return "目前没有未完成的任务，不需要导出。"
    
    md = "# 我的待办清单\n\n"
    md += "| 序号 | 任务 | 优先级 | 截止时间 |\n|---|---|---|---|\n"
    
    for index, r in enumerate(rows, start=1):
        md += f"| {index} | {r[1]} | {r[2]} | {r[3]} |\n"
    
    filename = "todo_export.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)
        
    return f"已成功导出！文件已保存为 `{filename}`。内容预览：\n\n{md}"

@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """保存用户的长期习惯或称呼。"""
    data = {}
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            try: data = json.load(f)
            except: pass
    data[key] = value
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return f"已永久记住：{key} 是 {value}"

if __name__ == "__main__":
    mcp.run()
