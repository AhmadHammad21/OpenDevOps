# Tool Response Caching

## What it does

Every AWS tool function is decorated with `@tool_cached`. Repeated calls with the
same arguments within a 2-minute window return the cached result instantly — no
AWS API call is made. This matters for investigations where the agent calls the same
tool multiple times (e.g. `get_alarms` at the start and again after a hypothesis).

## How it works

`src/tools/_cache.py` wraps `cachetools.TTLCache`:

- **Max entries:** 256
- **TTL:** 120 seconds (2 minutes)
- **Cache key:** function name + AWS profile + AWS region + serialised arguments

Including the AWS profile and region in the key means:
- Zero-argument functions like `list_lambda_functions()` never collide across functions
- Results from different AWS accounts or regions are never mixed (multi-tenant safe)

## Configuration

The cache is always on — there are no env vars to configure it. It is entirely
in-process and does not require Redis or any external service.

To swap the cache backend to Redis later, only `src/tools/_cache.py` needs to change —
tool files don't need to be touched.

## Interaction with tool response capping

The cap (`TOOL_RESPONSE_MAX_CHARS`) is applied **after** the cache is checked.
The raw full result is cached; the cap is applied on the way out to the LLM. This
means the cache always stores the full response regardless of the current cap setting.

## When caching is NOT useful

- First call in a session always hits AWS
- Results older than 2 minutes are always re-fetched
- The cache is lost on process restart (in-memory only)
