"""离线演示大脑（USE_MOCK_LLM=1 时启用）。

用途：没网 / 没 key / 答辩现场不想烧 token 时，用规则假大脑跑通
「说话 → 调工具 → 写数据库 → 看板刷新」的整条链路，界面行为与真实模式一致。
它操作的是同一个 TodoStore，所以和真实大模型效果等价。
"""
from __future__ import annotations

import re
from typing import Any

from .todo_store import PRIORITY_TO_TEXT, normalize_deadline


def _extract(title_text: str) -> tuple[str, str, str]:
    """从自然语言里抽 (标题, 优先级文本, 截止原文)。"""
    deadline = "无"
    for word in ("大后天", "后天", "明天", "今天"):
        if word in title_text:
            deadline = word
            break
    if deadline == "无":
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2})", title_text)
        if m:
            deadline = m.group(1)
    priority = "中"
    if any(w in title_text for w in ("紧急", "很急", "最急", "最高", "特急")):
        priority = "高"
    elif "不急" in title_text or "有空" in title_text:
        priority = "低"
    title = re.sub(r"(帮我|请|给我|提醒我|添加(一个)?任务|加(一个)?任务|记(一)?下|明天|后天|大后天|今天|，|,|。|紧急|很急|不急|吧|呀)",
                   "", title_text).strip(" ：:")
    return (title or title_text).strip(), priority, deadline


def answer(store: Any, text: str) -> tuple[str, list[dict]]:
    """返回 (回复文本, 工具轨迹)，格式与真实 Agent 一致。"""
    trace: list[dict] = []
    t = text.strip()

    # 导出
    if "导出" in t or "markdown" in t.lower():
        rows = [x for x in store.list_tasks() if x["status"] != "done"]
        md = "# 我的待办清单\n\n| 序号 | 任务 | 优先级 | 截止时间 |\n|---|---|---|---|\n"
        for i, r in enumerate(rows, 1):
            md += f"| {i} | {r['title']} | {r['priority_name']} | {r['deadline_text']} |\n"
        trace.append({"tool": "export_markdown", "args": {}, "result": f"已生成 {len(rows)} 行"})
        return ("已成功导出！内容预览：\n\n" + md, trace)

    # 删除
    m = re.search(r"(?:删除|删掉|去掉)\D*?(\d+)", t)
    if m:
        tid = int(m.group(1))
        ok = store.delete_task(tid)
        result = f"已成功删除第 {tid} 条待办事项。" if ok else f"操作失败：没有找到编号为 {tid} 的待办事项。"
        trace.append({"tool": "delete_todo", "args": {"id": tid}, "result": result})
        return (result, trace)

    # 完成
    m = re.search(r"(?:完成|做完了|搞定了|标为完成)\D*?(\d+)", t)
    if m:
        tid = int(m.group(1))
        task = store.complete_task(tid)
        result = (f"已将第 {tid} 条待办事项标记为完成。" if task
                  else f"操作失败：没有找到编号为 {tid} 的待办事项。")
        trace.append({"tool": "complete_todo", "args": {"id": tid}, "result": result})
        return (result, trace)

    # 明确的新增意图要优先于查询判断，否则「帮我记一个任务」会被当成查询
    if any(w in t for w in ("添加", "加个", "加一个", "加条", "记一个", "记一下", "记下",
                            "提醒我", "新增", "帮我加")):
        return _do_add(store, t)

    # 统计
    if any(w in t for w in ("统计", "多少", "几件", "几个")):
        s = store.stats()
        trace.append({"tool": "list_todos", "args": {"status": "all"}, "result": "（mock 读取）"})
        return (f"当前共 {s['total']} 条任务：待办 {s['pending']} 条、已完成 {s['done']} 条，"
                f"其中今日到期 {s['due_today']} 条、已逾期 {s['overdue']} 条。", trace)

    # 查询
    if any(w in t for w in ("列出", "有哪些", "看看", "清单", "安排", "今天干", "该干嘛")):
        tasks = store.list_tasks()
        if not tasks:
            trace.append({"tool": "list_todos", "args": {"status": "all"}, "result": "当前没有符合条件的待办。"})
            return ("当前没有符合条件的待办。", trace)
        lines = ["以下是查到的所有待办："]
        for i, r in enumerate(tasks, 1):
            icon = "✅" if r["status"] == "done" else "⬜"
            lines.append(f"{i}. {icon} {r['title']} | 优先级:{r['priority_name']} | "
                         f"耗时:{r['duration'] or '未知'} | 截止:{r['deadline_text'] or '无'} (内部ID:{r['id']})")
        trace.append({"tool": "list_todos", "args": {"status": "all"}, "result": "\n".join(lines)})
        return ("\n".join(lines), trace)

    return _do_add(store, t)


def _do_add(store: Any, t: str) -> tuple[str, list[dict]]:
    """落到队友 A 的 add_todo 语义：标题 + 推理出的优先级/截止时间。"""
    trace: list[dict] = []
    title, priority, deadline = _extract(t)
    created = store.add_todo(title=title, priority=priority, duration="未知", deadline=deadline)
    result = f"已添加待办：{title} [优先级:{priority}, 耗时:未知, 截止:{deadline}]"
    trace.append({"tool": "add_todo",
                  "args": {"title": title, "priority": priority, "deadline": deadline},
                  "result": result})
    due = normalize_deadline(deadline)
    tail = f"（截止 {due}）" if due else ""
    return (f"好的，已记下「{title}」（#{created['id']}）{tail}，"
            f"优先级 {PRIORITY_TO_TEXT.get(created['priority'], '中')}。", trace)
