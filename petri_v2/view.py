"""Transcript view for the judge: a dependency-free port of Petri's view code at f02b3ec.

Ported from (verbatim copies in petri_v2/pinned/f02b3ec/):
  - transcript.py: `_collect_messages(events, "target", add_only=True, indicate_rollbacks=True)`,
    `_iter_branches`, `_common_prefix_len`, the edit classes (AddMessage, Rollback, Reset, JSONPatchEdit)
  - xml_messages.py: `format_messages_xml` and the per-role formatters
  - messages.py: `format_content`, `_is_prefill_message`

Two views are offered:
  - "petri" (default): what Petri's `alignment_judge` actually builds. It replays the transcript
    events for the "target" view in add-only mode, so rolled-back branches stay in the transcript,
    separated by <info> "Starting new conversation branch ..." markers.
  - "target_messages": the stored final target branch, as used in the cheap-judge pilot.
Neither view contains the auditor's own messages or commentary (unlike the corpus' `messages`).
On the public corpus the two differ only for transcripts with target rollbacks
(64 of 311 files; counted by `python -m petri_v2.estimate --view-report`).

Differences from Petri that cannot matter on plain JSON: Petri compares messages with pydantic
`model_dump()`; here plain dicts are compared after the same JSON patch ops. Equivalence with the
real Petri code on all 311 corpus files is checked in tests/test_view.py when vendor/ and
inspect_ai are installed, and against committed SHA-256 fingerprints otherwise.
"""
import copy
import json

import jsonpatch

VIEWS = ("petri", "target_messages")


# ---------------------------------------------------------------- messages.py
def format_content(content):
    if isinstance(content, str):
        return content
    text_parts = []
    for item in content or []:
        t = item.get("type")
        if t == "text":
            text_parts.append(item.get("text", ""))
        elif t == "reasoning":
            if item.get("redacted"):
                if item.get("summary"):
                    text_parts.append(f"<thinking_summary>\n{item['summary'].strip()}\n</thinking_summary>")
                else:
                    text_parts.append("<thinking_redacted/>")
            else:
                text_parts.append(f"<thinking>\n{item.get('reasoning')}\n</thinking>")
        elif t == "image":
            text_parts.append("[Image]")
        elif t == "audio":
            text_parts.append("[Audio]")
        elif t == "video":
            text_parts.append("[Video]")
        elif t == "data":
            text_parts.append("[Data]")
    return "\n".join(text_parts)


def _is_prefill_message(m):
    md = m.get("metadata")
    return bool(md) and md.get("prefill") is True


# ---------------------------------------------------------------- xml_messages.py
def format_tool_call_xml(tc):
    lines = [f'<tool_call name="{tc.get("function")}" id="{tc.get("id")}">']
    for k, v in (tc.get("arguments") or {}).items():
        if isinstance(v, str):
            s = v
        elif isinstance(v, (dict, list)):
            s = json.dumps(v)
        else:
            s = str(v)
        lines.append(f'  <parameter name="{k}">{s}</parameter>')
    lines.append("</tool_call>")
    return "\n".join(lines)


def format_messages_xml(messages):
    """Return (transcript_xml, index_to_id) exactly as Petri's format_messages_xml."""
    parts, index_to_id, idx = [], {}, 1
    for m in messages:
        role = m.get("role")
        if role == "info":
            parts.append(f"<info>\n{format_content(m.get('content', ''))}\n</info>")
            continue
        index_to_id[str(idx)] = m.get("id")
        content = format_content(m.get("content", ""))
        if _is_prefill_message(m):
            parts.append(f'<prefill index="{idx}">\n{content}\n</prefill>')
        elif role == "system":
            parts.append(f'<system index="{idx}">\n{content}\n</system>')
        elif role == "user":
            parts.append(f'<user index="{idx}">\n{content}\n</user>')
        elif role == "assistant":
            lines = [f'<assistant index="{idx}">']
            if content:
                lines.append(content)
            for tc in m.get("tool_calls") or []:
                lines.append(format_tool_call_xml(tc))
            lines.append("</assistant>")
            parts.append("\n".join(lines))
        elif role == "tool":
            lines = [f'<tool index="{idx}">']
            if content:
                lines.append(content)
            if m.get("error"):
                lines.append((m["error"] or {}).get("message", ""))
            lines.append("</tool>")
            parts.append("\n".join(lines))
        idx += 1
    return "<transcript>\n" + "\n\n".join(parts) + "\n</transcript>", index_to_id


