# LLM Providers

OpenDevOps Agent uses [LiteLLM](https://docs.litellm.ai) to support 100+ LLM providers through a single unified interface. Switching providers requires only a `.env` change — no code modifications.

---

## How it works

`LLM_MODEL` is a LiteLLM model string in the format `provider/model-name`. At startup, `ChatLiteLLM` in `src/agent/core.py` reads this value and routes all LLM calls to the correct provider. LangChain's `BaseChatModel` interface means the rest of the agent (tool calling, streaming, DeepAgents graph) is completely unaware of which provider is in use.

```
.env: LLM_MODEL=anthropic/claude-3-5-sonnet-20241022
         ↓
src/agent/config.py  →  settings.llm_model
         ↓
src/agent/core.py    →  ChatLiteLLM(model=settings.llm_model)
         ↓
LiteLLM routes to Anthropic API  →  same agent graph, same tools
```

---

## Supported providers (examples)

### Claude Code (zero-config, uses your subscription)

If you have [Claude Code](https://claude.ai/code) installed and logged in, OpenDevOps can use your **existing Claude subscription** as the LLM — no API key, no `.env` changes.

> **Important — leave these unset.** Auto-detection only activates when you have **not** explicitly configured another provider. To use Claude Code, make sure your `.env` does **not** set any of:
> - `LLM_MODEL`
> - `OPENROUTER_API_KEY`
> - `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`
> - `LLM_API_BASE`
>
> If any of those are present, that provider wins and Claude Code is skipped. The simplest setup is an empty (or absent) `.env` — Claude Code is picked up automatically.

**How it works:**
1. On startup the app checks whether the `claude` CLI is in your `PATH`.
2. It reads `~/.claude/settings.json` for your selected model (e.g. `sonnet` → `anthropic/claude-sonnet-4-6`).
3. It reuses Claude Code's subscription login — the OAuth token in `~/.claude/.credentials.json` (`sk-ant-oat…`). LiteLLM sends it as a Bearer token with the OAuth beta header automatically.

The active backend is shown in **Settings → Environment** and in the **setup wizard**.

**Notes:**
- Rate limits are shared with your interactive Claude Code usage — both draw from the same subscription quota.
- The OAuth token expires periodically; running any `claude` command refreshes it.
- To force a different provider even when Claude Code is installed, set `LLM_MODEL` + the matching key, or disable detection entirely with `CLAUDE_CODE_AUTODETECT=false`.

---

### OpenRouter (default — 200+ models via one key)
```bash
LLM_MODEL=openrouter/openai/gpt-4o
OPENROUTER_API_KEY=sk-or-...
```
Browse all models at [openrouter.ai/models](https://openrouter.ai/models). Prefix any model ID with `openrouter/`.

### Anthropic
```bash
LLM_MODEL=anthropic/claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```
Other models: `anthropic/claude-3-5-haiku-20241022`, `anthropic/claude-3-opus-20240229`

### OpenAI
```bash
LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-...
```
Other models: `openai/gpt-4o-mini`, `openai/o1-mini`

### Groq (fast inference, free tier available)
```bash
LLM_MODEL=groq/llama3-70b-8192
GROQ_API_KEY=gsk_...
```
Other models: `groq/llama-3.1-8b-instant`, `groq/mixtral-8x7b-32768`

### Ollama (local, no API key)
```bash
LLM_MODEL=ollama/llama3
LLM_API_BASE=http://localhost:11434
```
Pull a model first: `ollama pull llama3`

### Any OpenAI-compatible endpoint (vLLM, LM Studio, Azure, etc.)
```bash
LLM_MODEL=openai/your-model-name
LLM_API_BASE=https://your-endpoint/v1
LLM_API_KEY=your-key
```

---

## API key resolution

LiteLLM reads API keys from standard environment variables automatically — you do not need to prefix them or add them to the app config:

| Provider | Env var |
|---|---|
| OpenRouter | `OPENROUTER_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Cohere | `COHERE_API_KEY` |
| Mistral | `MISTRAL_API_KEY` |
| Ollama | none required |

For custom endpoints, set `LLM_API_KEY` directly in `.env`.

---

## Choosing a model

| Goal | Recommended model |
|---|---|
| Best investigation quality | `anthropic/claude-3-5-sonnet-20241022` |
| Fastest + free | `groq/llama3-70b-8192` |
| Cheapest OpenRouter | `openrouter/google/gemma-4-26b-a4b-it` |
| Air-gapped / private | `ollama/llama3` or `ollama/mistral` |
| Balanced (default) | `openrouter/openai/gpt-4o` |

Tool calling support is required. Most frontier models support it; smaller local models vary — test before using in production.

---

## Cost tracking

Cost is calculated automatically using LiteLLM's built-in pricing database via `litellm.completion_cost()`. It covers thousands of models across all supported providers — no manual maintenance needed. If a model isn't in LiteLLM's database (e.g. a private endpoint), the cost card in the UI will show no estimate but everything else still works.

---

## Source files

| File | Purpose |
|---|---|
| `src/agent/core.py` | `ChatLiteLLM` instantiation in `init_agent()` |
| `src/agent/config.py` | `llm_model`, `llm_api_base`, `llm_api_key` settings |
| `src/api/routers/chat.py` | `_PRICING` map for cost tracking |
