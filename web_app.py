from __future__ import annotations

import argparse
import json
import mimetypes
import os
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agent.runtime import AgentRuntime
from app import build_runtime, load_dotenv
from memory.store import SessionStore


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "web"


@dataclass
class WebState:
    store: SessionStore
    trace_path: Path
    runtime: AgentRuntime | None = None
    runtime_error: str | None = None

    @property
    def ready(self) -> bool:
        return self.runtime is not None

    def recent_traces(
        self, user_id: str, session_id: str, limit: int = 30
    ) -> list[dict[str, Any]]:
        if not self.trace_path.exists():
            return []
        matched: deque[dict[str, Any]] = deque(maxlen=limit)
        with self.trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    record.get("user_id") == user_id
                    and record.get("session_id") == session_id
                ):
                    matched.append(record)
        return list(matched)


class AgentWebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: WebState):
        super().__init__(address, AgentWebHandler)
        self.state = state


class AgentWebHandler(BaseHTTPRequestHandler):
    server: AgentWebServer

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length 无效") from exc
        if length <= 0 or length > 1_000_000:
            raise ValueError("请求体为空或过大")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("请求体必须是 UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return payload

    @staticmethod
    def _required_text(payload: dict[str, Any], name: str, maximum: int = 200) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} 不能为空")
        value = value.strip()
        if len(value) > maximum:
            raise ValueError(f"{name} 不能超过 {maximum} 个字符")
        return value

    def _serve_static(self, route: str) -> bool:
        files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/style.css": "style.css",
        }
        filename = files.get(route)
        if filename is None:
            return False
        path = STATIC_ROOT / filename
        if not path.exists():
            self._send_json({"error": "界面资源不存在"}, HTTPStatus.NOT_FOUND)
            return True
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)
        return True

    @staticmethod
    def _public_message(row: dict[str, Any]) -> dict[str, Any]:
        content: Any = row["content"]
        if row["role"] == "tool":
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass
        return {
            "id": row["id"],
            "role": row["role"],
            "content": content,
            "tool_call_id": row.get("tool_call_id"),
            "tool_name": row.get("tool_name"),
            "created_at": row["created_at"],
        }

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if self._serve_static(parsed.path):
            return
        if parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "ready": self.server.state.ready,
                    "runtime_error": self.server.state.runtime_error,
                    "model": os.getenv("LLM_MODEL", "未配置"),
                    "tools": ["calculator", "search", "todo", "weather"],
                    "max_steps": 6,
                }
            )
            return
        if parsed.path == "/api/session":
            query = parse_qs(parsed.query)
            user_id = (query.get("user_id") or [""])[0].strip()
            session_id = (query.get("session_id") or [""])[0].strip()
            if not user_id or not session_id:
                self._send_json(
                    {"error": "user_id 和 session_id 不能为空"},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            messages = self.server.state.store.get_messages(user_id, session_id)
            todos = self.server.state.store.list_todos(user_id)
            traces = self.server.state.recent_traces(user_id, session_id)
            session = self.server.state.store.get_session(user_id, session_id)
            self._send_json(
                {
                    "session": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "summary": (session or {}).get("summary", ""),
                    },
                    "messages": [self._public_message(row) for row in messages],
                    "todos": todos,
                    "traces": traces,
                }
            )
            return
        self._send_json({"error": "页面不存在"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/chat":
                user_id = self._required_text(payload, "user_id")
                session_id = self._required_text(payload, "session_id")
                message = self._required_text(payload, "message", maximum=5000)
                if self.server.state.runtime is None:
                    self._send_json(
                        {
                            "error": self.server.state.runtime_error
                            or "真实 LLM 尚未配置，请检查 .env",
                        },
                        HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return
                answer = self.server.state.runtime.run(user_id, session_id, message)
                messages = self.server.state.store.get_messages(user_id, session_id)
                self._send_json(
                    {
                        "answer": answer,
                        "messages": [self._public_message(row) for row in messages],
                        "todos": self.server.state.store.list_todos(user_id),
                        "traces": self.server.state.recent_traces(user_id, session_id),
                    }
                )
                return
            if parsed.path == "/api/todos/complete":
                user_id = self._required_text(payload, "user_id")
                todo_id = payload.get("todo_id")
                if not isinstance(todo_id, int) or todo_id < 1:
                    raise ValueError("todo_id 必须是正整数")
                todo = self.server.state.store.complete_todo(user_id, todo_id)
                if todo is None:
                    self._send_json({"error": "待办不存在"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(
                    {"todo": todo, "todos": self.server.state.store.list_todos(user_id)}
                )
                return
            self._send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json(
                {"error": f"服务器处理失败: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def create_state(db_path: str, trace_path: str) -> WebState:
    load_dotenv()
    store = SessionStore(db_path)
    try:
        runtime = build_runtime(db_path=db_path, trace_path=trace_path)
        return WebState(store=store, trace_path=Path(trace_path), runtime=runtime)
    except (ValueError, OSError) as exc:
        return WebState(
            store=store,
            trace_path=Path(trace_path),
            runtime=None,
            runtime_error=str(exc),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Runtime 本地可视化界面")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", default=8765, type=int, help="监听端口")
    parser.add_argument("--db", default="data/agent.db", help="SQLite 数据库路径")
    parser.add_argument("--trace", default="logs/traces.jsonl", help="Trace 日志路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = create_state(args.db, args.trace)
    server = AgentWebServer((args.host, args.port), state)
    print(f"Agent Web 已启动：http://{args.host}:{args.port}")
    if not state.ready:
        print(f"提示：{state.runtime_error}")
        print("界面可以打开，但发送消息前需要在 .env 配置真实 LLM。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭 Agent Web...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
