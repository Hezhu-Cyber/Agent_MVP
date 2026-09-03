const state = {
  userId: localStorage.getItem("agent.userId") || "user_a",
  sessionId: localStorage.getItem("agent.sessionId") || "window_1",
  sending: false,
};

const elements = {
  runtimeStatus: document.querySelector("#runtimeStatus"),
  runtimeStatusText: document.querySelector("#runtimeStatusText"),
  modelName: document.querySelector("#modelName"),
  userId: document.querySelector("#userId"),
  sessionId: document.querySelector("#sessionId"),
  loadSession: document.querySelector("#loadSession"),
  activeSessionLabel: document.querySelector("#activeSessionLabel"),
  messageCount: document.querySelector("#messageCount"),
  refreshSession: document.querySelector("#refreshSession"),
  messages: document.querySelector("#messages"),
  emptyState: document.querySelector("#emptyState"),
  chatScroll: document.querySelector("#chatScroll"),
  composer: document.querySelector("#composer"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  traceList: document.querySelector("#traceList"),
  todoList: document.querySelector("#todoList"),
  todoCount: document.querySelector("#todoCount"),
  toast: document.querySelector("#toast"),
};

elements.userId.value = state.userId;
elements.sessionId.value = state.sessionId;

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => elements.toast.classList.remove("is-visible"), 2800);
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({ error: "服务器返回了无效响应" }));
  if (!response.ok) {
    throw new Error(payload.error || `请求失败 (${response.status})`);
  }
  return payload;
}

function setIdentity() {
  const userId = elements.userId.value.trim();
  const sessionId = elements.sessionId.value.trim();
  if (!userId || !sessionId) {
    throw new Error("用户 ID 和 Session ID 不能为空");
  }
  state.userId = userId;
  state.sessionId = sessionId;
  localStorage.setItem("agent.userId", userId);
  localStorage.setItem("agent.sessionId", sessionId);
  elements.activeSessionLabel.textContent = `${userId} / ${sessionId}`;
  document.querySelectorAll("[data-session]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.session === sessionId);
  });
}

