from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from agent.context import ContextBuilder
from agent.runtime import AgentRuntime
from llm.client import OpenAIChatClient
from memory.store import SessionStore
from tools import CalculatorTool, SearchTool, TodoTool, ToolRegistry, WeatherTool
from tracing.logger import TraceLogger


def configure_console_output() -> None:
    """Keep CLI output alive when a Windows console cannot encode model text."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_runtime(
    *,
    db_path: str = "data/agent.db",
    trace_path: str = "logs/traces.jsonl",
) -> AgentRuntime:
    load_dotenv()
    store = SessionStore(db_path)
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool(store))
    registry.register(WeatherTool())
    llm = OpenAIChatClient(
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
    )
    trace = TraceLogger(trace_path)
    return AgentRuntime(
        llm=llm,
        registry=registry,
        store=store,
        context_builder=ContextBuilder(store),
        trace=trace,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="最小可用 Agent Runtime CLI")
    parser.add_argument("--user", required=True, help="用户 ID，例如 user_a")
    parser.add_argument("--session", required=True, help="窗口/Session ID，例如 window_1")
    parser.add_argument("--message", help="只运行一条消息后退出")
    parser.add_argument("--db", default="data/agent.db", help="SQLite 数据库路径")
    parser.add_argument("--trace", default="logs/traces.jsonl", help="Trace JSONL 路径")
    return parser.parse_args()


def main() -> int:
    configure_console_output()
    args = parse_args()
    try:
        runtime = build_runtime(db_path=args.db, trace_path=args.trace)
    except (ValueError, OSError) as exc:
        print(f"启动失败：{exc}")
        print("请复制 .env.example 为 .env，并填写 LLM_API_KEY 与 LLM_MODEL。")
        return 2

    if args.message:
        print(runtime.run(args.user, args.session, args.message))
        return 0

    print(f"Agent 已启动：user={args.user}, session={args.session}")
    print("输入 exit 或 quit 结束。")
    while True:
        try:
            message = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if message.lower() in {"exit", "quit"}:
            print("再见。")
            break
        if not message:
            continue
        answer = runtime.run(args.user, args.session, message)
        print(f"Agent> {answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
