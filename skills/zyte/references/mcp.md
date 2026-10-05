This file is 25 lines long; read all of them.

# Zyte MCP

The Zyte MCP server at `https://mcp.zyte.com/v1/mcp` gives the agent Zyte
tools that run under the user's own Zyte login: page fetching and extraction,
the account's organizations (`user_info`), Scrapy Cloud jobs, periodic jobs,
items and logs (`scrapy_cloud_*`), recorded Zyte API usage
(`zyte_api_usage_stats`) and per-website prices (`zyte_api_domain_pricing`).
This skill has no other way to do any of that: no script or `curl` replaces
these tools.

The plugin declares the server, so Claude Code lists its tools as `mcp__plugin_zyte-web-data_zyte__<tool>`; a server the user added with `claude mcp add` is listed as `mcp__zyte__<tool>` instead.

## When the server is missing

No tool of the Zyte MCP among the available tools means the server is not
connected. Say that the request needs the Zyte MCP, and how to connect it.
Tell the user to install or update the Zyte Agentic Web Data plugin, which declares the server, then run `/mcp` and sign in to `zyte` in the browser. They should not also add the server with `claude mcp add`, or every tool is listed twice. Once connected, the user can repeat the request.

A call answered with HTTP 401 and a message that the tool needs an account
login means the server was added with a Zyte API key as the bearer token. A
key gives the fetch, extraction, search and domain pricing tools only; Scrapy
Cloud, usage stats and `user_info` need the browser sign-in, so the fix is to
reconnect the server without the key and sign in.
