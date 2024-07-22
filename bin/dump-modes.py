#!/usr/bin/env python3
import sys
import requests
import hashlib
import binascii
import pprint

from franklinwh import TokenFetcher, Client

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: {} email password gatewayid".format(sys.argv[0]))
        sys.exit(1)
    fetcher = TokenFetcher(sys.argv[1], sys.argv[2])
    gateway = sys.argv[3]
    client = Client(fetcher, gateway)

    pprint.pprint(client._switch_status())




