import sys
import pprint
from franklinwh import Client, TokenFetcher

def main(argv):
    username = argv[1]
    password = argv[2]
    gateway = argv[3]

    fetcher = TokenFetcher(username, password)
    client = Client(fetcher, gateway)
    pprint.pprint(client.get_stats())


if __name__ == "__main__":
    main(sys.argv)
