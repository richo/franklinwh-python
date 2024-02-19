import sys
import pprint
from franklinwh import Client

def main(argv):
    token = argv[1]
    gateway = argv[2]

    client = Client(token, gateway)
    pprint.pprint(client.get_stats())


if __name__ == "__main__":
    main(sys.argv)
