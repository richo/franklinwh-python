#!/usr/bin/env python
# ruff: noqa: D100, T201
import sys

from franklinwh import TokenFetcher

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} email password")
        sys.exit(1)
    token = TokenFetcher.login(sys.argv[1], sys.argv[2])
    print("Your token is")
    print(f"  {token}")
    print("Use this in your hass config")
