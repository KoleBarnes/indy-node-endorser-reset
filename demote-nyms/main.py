import argparse
import asyncio
import json
import os
import indy_vdr
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
    parser.add_argument("-s", "--seed", default=os.environ.get('SEED'), help="The privileged DID seed to use for the ledger requests.  Can be specified using the 'SEED' environment variable.")
    parser.add_argument("--DEMOTE", action="store_true", help="Enable demoting. Role of NYM required.")
    parser.add_argument("--role", default=os.environ.get('ROLE'), help="The role you are looking for. Role of 101 required for demoting. - None (common USER) - '0' (TRUSTEE) - '2' (STEWARD) - '101' (ENDORSER) - '201' (NETWORK_MONITOR)")
    parser.add_argument("--batch", default=os.environ.get('BATCH'), help="Number of NYM's you would like to go through.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging.")
    args, unknown = parser.parse_known_args()

    util.enable_verbose(args.verbose, args.debug)

    if not args.batch: args.batch = None
    
    did_seed = None if not args.seed else args.seed

    if args.DEMOTE: # Check to avoid accidental demotion.
        if not did_seed:
            print("DID seed required to Demote. Exiting ...")
            exit()
        if not args.role or args.role != '101':
            util.warning('Role flag must be set to endorsor ie: 101, to enable demoting!')
            print('exiting...')
            exit()
        Join = input(f"\033[93mWARNING: You are about to demote NYM's on network '{network.name}'! Do you wish to proceed? (y) to continue... \033[m").lower()
        if not Join.startswith('y'):
            print('exiting...')
            exit()

    util.log("indy-vdr version:", indy_vdr.version())
    ident = util.create_did(did_seed)
    networks = Networks()
    pool_collection = PoolCollection(args.verbose, networks)
    network = networks.resolve(args.net)

    demote_nyms = DemoteNyms(args.verbose, network, args.DEMOTE, args.role, args.batch, pool_collection)
    result = asyncio.get_event_loop().run_until_complete(demote_nyms.demote(network, ident))
    print(json.dumps(result, indent=2))