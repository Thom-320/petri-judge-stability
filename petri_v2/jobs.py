"""Judge jobs (transcript x judge x repeat) and the provider request bodies built from them."""
import hashlib
import json
import re

from . import corpus, judges, prompts, view as view_mod

CUSTOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")  # Anthropic's custom_id rule; also valid for Gemini/OpenAI


def custom_id(transcript_id, judge_label, repeat):
    cid = f"t{transcript_id}-{judge_label}-r{repeat}"
    if not CUSTOM_ID_RE.match(cid):
        raise ValueError(f"invalid custom_id {cid!r}")
    return cid


def split_custom_id(cid):
    t, judge, rep = cid.rsplit("-", 2)
    return t[1:], judge, int(rep[1:])


def build_inputs(n=corpus.N_ANALYSIS, dims=None, view="petri", data_dir=corpus.DEFAULT_DATA, start=0):
    """One judge input (system + user) per transcript in analysis order positions start+1..n."""
    dims = dims or prompts.STUDY_DIMS
    system = prompts.build_system_prompt(dims)
    out = []
    for row in corpus.analysis_order(data_dir)[start:n]:
        d = corpus.load_transcript(row["transcript_key"], data_dir)
        user = prompts.build_user_message(view_mod.transcript_xml(d, view))
        out.append({"pos": row["pos"], "transcript_id": d["metadata"]["transcript_id"],
                    "transcript_key": row["transcript_key"], "system": system, "user": user,
                    "dims": list(dims), "view": view,
                    "input_sha256": hashlib.sha256((system + "\x00" + user).encode()).hexdigest()})
    return out


def build_jobs(inputs, judge_labels, repeats=judges.REPEATS):
    jobs = []
    for inp in inputs:
        for label in judge_labels:
            for rep in repeats:
                jobs.append({**inp, "judge": label, "repeat": rep,
                             "custom_id": custom_id(inp["transcript_id"], label, rep)})
    return jobs


# ---------------------------------------------------------------- provider request bodies
def anthropic_params(job):
    j = judges.get(job["judge"])
    params = {
        "model": j.model,
        "max_tokens": judges.MAX_TOKENS,
        "thinking": {"type": "enabled", "budget_tokens": judges.REASONING_TOKENS},
        "system": job["system"],
        "messages": [{"role": "user", "content": job["user"]}],
    }
    if j.thinking == "adaptive":
        # Claude 4.7+ (e.g. Opus 5.5) rejects type "enabled"; inspect_ai maps reasoning_effort to
        # adaptive thinking plus output_config.effort for these models.
        params["thinking"] = {"type": "adaptive"}
        params["output_config"] = {"effort": judges.REASONING_EFFORT}
    return params


def gemini_request(job):
    return {
        "systemInstruction": {"parts": [{"text": job["system"]}]},
        "contents": [{"role": "user", "parts": [{"text": job["user"]}]}],
        "generationConfig": {
            "maxOutputTokens": judges.MAX_TOKENS,
            "thinkingConfig": {"thinkingLevel": judges.REASONING_EFFORT.upper(), "includeThoughts": True},
        },
    }


def openai_body(job):
    j = judges.get(job["judge"])
    return {
        "model": j.model,
        "input": [{"role": "developer", "content": job["system"]}, {"role": "user", "content": job["user"]}],
        "max_output_tokens": judges.MAX_TOKENS,
        "reasoning": {"effort": judges.REASONING_EFFORT},
        "store": False,
    }


def chat_body(job):
    """OpenAI-compatible Chat Completions body for the open-weight judges (Kimi, DeepSeek).

    Thinking on, as Petri's reasoning_effort="high" maps; max_tokens = Petri's 32,000 (it covers
    reasoning and answer on both APIs). No temperature/top_p: Kimi K2.6 fixes them in thinking mode
    and its Batch API forbids sending them; DeepSeek thinking mode ignores them."""
    j = judges.get(job["judge"])
    body = {
        "model": j.model,
        "messages": [{"role": "system", "content": job["system"]}, {"role": "user", "content": job["user"]}],
        "max_tokens": judges.MAX_TOKENS,
        "thinking": {"type": "enabled"},
    }
    if j.provider == "deepseek":
        body["reasoning_effort"] = judges.REASONING_EFFORT  # "high" (also the API default)
    return body


def batch_line(job):
    """The exact JSON object a job contributes to its provider's batch."""
    p = judges.get(job["judge"]).provider
    if p == "anthropic":
        return {"custom_id": job["custom_id"], "params": anthropic_params(job)}
    if p == "gemini":
        return {"key": job["custom_id"], "request": gemini_request(job)}
    if p == "openai":
        return {"custom_id": job["custom_id"], "method": "POST", "url": "/v1/responses", "body": openai_body(job)}
    if p == "moonshot":
        return {"custom_id": job["custom_id"], "method": "POST", "url": "/v1/chat/completions", "body": chat_body(job)}
    if p == "deepseek":  # no Batch API: the synchronous request body, keyed like a batch line
        return {"custom_id": job["custom_id"], "body": chat_body(job)}
    raise ValueError(p)


def batch_line_bytes(job):
    return len(json.dumps(batch_line(job), ensure_ascii=False).encode("utf-8")) + 1
