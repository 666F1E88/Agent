"""桥接存储层：让成员 B 的看板界面，直接读写队友 A 的 todos.db。

队友 A 的表结构（保持不动）：
    todos(id, title, done, priority[文本:高/中/低], duration, deadline[文本], created_at)

看板需要的字段：
    id, title, priority[int 1紧急/2高/3中/4低], status[pending/doing/done],
    due_date[YYYY-MM-DD], tags, description, created_at, updated_at

这里做双向翻译：读出来时把文本优先级/完成标记/截止时间翻成看板字段；
点按钮时再翻回她表的写法。**两边操作的是同一行数据，永远不会不同步。**
"""
from __future__ import annotations

import re
import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    priority TEXT DEFAULT '中',
    duration TEXT DEFAULT '未知',
    deadline TEXT DEFAULT '无',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# 队友 A 的文本优先级 → 看板用的数字优先级
TEXT_TO_PRIORITY = {"紧急": 1, "高": 2, "中": 3, "低": 4}
PRIORITY_TO_TEXT = {1: "紧急", 2: "高", 3: "中", 4: "低"}

_WEEKDAY = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6, "周天": 6}


def normalize_deadline(text: str, today: str | None = None) -> str:
    """把「明天 / 10-26 / 2026-10-26 / 周五」等口语化截止，翻成 YYYY-MM-DD。

    翻不出来的（如「下周吧」「无」「未知」）返回空串——看板的逾期判定只认规范日期，
    避免字符串比较把「无」当成时间导致误判。
    """
    s = (text or "").strip()
    if not s or s in ("无", "未知", "待定", "-"):
        return ""
    today_d = date.fromisoformat(today) if today else date.today()

    # 队友 A 的 Agent 常产出「2026-10-26 23:59」这种带时刻的截止，
    # 所以这里用 match 而不是 fullmatch：认开头的日期部分，后面的时间忽略。
    m1 = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]\d{1,2}:\d{2})?", s)
    m2 = re.match(r"\s*(\d{1,2})-(\d{1,2})(?:[ T]\d{1,2}:\d{2})?", s)
    m3 = re.match(r"\s*(\d{1,2})月(\d{1,2})[日号]", s)
    if m1:
        y, m, d = (int(x) for x in m1.groups())
    elif m2:
        m, d = (int(x) for x in m2.groups())
        y = today_d.year
    elif m3:
        m, d = (int(x) for x in m3.groups())
        y = today_d.year
    else:
        # 口语词后面可能跟着时刻/时段（如「明天 15:00」「后天下午三点」），用前缀匹配
        for word, days in (("大后天", 3), ("后天", 2), ("明天", 1), ("今天", 0)):
            if s.startswith(word):
                return (today_d + timedelta(days=days)).isoformat()
        for word, idx in _WEEKDAY.items():
            if s.startswith(word):
                delta = (idx - today_d.weekday()) % 7
                delta = 7 if delta == 0 else delta
                return (today_d + timedelta(days=delta)).isoformat()
        return ""
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return ""


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    priority_text = (row["priority"] or "中").strip()
    priority = TEXT_TO_PRIORITY.get(priority_text, 3)
    done = int(row["done"] or 0)
    deadline_raw = (row["deadline"] or "").strip()
    duration = (row["duration"] or "").strip()

    return {
        "id": row["id"],
        "title": row["title"],
        "priority": priority,
        "priority_name": priority_text or "中",
        "status": "done" if done else "pending",
        "status_name": "已完成" if done else "待办",
        "due_date": normalize_deadline(deadline_raw),
        "deadline_text": deadline_raw,          # 原文，用于看板显示（可能是「明天」）
        "duration": duration,                    # 队友 A 独有的耗时字段
        "tags": [],
        # 耗时已有独立字段且界面会单独展示，这里不再重复拼进描述（避免「耗时xx」出现两次）
        "description": "",
        "created_at": row["created_at"],
        "updated_at": row["created_at"],
    }


class TodoStore:
    """针对队友 A 的 todos 表实现的看板数据接口。"""

    def __init__(self, db_path: str) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # Streamlit 的 @st.cache_resource 会在「同一个实例、不同 rerun 线程」里复用它，
        # 默认 check_same_thread=True 会抛 ProgrammingError（看板加载失败），
        # 所以这里允许跨线程，并用一把锁保证读写互斥。
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def _run(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """线程安全地执行一条 SQL。"""
        with self._lock:
            return self.conn.execute(sql, params)

    def _commit(self) -> None:
        with self._lock:
            self.conn.commit()

    # ---------------- 读 ----------------
    def get_task(self, task_id: int) -> dict[str, Any] | None:
        row = self._run("SELECT * FROM todos WHERE id=?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def list_tasks(self, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._run(
            "SELECT * FROM todos ORDER BY done ASC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_task(r) for r in rows]

    def stats(self) -> dict[str, int]:
        today = date.today().isoformat()
        total = self._run("SELECT COUNT(*) c FROM todos").fetchone()["c"]
        done = self._run("SELECT COUNT(*) c FROM todos WHERE done=1").fetchone()["c"]
        tasks = [_row_to_task(r) for r in self._run("SELECT * FROM todos").fetchall()]
        due_today = sum(1 for t in tasks if t["due_date"] == today and t["status"] != "done")
        overdue = sum(1 for t in tasks if t["due_date"] and t["due_date"] < today and t["status"] != "done")
        return {
            "total": total,
            "done": done,
            "pending": total - done,
            "doing": 0,
            "due_today": due_today,
            "overdue": overdue,
        }

    # ---------------- 写（全部映射回队友 A 的字段） ----------------
    def add_todo(self, title: str, priority: str = "中", duration: str = "未知",
                 deadline: str = "无") -> dict[str, Any]:
        cur = self._run(
            "INSERT INTO todos(title, priority, duration, deadline) VALUES (?,?,?,?)",
            (title, priority, duration, deadline),
        )
        new_id = cur.lastrowid
        self._commit()
        return self.get_task(new_id)

    def complete_task(self, task_id: int) -> dict[str, Any] | None:
        self._run("UPDATE todos SET done=1 WHERE id=?", (task_id,))
        self._commit()
        return self.get_task(task_id)

    def update_task(self, task_id: int, status: str | None = None, **kwargs: Any) -> dict[str, Any] | None:
        if status is not None:
            self._run("UPDATE todos SET done=? WHERE id=?",
                      (1 if status == "done" else 0, task_id))
        # 兼容看板可能传入的数字优先级
        if "priority" in kwargs:
            p = kwargs["priority"]
            text = p if isinstance(p, str) else PRIORITY_TO_TEXT.get(int(p), "中")
            self._run("UPDATE todos SET priority=? WHERE id=?", (text, task_id))
        if "title" in kwargs:
            self._run("UPDATE todos SET title=? WHERE id=?", (kwargs["title"], task_id))
        self._commit()
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        cur = self._run("DELETE FROM todos WHERE id=?", (task_id,))
        n = cur.rowcount
        self._commit()
        return n > 0

    def clear(self) -> None:
        self._run("DELETE FROM todos")
        self._commit()

    def close(self) -> None:
        self.conn.close()
