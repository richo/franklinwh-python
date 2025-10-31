#!/usr/bin/env python3
# ruff: noqa: D100, T201
import pprint
import sys

from franklinwh import Client, TokenFetcher

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} email password gatewayId")
        sys.exit(1)
    fetcher = TokenFetcher(sys.argv[1], sys.argv[2])
    gateway = sys.argv[3]
    client = Client(fetcher, gateway)

    pprint.pprint(client._switch_status())  # noqa: SLF001, T203
