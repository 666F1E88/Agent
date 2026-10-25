"""合并项目一键回归：静态检查 + 桥接层测试。

用法：python tests/run_all.py   （不需要 API key，退出码 0 = 全绿）
"""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEY_FILES = [
    "README.md", "requirements.txt", ".env.example", ".gitignore", "run.ps1", "main.py",
    "core/todo_agent.py", "core/todo_mcp_server.py",
    "bridge/config.py", "bridge/todo_store.py", "bridge/todo_runtime.py", "bridge/mock_brain.py",
    "ui/app.py", "ui/task_views.py", "ui/voice.py",
    "scripts/fetch_asr_model.py", "models/README.md",
]

PY_FILES = [
    "core/todo_agent.py", "core/todo_mcp_server.py", "main.py",
    "bridge/config.py", "bridge/todo_store.py", "bridge/todo_runtime.py", "bridge/mock_brain.py",
    "ui/app.py", "ui/task_views.py", "ui/voice.py",
    "scripts/fetch_asr_model.py", "tests/test_bridge.py",
]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append((name, bool(ok), extra))


def main() -> int:
    print("=== 静态检查 ===")
    missing = [f for f in KEY_FILES if not (ROOT / f).exists()]
    check(f"{len(KEY_FILES)} 个关键文件齐全", not missing, "缺：" + "、".join(missing))

    bad = []
    for f in PY_FILES:
        try:
            py_compile.compile(str(ROOT / f), doraise=True)
        except Exception as e:
            bad.append(f"{f}: {e}")
    check(f"{len(PY_FILES)} 个 Python 文件语法通过", not bad, "; ".join(bad))

    # 队友 A 的 6 个 MCP 工具必须都在，一个都不能少
    srv = (ROOT / "core" / "todo_mcp_server.py").read_text(encoding="utf-8")
    tools = ["add_todo", "list_todos", "complete_todo", "delete_todo", "export_markdown", "save_memory"]
    check("队友 A 的 6 个 MCP 工具全部保留", all(f"def {t}(" in srv for t in tools),
          "缺：" + "、".join(t for t in tools if f"def {t}(" not in srv))

    # 兼容性修复点不能被回退
    check("MCP 导入已改为 fastmcp（原 mcpserver 模块不存在）",
          "from mcp.server.fastmcp import FastMCP" in srv
          and "from mcp.server.mcpserver import" not in srv)
    agent_src = (ROOT / "core" / "todo_agent.py").read_text(encoding="utf-8")
    check("保留了 DSML 乱码拦截逻辑", "DSML" in agent_src and "系统自动修复" in agent_src)
    check("保留了二段式总结（list/export）", 'in ["list_todos", "export_markdown"]' in agent_src)
    check("保留了用户档案注入", "【用户档案】" in agent_src)

    # 界面也要在
    ui_src = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    check("界面保留成员 B 的看板与语音", "render_board" in ui_src and "voice_rec" in ui_src)
    check("界面接的是桥接层而非原后端", "from bridge." in ui_src and "from agent.config" not in ui_src)
    check("界面保留队友 A 的导出下载按钮", "下载 Markdown 文件" in ui_src)

    # 看板线程报错回归：连接必须允许跨线程 + 读写加锁
    store_src = (ROOT / "bridge" / "todo_store.py").read_text(encoding="utf-8")
    check("SQLite 连接允许跨线程且加了锁（看板线程报错回归）",
          "check_same_thread=False" in store_src and "threading.Lock" in store_src)

    # 敏感文件
    check(".env 不会进仓库（.gitignore 已覆盖）",
          ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8"))

    static_pass = sum(1 for _, ok, _ in results if ok)
    for name, ok, extra in results:
        print(f"{'  PASS' if ok else '  FAIL'}  {name}" + (f"  -> {extra}" if extra and not ok else ""))
    print(f"静态检查：{static_pass}/{len(results)} 通过\n")

    print("=== 桥接层测试 ===")
    from tests.test_bridge import run as run_bridge

    bridge_code = run_bridge()

    print(f"\n合计：静态 {static_pass}/{len(results)} · 桥接层 {'全过' if bridge_code == 0 else '有失败'}")
    return 0 if (static_pass == len(results) and bridge_code == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
