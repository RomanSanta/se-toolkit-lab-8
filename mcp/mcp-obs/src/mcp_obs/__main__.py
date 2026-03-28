"""Allow running as `python -m mcp_obs`."""

import asyncio

from mcp_obs.server import main

if __name__ == "__main__":
    asyncio.run(main())
