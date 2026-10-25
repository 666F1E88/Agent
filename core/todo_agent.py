"""队友 A 的 Agent 大脑（原 agent.py），对话与工具调用逻辑 100% 保留。

合入 together program 时做了 4 处「非功能性」修改，业务行为一致：
1. OpenAI 客户端改为懒加载：原写法在 import 时若没有 DEEPSEEK_API_KEY 会直接抛错，
   导致 Streamlit 首屏白屏；现在只在真正第一次对话时才创建。
2. 新增 `arun_agent_traced()`：与 `run_agent()` 走完全相同的逻辑，
   额外把「调用了哪些工具 / 参数 / 返回」收集成 trace，供新 UI 的「🔧 执行轨迹」展示。
   原来的 `run_agent()` 签名与返回值不变，队友的调用方式依旧可用。
3. MCP Server 脚本改为绝对路径 + 显式传 TODO_DB_PATH / TODO_MEMORY_PATH，
   解决「子进程工作目录不同 → 数据写到别处 → 看板看不到」的隐患。
4. base_url 可用 DEEPSEEK_BASE_URL 覆盖（默认仍是 api.deepseek.com）。

保留的原有特性：
- 真实时间注入 + 用户档案（user_memory.json）注入
- DeepSeek 工具调用、list_todos/export_markdown 的二段式总结
- 对 DSML 乱码的「暴力拦截 + 自动修复」（这是队友针对 DeepSeek 输出特点做的容错）
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = str(ROOT / "core" / "todo_mcp_server.py")
MEMORY_FILE = os.environ.get("TODO_MEMORY_PATH") or str(ROOT / "data" / "user_memory.json")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

_client = None


def get_client():
    """懒加载 AsyncOpenAI：没有 key 时不 import 就崩，缺 key 的提示交给 UI 层处理。"""
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url=BASE_URL)
    return _client


def _load_memory_text() -> str:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                mem = json.load(f)
                return f"【用户档案】{json.dumps(mem, ensure_ascii=False)}。"
            except Exception:
                pass
    return ""


def _build_system_prompt() -> str:
    memory_text = _load_memory_text()
    now = datetime.datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %H:%M:%S")

    return f"""你是一个极其专业的智能日程与待办管理助理。
当前真实时间是：{time_str}。请严格以此时间为基准计算“今天”、“明天”。
{memory_text}

【核心能力要求】
1. 自动化任务：添加任务时自动推理填入 priority(高/中/低)、duration(耗时)、deadline(截止时间)。
2. 日程规划：用户说“安排今天”时，先调 list_todos 查询，再结合当前真实时间和优先级，排出一个合理的时间表。
3. 记忆功能：如果用户告诉你称呼/习惯，请调用 save_memory。
4. 导出功能：调用 export_markdown 导出文件。
5. 严禁输出任何底层 XML/DSML 乱码。"""


async def _call_with_garbled_fix(session, msg, trace_sink: list[dict] | None) -> str:
    """队友 A 原有的「乱码暴力拦截」逻辑，原样保留 + 记录 trace。"""
    if not (msg.content and ("DSML" in msg.content or "invoke" in msg.content or "<|" in msg.content)):
        return ""

    # 暴力抓取乱码里的所有数字
    numbers = re.findall(r"\d+", msg.content)

    if "delete_todo" in msg.content and numbers:
        # 通常参数里的ID在最后面，取最后一个数字作为ID
        todo_id = int(numbers[-1])
        result = await session.call_tool("delete_todo", {"id": todo_id})
        if trace_sink is not None:
            trace_sink.append({"tool": "delete_todo", "args": {"id": todo_id},
                               "result": result.content[0].text})
        return f"（系统自动修复）{result.content[0].text}"

    if "complete_todo" in msg.content and numbers:
        todo_id = int(numbers[-1])
        result = await session.call_tool("complete_todo", {"id": todo_id})
        if trace_sink is not None:
            trace_sink.append({"tool": "complete_todo", "args": {"id": todo_id},
                               "result": result.content[0].text})
        return f"（系统自动修复）{result.content[0].text}"

    return "抱歉，系统拦截到未知乱码格式，请重新下达指令。"


async def arun_agent_traced(user_input: str, history: list[dict]) -> tuple[str, list[dict[str, Any]]]:
    """跑一轮对话，返回 (回复文本, 工具调用轨迹)。逻辑与队友原 run_agent 一致。"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    trace_sink: list[dict[str, Any]] = []
    env = dict(os.environ)
    env.setdefault("TODO_DB_PATH", str(ROOT / "data" / "todos.db"))
    env.setdefault("TODO_MEMORY_PATH", MEMORY_FILE)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=env,
    )

    def _result_text(result) -> str:
        try:
            return result.content[0].text
        except Exception:
            return ""

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tools_schema = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    # 兼容性：mcp 新版把字段改成了 inputSchema（驼峰），旧版是 input_schema。
                    # 两种都取，取不到再退化成空 schema，保证任何版本都不会在这里炸。
                    "parameters": (getattr(t, "inputSchema", None)
                                   or getattr(t, "input_schema", None)
                                   or {"type": "object", "properties": {}}),
                },
            } for t in tools.tools]

            messages = [{"role": "system", "content": _build_system_prompt()}] + list(history) + [
                {"role": "user", "content": user_input}
            ]

            resp = await get_client().chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools_schema,
                temperature=0.1
            )
            msg = resp.choices[0].message

            # 正常工具调用
            if msg.tool_calls:
                reply_text = ""
                for call in msg.tool_calls:
                    args = json.loads(call.function.arguments)
                    result = await session.call_tool(call.function.name, args)
                    text = _result_text(result)
                    trace_sink.append({"tool": call.function.name, "args": args, "result": text})
                    reply_text += text + "\n"

                if any(call.function.name in ["list_todos", "export_markdown"] for call in msg.tool_calls):
                    messages.append(msg)
                    for call in msg.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": reply_text,
                        })
                    final = await get_client().chat.completions.create(model=MODEL, messages=messages)
                    return final.choices[0].message.content, trace_sink

                return reply_text.strip(), trace_sink

            # 暴力拦截，只要文本里有乱码，直接强制执行操作
            fixed = await _call_with_garbled_fix(session, msg, trace_sink)
            if fixed:
                return fixed, trace_sink

            return (msg.content if msg.content else "抱歉，我没有理解你的意思。"), trace_sink


async def run_agent(user_input: str, history: list[dict]) -> str:
    """队友 A 原始签名，行为不变（供她原来的 app.py 直接使用）。"""
    reply, _ = await arun_agent_traced(user_input, history)
    return reply
