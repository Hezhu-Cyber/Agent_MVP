from agent.prompts import SYSTEM_PROMPT


def test_todo_prompt_requires_explicit_user_intent() -> None:
    assert "只有用户明确要求" in SYSTEM_PROMPT
    assert "才允许调用 todo 工具" in SYSTEM_PROMPT
    assert "禁止创建 todo" in SYSTEM_PROMPT
    assert "不确定用户是否要创建待办时，先询问用户" in SYSTEM_PROMPT
