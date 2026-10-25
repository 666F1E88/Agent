"""合并后的统一配置。

队友 A 的后端读 DEEPSEEK_API_KEY，成员 B 的 UI 读 LLM_API_KEY；
这里做一次「翻译」，两种写法都认，用户在 .env 里填任意一个都能跑。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _abs(p: str) -> str:
    return p if os.path.isabs(p) else str(ROOT / p)


class Config:
    # ---- 存储：MCP 工具与看板读写同一个库，这是两边能合并的前提 ----
    DB_PATH = _abs(_get("TODO_DB_PATH", "data/todos.db"))
    MEMORY_PATH = _abs(_get("TODO_MEMORY_PATH", "data/user_memory.json"))
    EXPORT_PATH = _abs(_get("TODO_EXPORT_PATH", "data/todo_export.md"))

    # ---- 大模型 ----
    API_KEY = _get("DEEPSEEK_API_KEY") or _get("LLM_API_KEY")
    BASE_URL = _get("LLM_BASE_URL") or _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    MODEL = _get("LLM_MODEL") or _get("DEEPSEEK_MODEL", "deepseek-chat")

    HISTORY_TURNS = int(_get("AGENT_HISTORY_TURNS", "20"))

    # 离线演示：没网络/没 key 时用规则大脑，整条链路照跑（老师当场演示很实用）
    USE_MOCK_LLM = _get("USE_MOCK_LLM", "0").strip().lower() in ("1", "true", "yes")

    SERVER_SCRIPT = str(ROOT / "core" / "todo_mcp_server.py")


def apply_env() -> None:
    """把统一配置写回环境变量，供队友 A 的原逻辑（读 DEEPSEEK_*）直接使用。"""
    os.environ["TODO_DB_PATH"] = Config.DB_PATH
    os.environ["TODO_MEMORY_PATH"] = Config.MEMORY_PATH
    if Config.API_KEY:
        os.environ.setdefault("DEEPSEEK_API_KEY", Config.API_KEY)
    if Config.BASE_URL:
        os.environ.setdefault("DEEPSEEK_BASE_URL", Config.BASE_URL)
    if Config.MODEL:
        os.environ.setdefault("DEEPSEEK_MODEL", Config.MODEL)


def check_config() -> list[str]:
    """启动前自检，返回问题列表（空列表 = 配置 OK）。"""
    problems: list[str] = []
    if Config.USE_MOCK_LLM:
        return problems
    if not Config.API_KEY:
        problems.append("未配置 API Key：复制 .env.example 为 .env，填 DEEPSEEK_API_KEY（或 LLM_API_KEY）")
    if not Path(Config.SERVER_SCRIPT).exists():
        problems.append(f"找不到 MCP Server 脚本：{Config.SERVER_SCRIPT}")
    return problems
