#!/usr/bin/env python3
"""Get information about the FranklinHW installation."""

import argparse
import asyncio
import logging
import sys

from franklinwh import Client, TokenFetcher
import jsonpickle


def truthy(value: str) -> bool:
    """Convert a string to a boolean."""
    sure = ("yes", "true", "t", "y", "1", "on")
    nope = ("no", "false", "f", "n", "0", "off")
    if value.lower() in sure:
        return True
    if value.lower() in nope:
        return False
    raise argparse.ArgumentTypeError(
        "Boolean must be one of " + ", ".join(sure + nope) + "."
    )


async def main():
    """Do all the work."""
    parser = argparse.ArgumentParser(description="Get FranklinWH installation info.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "username",
        type=str,
        help="The username for the installation.",
    )
    parser.add_argument(
        "password",
        type=str,
        help="The password for the installation.",
    )
    parser.add_argument(
        "gateway",
        type=str,
        help="The gateway / serial number to query.",
    )
    parser.add_argument(
        "--merged",
        action=argparse.BooleanOptionalAction,
        help="Merge Circuits 1 and 2.",
    )
    parser.add_argument(
        "circuit",
        type=int,
        choices=range(1, 4),
        help="The circuit number to query.",
    )
    parser.add_argument("on", type=truthy, help="Turn on or off.")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig()
        logging.getLogger("franklinwh").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.DEBUG)

    fetcher = TokenFetcher(args.username, args.password)
    client = Client(fetcher, args.gateway)
    if args.merged is not None:
        await client.set_smart_circuits_merged(args.merged)
    await client.set_circuit(args.circuit, args.on)

    print(  # noqa: T201
        jsonpickle.dumps(
            await client.get_smart_circuits_enhanced(), indent=2, unpicklable=False
        )
    )

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
