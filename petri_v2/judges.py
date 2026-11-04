"""Judge facets: model IDs, service status and request parameters.

Status checked 2026-10-09 against the providers' official pages (URLs below and in prices.yaml).
Petri 2.0's official judges (alignment.anthropic.com/2026/petri-v2): Claude Opus 4.5, Gemini 3 Pro,
GPT-5.1. A retired model is kept in this registry with served=False and its named successor is a
separate, explicitly labelled facet, never a silent swap.

Request parameters mirror Petri's judge config at f02b3ec
(`GenerateConfig(max_tokens=32_000, reasoning_tokens=10_000, reasoning_effort="high")`) as mapped
by inspect_ai (Petri's uv.lock pins inspect-ai 0.3.192, not on PyPI any more; mapping read from
0.3.193's providers):
  - Anthropic, Claude 4.5: `max_tokens=32000`, `thinking={"type": "enabled", "budget_tokens": 10000}`,
    no temperature (incompatible with thinking); inspect_ai 0.3.193 sends no `effort` for 4.5 models.
  - Gemini 3+: `maxOutputTokens=32000`, `thinkingConfig={"thinkingLevel": "HIGH", "includeThoughts": true}`
    (reasoning_tokens is not sent when thinking_level is used; the API rejects both together).
  - OpenAI GPT-5.x: Responses API, `max_output_tokens=32000`, `reasoning={"effort": "high"}`,
    system prompt sent as a `developer` message.

Sampling (pre-registration, Session 2): no request sets temperature, top_p or top_k, for any
judge. Each provider's default applies, and with reasoning on it is fixed or required: Anthropic
"temperature and top_k are incompatible with thinking" (default 1.0); Gemini 3 "strongly recommend
keeping the temperature parameter at its default value of 1.0" (3.6 Flash and later ignore it);
OpenAI reasoning models reject temperature/top_p when reasoning effort is not none; DeepSeek
thinking mode ignores temperature; Kimi K2.6 fixes temperature 1.0 and top_p 0.95 in thinking mode
and its Batch API forbids setting them. σ²_e is therefore the provider-default sampling noise at
these settings. Quotes and URLs: docs/CLOUD-SESSION-2026-10.md, Session 2.

Expanded panel (Session 2, checked 2026-10-10): a stated judge population, "frontier and mid-tier
judges served on 2026-10-10 from at least 4 developers": the three Petri facets (frontier), one
tier down from each of Anthropic, Google and OpenAI (mid), and two strong open-weight judges
(DeepSeek, Moonshot Kimi). `runner` says whether this repository can submit to it yet.
"""
from dataclasses import dataclass, field

CHECKED = "2026-10-09"  # Session 2 additions: 2026-10-10


@dataclass(frozen=True)
class Judge:
    label: str
    provider: str           # anthropic | gemini | openai
    model: str
    served: bool
    status: str
    official_petri_judge: bool
    sources: tuple = field(default_factory=tuple)
    successor_of: str = ""
    thinking: str = "budget"   # anthropic only: "budget" (enabled + budget_tokens) or "adaptive"
    developer: str = ""
    tier: str = "frontier"     # frontier | mid | open (open-weight)
    open_weight: bool = False
    runner: bool = True        # a batch runner in this repository can submit to it
    sampling: str = "provider default; temperature/top_p/top_k never sent"
    reasoning: str = ""        # how Petri's reasoning_effort="high" is mapped