# ---------------------------------------------------------------- transcript.py
def _patch_ops(patch):
    # Petri: change.model_dump(by_alias=True, exclude_none=True); the corpus stores `from_`.
    ops = []
    for ch in patch:
        op = {k: v for k, v in ch.items() if v is not None and k != "replaced"}
        if "from_" in op:
            op["from"] = op.pop("from_")
        ops.append(op)
    return ops


def _apply_edit(edit, messages):
    op = edit.get("operation")
    if op == "add":
        return messages + [edit["message"]]
    if op == "rollback":
        if edit.get("to_id"):
            out = []
            for m in messages:
                out.append(m)
                if m.get("id") == edit["to_id"]:
                    break
            return out
        count = edit.get("count", 0)
        return messages if count == 0 else messages[:-count]
    if op == "reset":
        return list(edit.get("new_messages") or [])
    if op == "json_patch":
        return jsonpatch.JsonPatch(_patch_ops(edit["patch"])).apply(copy.deepcopy(messages), in_place=False)
    raise ValueError(f"unknown edit operation {op!r}")


def _common_prefix_len(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def _iter_branches(events, view):
    history = []
    for ev in events:
        if ev.get("type") != "transcript_event":
            continue
        views = ev["view"] if isinstance(ev["view"], list) else [ev["view"]]
        if not (view in views or view == "all"):
            continue
        new = _apply_edit(ev["edit"], history)
        prefix = _common_prefix_len(history, new)
        if prefix < len(history) and history:
            yield history
        history = new
    if history:
        yield history


def collect_messages(events, view="target", add_only=True, indicate_rollbacks=True):
    """Port of Petri's `_collect_messages` (the judge calls it with add_only and indicate_rollbacks)."""
    if indicate_rollbacks and not add_only:
        raise ValueError("indicate_rollbacks=True is only supported when add_only=True")
    branches = list(_iter_branches(events, view))
    if not branches:
        return []
    aggregated, history = [], []
    for new in branches:
        prefix = _common_prefix_len(history, new)
        branched = prefix < len(history)
        if add_only and indicate_rollbacks and branched:
            if prefix > 0:
                last = format_content(new[prefix - 1].get("content", ""))
                if len(last) > 1010:
                    last = last[:500] + "..." + last[-500:]
                aggregated.append({"role": "info", "content": (
                    f"Starting new conversation branch from this message:\n<message>\n{last}\n</message>\n"
                    f"Continuing conversation from this point.")})
            else:
                aggregated.append({"role": "info", "content": "Starting new conversation branch from the beginning."})
        if add_only:
            aggregated.extend(new[prefix:])
        history = new
    return aggregated if add_only else history


def n_target_branches(transcript):
    return len(list(_iter_branches(transcript.get("events") or [], "target")))


def judge_messages(transcript, view="petri"):
    """Messages the judge sees for one corpus transcript (dict loaded from the corpus JSON)."""
    if view == "petri":
        return collect_messages(transcript.get("events") or [], "target", add_only=True, indicate_rollbacks=True)
    if view == "target_messages":
        return list(transcript["target_messages"])
    raise ValueError(f"view must be one of {VIEWS}")


def transcript_xml(transcript, view="petri"):
    return format_messages_xml(judge_messages(transcript, view))[0]
