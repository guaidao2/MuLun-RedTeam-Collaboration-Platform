#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - MCP 客户端示例（Streamable HTTP）

用法：
  pip install mcp
  python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" list_tools
  python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" call --name list_projects
  python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" \
        call --name add_entry --arg project_id=1 --arg category=note --arg title=hi
"""
import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _parse_kv(items):
    out = {}
    for it in items or []:
        if '=' in it:
            k, v = it.split('=', 1)
            # 尽力转 int/float/true/false/null
            try:
                v = json.loads(v)
            except Exception:
                pass
            out[k] = v
    return out


async def run(url: str, token: str, sub: str, name: str, args_kv):
    headers = {"Authorization": f"Bearer {token}", "X-API-Key": token}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if sub == "list_tools":
                tools = await session.list_tools()
                print("== Tools ==")
                for t in tools.tools:
                    print(f"- {t.name}: {t.description or ''}")
                return
            if sub == "call":
                print(f"== call {name} {args_kv} ==")
                result = await session.call_tool(name, arguments=args_kv)
                for c in result.content:
                    if hasattr(c, 'text') and c.text:
                        print(c.text)
                if result.isError:
                    print("(tool returned error)")
                return
            raise SystemExit(f"未知子命令: {sub}")


def main():
    ap = argparse.ArgumentParser(description="RedTeam MCP 客户端示例")
    ap.add_argument("--url", default="http://127.0.0.1:5000/mcp")
    ap.add_argument("--token", required=True)
    ap.add_argument("sub", choices=["list_tools", "call"])
    ap.add_argument("--name", default="")
    ap.add_argument("--arg", action="append", default=[])
    a = ap.parse_args()
    asyncio.run(run(a.url, a.token, a.sub, a.name, _parse_kv(a.arg)))


if __name__ == "__main__":
    main()