JUDGES = {
    "opus45": Judge(
        "opus45", "anthropic", "claude-opus-4-5-20251101", True,
        "Active (legacy); retirement 'not sooner than November 24, 2026'. Run this leg before that date.",
        True, ("https://platform.claude.com/docs/en/about-claude/model-deprecations",
               "https://platform.claude.com/docs/en/models/opus-4-5/overview")),
    "gemini3pro": Judge(
        "gemini3pro", "gemini", "gemini-3-pro-preview", False,
        "Shut down 2026-03-09 (deprecations page); named replacement gemini-3.1-pro-preview.",
        True, ("https://ai.google.dev/gemini-api/docs/deprecations",)),
    "gemini31pro": Judge(
        "gemini31pro", "gemini", "gemini-3.1-pro-preview", True,
        "Preview, no shutdown date announced. Successor facet for the retired gemini-3-pro-preview.",
        False, ("https://ai.google.dev/gemini-api/docs/deprecations",
                "https://ai.google.dev/gemini-api/docs/models"), successor_of="gemini3pro"),
    "gpt51": Judge(
        "gpt51", "openai", "gpt-5.1-2025-11-13", True,
        "Deprecated; removal from the API on 2027-04-01; named replacement gpt-6-sol.",
        True, ("https://developers.openai.com/api/docs/deprecations",
               "https://developers.openai.com/api/docs/models/gpt-5.1")),
    "gpt6sol": Judge(
        "gpt6sol", "openai", "gpt-6-sol", True,
        "Named replacement for gpt-5.1 (deprecations page). Optional facet; not in the default design.",
        False, ("https://developers.openai.com/api/docs/deprecations",), successor_of="gpt51"),
    "opus55": Judge(
        "opus55", "anthropic", "claude-opus-5-5", True,
        "Named on the Opus 4.5 page as the migration target. Optional facet, only if Opus 4.5 is retired "
        "before the run. Adaptive thinking only (type 'enabled' with budget_tokens returns 400).",
        False, ("https://platform.claude.com/docs/en/models/opus-4-5/overview",
                "https://platform.claude.com/docs/en/models/opus-5-5/overview"),
        successor_of="opus45", thinking="adaptive"),
}

