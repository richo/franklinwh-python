#!/usr/bin/env python
import sys
import requests
import hashlib
import binascii

from franklinwh import TokenFetcher
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 3:
        print("Usage: {} email password".format(sys.argv[0]))
        sys.exit(1)
    token = TokenFetcher.login(sys.argv[1], sys.argv[2])
    print("Your token is")
    print("  {}".format(token))
    print("Use this in your hass config")