function messageTime(timestamp) {
  if (!timestamp) return "NOW";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "HISTORY";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function renderMessages(messages) {
  elements.messages.replaceChildren();
  const visible = messages.filter(
    (message) =>
      message.role === "user" ||
      (message.role === "assistant" && !message.tool_call_id),
  );
  visible.forEach((message) => {
    const article = document.createElement("article");
    const isUser = message.role === "user";
    article.className = `message ${isUser ? "message-user" : "message-agent"}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${isUser ? "YOU" : "AGENT"} · ${messageTime(message.created_at)}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = String(message.content || "");
    article.append(meta, bubble);
    elements.messages.append(article);
  });
  elements.emptyState.classList.toggle("is-hidden", visible.length > 0);
  elements.messageCount.textContent = `${visible.length} 条消息`;
  requestAnimationFrame(() => {
    elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
  });
}

const traceLabels = {
  request_started: "收到用户请求",
  llm_decision: "模型完成决策",
  tool_executed: "工具执行完成",
  final_answer: "返回最终答案",
  context_compressed: "上下文已压缩",
  request_failed: "请求执行失败",
  duplicate_tool_call: "阻止重复调用",
  llm_output_invalid: "模型输出纠正",
};

function renderTraces(traces) {
  elements.traceList.replaceChildren();
  const relevant = traces.slice(-8).reverse();
  if (!relevant.length) {
    const empty = document.createElement("p");
    empty.className = "muted-copy";
    empty.textContent = "发送消息后，这里会显示模型决策、工具执行和最终回答。";
    elements.traceList.append(empty);
    return;
  }
  relevant.forEach((trace) => {
    const item = document.createElement("article");
    item.className = `trace-item ${trace.event_type === "tool_executed" ? "is-tool" : ""}`;
    const title = document.createElement("div");
    title.className = "trace-title";
    title.textContent = `${String(trace.step ?? "—").padStart(2, "0")} · ${traceLabels[trace.event_type] || trace.event_type}`;
    const detail = document.createElement("p");
    detail.className = "trace-detail";
    if (trace.tool_name) {
      detail.textContent = `${trace.tool_name} · ${trace.duration_ms ?? 0} ms`;
    } else if (trace.decision_summary) {
      detail.textContent = trace.decision_summary;
    } else {
      detail.textContent = trace.trace_id || "runtime event";
    }
    item.append(title, detail);
    elements.traceList.append(item);
  });
}

function renderTodos(todos) {
  elements.todoList.replaceChildren();
  elements.todoCount.textContent = String(todos.length);
  if (!todos.length) {
    const empty = document.createElement("p");
    empty.className = "muted-copy";
    empty.textContent = "当前用户还没有待办。";
    elements.todoList.append(empty);
    return;
  }
  todos.forEach((todo) => {
    const item = document.createElement("article");
    item.className = `todo-item ${todo.status === "completed" ? "is-completed" : ""}`;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "todo-toggle";
    toggle.setAttribute("aria-label", `完成待办 ${todo.content}`);
    toggle.textContent = todo.status === "completed" ? "✓" : "";
    toggle.disabled = todo.status === "completed";
    toggle.addEventListener("click", () => completeTodo(todo.id));
    const copy = document.createElement("div");
    const content = document.createElement("p");
    content.className = "todo-content";
    content.textContent = todo.content;
    const id = document.createElement("span");
    id.className = "todo-id";
    id.textContent = `#${todo.id} · ${todo.status}`;
    copy.append(content, id);
    item.append(toggle, copy);
    elements.todoList.append(item);
  });
}

async function loadHealth() {
  try {
    const data = await request("/api/health");
    elements.runtimeStatus.classList.toggle("is-ready", data.ready);
    elements.runtimeStatus.classList.toggle("is-error", !data.ready);
    elements.runtimeStatusText.textContent = data.ready ? "Runtime 已就绪" : "LLM 配置未完成";
    elements.modelName.textContent = data.model;
    elements.sendButton.disabled = !data.ready;
    if (!data.ready && data.runtime_error) showToast(data.runtime_error);
  } catch (error) {
    elements.runtimeStatus.classList.add("is-error");
    elements.runtimeStatusText.textContent = "无法连接本地服务";
    elements.sendButton.disabled = true;
  }
}

async function loadSession({ quiet = false } = {}) {
  try {
    setIdentity();
    const params = new URLSearchParams({ user_id: state.userId, session_id: state.sessionId });
    const data = await request(`/api/session?${params}`);
    renderMessages(data.messages || []);
    renderTraces(data.traces || []);
    renderTodos(data.todos || []);
    if (!quiet) showToast(`已加载 ${state.sessionId}`);
  } catch (error) {
    showToast(error.message);
  }
}

async function sendMessage(message) {
  if (state.sending || !message.trim()) return;
  try {
    setIdentity();
    state.sending = true;
    elements.sendButton.disabled = true;
    elements.sendButton.querySelector("span").textContent = "运行中";
    elements.messageInput.disabled = true;
    const optimistic = {
      id: `local-${Date.now()}`,
      role: "user",
      content: message.trim(),
      created_at: new Date().toISOString(),
    };
    const current = Array.from(elements.messages.querySelectorAll(".message")).length;
    elements.emptyState.classList.add("is-hidden");
    const waiting = document.createElement("article");
    waiting.className = "message message-agent";
    waiting.innerHTML = '<div class="message-meta">AGENT · RUNNING</div><div class="message-bubble">正在思考并检查是否需要调用工具…</div>';
    renderMessages([optimistic]);
    elements.messages.append(waiting);
    elements.messageCount.textContent = `${current + 1} 条消息`;
    const data = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        user_id: state.userId,
        session_id: state.sessionId,
        message: message.trim(),
      }),
    });
    renderMessages(data.messages || []);
    renderTraces(data.traces || []);
    renderTodos(data.todos || []);
    elements.messageInput.value = "";
  } catch (error) {
    showToast(error.message);
    await loadSession({ quiet: true });
  } finally {
    state.sending = false;
    elements.sendButton.disabled = false;
    elements.sendButton.querySelector("span").textContent = "发送";
    elements.messageInput.disabled = false;
    elements.messageInput.focus();
  }
}

async function completeTodo(todoId) {
  try {
    const data = await request("/api/todos/complete", {
      method: "POST",
      body: JSON.stringify({ user_id: state.userId, todo_id: todoId }),
    });
    renderTodos(data.todos || []);
    showToast(`待办 #${todoId} 已完成`);
  } catch (error) {
    showToast(error.message);
  }
}

elements.loadSession.addEventListener("click", () => loadSession());
elements.refreshSession.addEventListener("click", () => loadSession({ quiet: true }));
elements.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.messageInput.value);
});
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});
document.querySelectorAll("[data-session]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.sessionId.value = button.dataset.session;
    loadSession();
  });
});
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.messageInput.value = button.dataset.prompt;
    elements.messageInput.focus();
  });
});

loadHealth();
loadSession({ quiet: true });
