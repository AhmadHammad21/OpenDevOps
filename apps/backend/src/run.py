"""Dev server entry point — sets Windows SelectorEventLoop before uvicorn starts."""
import sys

# Must be set BEFORE uvicorn creates the event loop.
# psycopg3 async does not support Windows' default ProactorEventLoop.
if sys.platform == "win32":
    import asyncio
    import selectors
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=True)
