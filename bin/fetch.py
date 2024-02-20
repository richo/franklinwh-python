import sys
import pprint
from franklinwh import Client

def main(argv):
    token = argv[1]
    gateway = argv[2]

    client = Client(token, gateway)
    # pprint.pprint(client.get_stats())
    # pprint.pprint(client.get_controllable_loads())
    # pprint.pprint(client.get_accessory_list())
    # pprint.pprint(client.get_equipment_list())
    pprint.pprint(client.get_smart_switch_state())


if __name__ == "__main__":
    main(sys.argv)
