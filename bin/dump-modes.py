#!/usr/bin/env python3
# ruff: noqa: D100, D103, T201
import asyncio
import pprint
import sys

from franklinwh import Client, TokenFetcher


async def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} email password gatewayId")
        sys.exit(1)
    fetcher = TokenFetcher(sys.argv[1], sys.argv[2])
    gateway = sys.argv[3]
    client = Client(fetcher, gateway)

    pprint.pprint(await client._switch_status())  # noqa: SLF001, T203


if __name__ == "__main__":
    asyncio.run(main())
