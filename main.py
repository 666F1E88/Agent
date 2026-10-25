"""命令行入口：与网页共用队友 A 的 Agent 和同一个数据库。

用法：python main.py   （输入 /quit 退出）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bridge.config import Config, check_config  # noqa: E402
from bridge.todo_runtime import TodoRuntime  # noqa: E402


def main() -> int:
    problems = check_config()
    if problems:
        print("⚠️  " + "；".join(problems))
        if not Config.USE_MOCK_LLM:
            print("提示：复制 .env.example 为 .env 填入 DEEPSEEK_API_KEY，或设置 USE_MOCK_LLM=1 用离线大脑。")
            return 1

    rt = TodoRuntime(Config.DB_PATH)
    mode = "离线演示（规则大脑）" if Config.USE_MOCK_LLM else f"真实大模型 · {Config.MODEL}"
    print(f"✅ TaskMate Duo 命令行版｜{mode}｜数据库 {Path(Config.DB_PATH).name}")
    print("   试试：帮我记一个任务：明天交智能体作业，很急 / 我今天该干嘛？ / 导出我的待办")
    print("   输入 /quit 退出\n")

    try:
        while True:
            try:
                text = input("你> ").strip()
            except EOFError:
                break
            if text.lower() in ("/quit", "/exit", "quit", "exit"):
                break
            if not text:
                continue
            out = rt.chat(text, session_id="cli")
            print(f"助理> {out['answer']}")
            for t in out["trace"]:
                print(f"   🔧 {t['tool']}({t['args']})")
    finally:
        rt.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