JUDGES.update({
    "sonnet55": Judge(
        "sonnet55", "anthropic", "claude-sonnet-5-5", True,
        "Active; retirement 'not sooner than September 28, 2027'. Current Sonnet (one tier below Opus).",
        False, ("https://platform.claude.com/docs/en/about-claude/models/overview",
                "https://platform.claude.com/docs/en/about-claude/model-deprecations",
                "https://platform.claude.com/docs/en/about-claude/pricing"),
        thinking="adaptive", developer="Anthropic", tier="mid",
        sampling="temperature not sent: 'non-default temperature ... return a 400 error'",
        reasoning="thinking {type: adaptive} + output_config.effort high"),
    "gemini38flash": Judge(
        "gemini38flash", "gemini", "gemini-3.8-flash", True,
        "Stable (released 2026-09-02), no shutdown date announced. Batch price doubles on 2027-01-01.",
        False, ("https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash",
                "https://ai.google.dev/gemini-api/docs/pricing"),
        developer="Google", tier="mid",
        sampling="temperature/top_p/top_k 'deprecated and ignored' from Gemini 3.6 Flash on",
        reasoning="thinkingConfig.thinkingLevel HIGH (model default is medium)"),
    "gpt54mini": Judge(
        "gpt54mini", "openai", "gpt-5.4-mini-2026-03-17", True,
        "Active, no deprecation listed (gpt-5-mini shuts down 2026-12-11, so not used).",
        False, ("https://developers.openai.com/api/docs/models/gpt-5.4-mini",
                "https://developers.openai.com/api/docs/pricing"),
        developer="OpenAI", tier="mid",
        sampling="temperature/top_p rejected with reasoning effort not none; not sent",
        reasoning="reasoning.effort high"),
    "deepseekv4pro": Judge(
        "deepseekv4pro", "deepseek", "deepseek-v4-pro", True,
        "Active on DeepSeek's API (model version DeepSeek-V4-Pro-0813, MIT weights). No Batch API; "
        "off-peak synchronous calls cost half (peak 01-04 and 06-10 UTC Mon-Fri).",
        False, ("https://api-docs.deepseek.com/quick_start/pricing",
                "https://api-docs.deepseek.com/guides/thinking_mode",
                "https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro-0813"),
        developer="DeepSeek", tier="open", open_weight=True,
        sampling="thinking mode ignores temperature; not sent",
        reasoning="thinking {type: enabled} + reasoning_effort high (the API default)"),
    "kimik26": Judge(
        "kimik26", "moonshot", "kimi-k2.6", True,
        "Active on Moonshot's platform (modified-MIT weights); Batch API supports kimi-k2.6 at 60% of list.",
        False, ("https://platform.kimi.ai/docs/pricing/chat",
                "https://platform.kimi.ai/docs/pricing/batch",
                "https://platform.kimi.ai/docs/guide/use-batch-api"),
        developer="Moonshot AI", tier="open", open_weight=True,
        sampling="temperature 1.0 and top_p 0.95 fixed in thinking mode; Batch API forbids sending them",
        reasoning="thinking {type: enabled} (the default)"),
    # Alternates, not in a default panel.
    "qwen38max": Judge(
        "qwen38max", "fireworks", "accounts/fireworks/models/qwen3p8-max", True,
        "Qwen3.8-2.4T-A95B served by Fireworks; batch = 50% of serverless (price derived, not listed).",
        False, ("https://fireworks.ai/models/fireworks/qwen3p8-max", "https://docs.fireworks.ai/guides/batch-inference",
                "https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B"),
        developer="Alibaba Qwen", tier="open", open_weight=True, runner=False,
        sampling="model card recommends temperature 1.0, top_p 0.95, top_k 20; not sent",
        reasoning="thinking always on"),
    "gemma4": Judge(
        "gemma4", "deepinfra", "google/gemma-4-31B-it", True,
        "Gemma 4 31B (Apache 2.0). Gemini API: free tier only, no paid or batch tier; DeepInfra batch = 80% "
        "of list (price derived). Weaker than the other judges: optional Google open-weight stratum.",
        False, ("https://ai.google.dev/gemini-api/docs/pricing", "https://docs.deepinfra.com/batch/introduction"),
        developer="Google", tier="open", open_weight=True, runner=False,
        sampling="model card recommends temperature 1.0, top_p 0.95, top_k 64; not sent",
        reasoning="thinking level high"),
})
for _k in ("opus45", "gemini3pro", "gemini31pro", "gpt51", "gpt6sol", "opus55"):
    _j = JUDGES[_k]
    JUDGES[_k] = Judge(**{**_j.__dict__, "developer": {"anthropic": "Anthropic", "gemini": "Google", "openai": "OpenAI"}[_j.provider],
                          "reasoning": {"anthropic": "thinking {type: enabled, budget_tokens: 10000}" if _j.thinking == "budget"
                                        else "thinking {type: adaptive} + output_config.effort high",
                                        "gemini": "thinkingConfig.thinkingLevel HIGH",
                                        "openai": "reasoning.effort high"}[_j.provider],
                          "sampling": {"anthropic": "temperature not sent (incompatible with thinking; default 1.0)",
                                       "gemini": "temperature not sent (default 1.0, which Google recommends keeping)",
                                       "openai": "temperature/top_p not sent (rejected with reasoning on)"}[_j.provider]})

# Default v2 design: one served judge per official Petri family (gemini3pro is retired).
DEFAULT_PANEL = ["opus45", "gemini31pro", "gpt51"]
# Design options for Thomas (pre-registration §3). The extra judges score only the 140
# confirmatory transcripts (positions 121-260). The Petri panel stays the confirmatory panel.
PANEL_J6 = DEFAULT_PANEL + ["gemini38flash", "deepseekv4pro", "kimik26"]
PANEL_J8 = DEFAULT_PANEL + ["sonnet55", "gemini38flash", "gpt54mini", "deepseekv4pro", "kimik26"]
REPEATS = [1, 2]

MAX_TOKENS = 32000
REASONING_TOKENS = 10000
REASONING_EFFORT = "high"


def get(label):
    if label not in JUDGES:
        raise KeyError(f"unknown judge {label!r}; known: {sorted(JUDGES)}")
    return JUDGES[label]


def require_served(label):
    j = get(label)
    if not j.served:
        raise SystemExit(f"judge {label} ({j.model}) is not served: {j.status}")
    return j
