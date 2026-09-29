from .config import ANTHROPIC_API_KEY


def is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def explain_flaky_test(test_name: str, history: list[dict]) -> str:
    """Ask Claude why a test looks flaky, given its recent outcome history.

    Raises RuntimeError if ANTHROPIC_API_KEY is not set — callers should
    check `is_configured()` first and return a clear 501 instead of calling
    this.
    """
    if not is_configured():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    history_lines = "\n".join(
        f"- {item['created_at']} on {item['branch']}: {item['outcome']}"
        + (f" ({item['error_message']})" if item.get("error_message") else "")
        for item in history
    )

    prompt = (
        f"The test `{test_name}` has been flagged as flaky. "
        f"Here is its recent outcome history (newest first):\n\n{history_lines}\n\n"
        "In 2-3 sentences, suggest the most likely cause of this flakiness "
        "(e.g. timing/race condition, shared state, external dependency, "
        "test order dependency) based on the pattern above."
    )

    message = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
