#!/usr/bin/env python
# ruff: noqa: D100, D103, T201
import asyncio
import sys

from franklinwh import TokenFetcher


async def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} email password")
        sys.exit(1)
    token = await TokenFetcher.login(sys.argv[1], sys.argv[2])
    print("Your token is")
    print(f"  {token}")
    print("Use this in your hass config")


if __name__ == "__main__":
    asyncio.run(main())
