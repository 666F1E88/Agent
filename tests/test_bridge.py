"""桥接层测试：验证「队友 A 的数据库」与「成员 B 的看板」能无缝对上。

不需要 API key、不联网，退出码 0 即通过。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge.mock_brain import answer  # noqa: E402
from bridge.todo_store import TodoStore, normalize_deadline  # noqa: E402
from ui.task_views import (  # noqa: E402
    completion_rate, filter_tasks, is_overdue, sort_tasks, to_csv, to_markdown,
)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append((name, bool(ok), extra))


def run() -> int:
    # ---------- 截止时间口语化归一 ----------
    check("「明天」翻成具体日期", bool(normalize_deadline("明天")), normalize_deadline("明天"))
    check("「后天」翻成具体日期", bool(normalize_deadline("后天")), normalize_deadline("后天"))
    check("「10-26」补全年份", normalize_deadline("10-26").endswith("-10-26"), normalize_deadline("10-26"))
    # 队友 A 的 Agent 实际产出的是「2026-10-26 23:59」这种带时刻的写法
    check("带时刻的截止也能归一", normalize_deadline("2026-10-26 23:59") == "2026-10-26",
          normalize_deadline("2026-10-26 23:59"))
    check("明天+时刻也能归一", bool(normalize_deadline("明天 15:00")), normalize_deadline("明天 15:00"))
    check("「无」不参与日期比较", normalize_deadline("无") == "", repr(normalize_deadline("无")))
    check("「下周吧」翻不出来也不乱来", normalize_deadline("下周吧") == "", repr(normalize_deadline("下周吧")))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = os.path.join(tmp, "todos.db")
        s = TodoStore(db)

        # 模拟队友 A 的 MCP 工具写入的数据（她的字段：priority 文本 / deadline 文本）
        s.add_todo("交智能体作业", "高", "2小时", "明天")
        s.add_todo("读论文", "中", "未知", "无")
        s.add_todo("买牛奶", "低", "10分钟", "2020-01-01")  # 造一条历史数据用于验证逾期

        tasks = s.list_tasks()
        check("看板能读到队友 A 写入的 3 条", len(tasks) == 3, str(len(tasks)))

        pri = {t["title"]: t["priority"] for t in tasks}
        check("文本优先级(高/中/低)映射为 1-4",
              pri["交智能体作业"] == 2 and pri["读论文"] == 3 and pri["买牛奶"] == 4, str(pri))

        due = {t["title"]: t["due_date"] for t in tasks}
        check("口语化截止(明天)被翻成日期", bool(due["交智能体作业"]), str(due))
        check("『无』不产生假日期", due["读论文"] == "", str(due))
        check("逾期任务能被识别", any(is_overdue(t) for t in tasks), str(due))

        # ---------- 看板按钮写回她表 ----------
        s.complete_task(1)
        check("点『完成』写回 done=1", s.get_task(1)["status"] == "done")
        s.update_task(1, status="pending")
        check("点『重开』写回 done=0", s.get_task(1)["status"] == "pending")
        s.delete_task(3)
        check("点『删除』真删掉", s.get_task(3) is None)

        st = s.stats()
        check("stats 字段齐全", {"total", "done", "pending", "due_today", "overdue"} <= set(st), str(st))
        check("完成率可计算", 0.0 <= completion_rate(st) <= 1.0, str(completion_rate(st)))

        # ---------- 离线大脑（无 key 也能跑通全链路） ----------
        reply, trace = answer(s, "帮我记一个任务：后天交物理作业，很急")
        check("离线大脑能加任务", len(s.list_tasks()) == 3, str(len(s.list_tasks())))
        check("离线大脑产生 add_todo 轨迹",
              bool(trace) and trace[0]["tool"] == "add_todo", str(trace))
        check("离线大脑回复非空", bool(reply.strip()), reply[:40])

        reply2, trace2 = answer(s, "我有哪些任务？")
        check("离线大脑能列任务", "以下是" in reply2 or "当前没有" in reply2, reply2[:40])
        check("离线列任务也有轨迹", any(t["tool"] == "list_todos" for t in trace2), str(trace2))

        reply3, _ = answer(s, "完成第 1 条")
        check("离线大脑能完成指定任务", "完成" in reply3, reply3[:40])

        # ---------- 视图层 ----------
        all_tasks = s.list_tasks()
        md = to_markdown(all_tasks)
        csv_text = to_csv(all_tasks)
        check("导出 Markdown 含标题", "交智能体作业" in md, md[:60])
        check("导出 CSV 含耗时列", "耗时" in csv_text, csv_text.splitlines()[0])
        check("筛选可用", isinstance(filter_tasks(all_tasks, "待办", ""), list))
        check("排序可用", len(sort_tasks(all_tasks, "智能排序")) == len(all_tasks))

        # ---------- 跨线程回归 ----------
        # Streamlit 用 @st.cache_resource 复用同一个 TodoStore，但每次 rerun 在不同线程，
        # 曾经因 sqlite 默认 check_same_thread=True 抛 ProgrammingError（看板加载失败）。
        errs: list[str] = []

        def _use_store_in_another_thread() -> None:
            try:
                s.add_todo("跨线程任务", "中", "未知", "无")
                _ = s.list_tasks()
                _ = s.stats()
            except Exception as e:  # noqa: BLE001
                errs.append(f"{type(e).__name__}: {e}")

        th = threading.Thread(target=_use_store_in_another_thread)
        th.start()
        th.join()
        check("SQLite 连接可跨线程使用（看板线程报错回归）", not errs, "; ".join(errs))
        s.close()

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, extra in results:
        print(f"{'  PASS' if ok else '  FAIL'}  {name}" + (f"  -> {extra}" if extra and not ok else ""))
    print(f"\n桥接层测试：{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())
