"""System prompt builder for the ADMZ chatbot.

The system prompt is small on purpose: most of the LLM's
guidance comes from the MCP tool descriptions themselves, which
the model sees natively (ADR-0025). We only inject what the LLM
cannot know from tools alone:

  - The authenticated principal (so the LLM addresses the user
    correctly and knows whose audit-log entries it's generating).
  - The org's safety posture (multi-level confirmation gates,
    snapshot-before-write).
  - Brief house style (concise answers, ask before destructive).
"""

from __future__ import annotations

from typing import Iterable, Optional


_PROMPT_TEMPLATE = """\
You are ADMZ, an assistant for Axis network device fleet management.

Authenticated user: {user_line}

You operate through the ADMZ MCP tools (provided as your tool
surface). Every tool call is audit-logged against the
authenticated user above.

Safety posture you must respect:
- Read-only queries can run freely.
- Writes go through plans; ADMZ snapshots the device before any
  write so rollback is always available.
- "Dangerous" risk operations (factory reset, firmware ops,
  delete-user) require explicit user confirmation. Never assume
  consent; always show the user what will happen and wait for
  them to approve.
- Credentials live in the registry, never in chat. To collect a
  password from the user, use the capture tool, never ask in
  plain text.

House style:
- Concise, factual answers. If you need data from the device,
  call a tool — don't speculate.
- Surface costs and irreversibility before acting.
- When unsure, ask.
"""


def build_system_prompt(
    principal_name: str,
    *,
    display_name: Optional[str] = None,
    groups: Optional[Iterable[str]] = None,
) -> str:
    """Construct the chatbot's system prompt for a given principal."""
    display = display_name or principal_name
    group_list = sorted(set(groups)) if groups else []

    if group_list:
        user_line = f"{display} ({principal_name}) — groups: {', '.join(group_list)}"
    elif display != principal_name:
        user_line = f"{display} ({principal_name})"
    else:
        user_line = principal_name

    return _PROMPT_TEMPLATE.format(user_line=user_line)
