#!/usr/bin/env python
import sys
import pprint
import time
from franklinwh import Client, CachingThread, TokenFetcher

def main(argv):
    token = argv[1]
    gateway = argv[2]


    username = argv[1]
    password = argv[2]
    gateway = argv[3]

    fetcher = TokenFetcher(username, password)
    client = Client(fetcher, gateway)
    thread = CachingThread(client)
    pprint.pprint(thread.get_stats())
    time.sleep(10)
    pprint.pprint(thread.get_stats())



if __name__ == "__main__":
    main(sys.argv)

