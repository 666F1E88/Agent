"""桥接运行时：把队友 A 的异步 Agent 包装成成员 B 的 UI 需要的 chat() 接口。

关键设计：
- 队友 A 的 run_agent 是 async，Streamlit 主线程里直接 asyncio.run 会与 Streamlit
  自己的事件循环打架（她原项目用 nest_asyncio 打补丁才能跑）。
  这里改为「独立后台线程 + 常驻事件循环 + run_coroutine_threadsafe」，
  不污染全局、不需要 nest_asyncio，也不会阻塞页面。
- 会话历史按 session_id 分开存，长度受 HISTORY_TURNS 限制。
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from .config import Config, apply_env
from .todo_store import TodoStore

apply_env()


class TodoRuntime:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or Config.DB_PATH
        self._store = TodoStore(self.db_path)
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._pump, name="todo-agent-loop", daemon=True)
        self._thread.start()

    # ---------------- 事件循环 ----------------
    def _pump(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro, timeout: int = 180):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    # ---------------- 对外接口（UI 只认这一个） ----------------
    def chat(self, text: str, session_id: str = "web") -> dict[str, Any]:
        if Config.USE_MOCK_LLM:
            from .mock_brain import answer

            reply, trace = answer(self._store, text)
            return {"answer": reply, "trace": trace}

        from core.todo_agent import arun_agent_traced

        history = self._histories.setdefault(session_id, [])
        snapshot = history[-Config.HISTORY_TURNS * 2:]
        try:
            reply, trace = self._run(arun_agent_traced(text, snapshot))
        except Exception as e:  # 网络/超时/模型异常都要转成可读提示，不能让页面炸
            return {"answer": f"❌ Agent 调用失败：{type(e).__name__}: {e}", "trace": []}

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        del history[:-Config.HISTORY_TURNS * 2]
        return {"answer": reply or "（模型没有返回内容）", "trace": trace}

    def reset(self, session_id: str = "web") -> None:
        self._histories[session_id] = []

    def close(self) -> None:
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        try:
            self._store.close()
        except Exception:
            pass
