import argparse
import asyncio
import json
import os
from dotenv import load_dotenv
from demote_nyms import DemoteNyms
from pool import PoolCollection
from networks import Networks
import util

if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch NYM transactions with endorser role and reset them.")
    parser.add_argument("--net", choices=Networks.get_ids(), help="Connect to a known network using an ID.")
    parser.add_argument("--list-nets", action="store_true", help="List known networks.")
    parser.add_argument("-s", "--seed", default=os.environ.get('SEED') , help="The privileged DID seed to use for the ledger requests.  Can be specified using the 'SEED' environment variable.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging.")
    args, unknown = parser.parse_known_args()

    util.enable_verbose(args.verbose, args.debug)

    if not args.seed:
        print("DID seed required to continue. Exiting ...")
        exit()
    else:
        did_seed = args.seed

    ident = util.create_did(did_seed)
    networks = Networks()
    pool_collection = PoolCollection(args.verbose, networks)
    network = networks.resolve(args.net)
    demote_nyms = DemoteNyms(args.verbose, pool_collection)
    result = asyncio.get_event_loop().run_until_complete(demote_nyms.demote(network, ident))

    print(json.dumps(result, indent=2))