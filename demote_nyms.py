from contextlib import nullcontext
import json
import os
import requests
from indy_vdr.ledger import (
    build_get_nym_request,
    build_nym_request,
    build_custom_request
)
from networks import Network
from DidKey import DidKey
from pool import PoolCollection
from singleton import Singleton
import util

class DemoteNyms(object, metaclass=Singleton):
    """
    DemoteNyms Class
    """
    def __init__(self, verbose, pool_collection: PoolCollection):
        self.verbose = verbose
        self.pool_collection = pool_collection

    async def get_nym(self, pool, nym):
        """
        Get NYM request
        """
        req = build_get_nym_request(None, nym)
        return await pool.submit_request(req)

    async def demote_nym(self, pool, ident, dest):
        """
        Uses build_nym_request to demote NYM.
        """
        nym_build_req = build_nym_request(ident.did, dest)
        nym_build_req_body = json.loads(nym_build_req.body)
        nym_build_req_body["operation"]["role"] = ""
        custom_req = build_custom_request(nym_build_req_body)
        ident.sign_request(custom_req)
        return await pool.submit_request(custom_req)

    async def demote(self, network: Network, ident: DidKey): #, ident: DidKey
        """
        Scans for NYMs in txns with endorser roll and demotes then skiping allowed DIDs.
        """
        INDYSCAN_BASE_URL = network.indy_scan_base_url # read in as base url from networks.json
        ALLOW_DIDS_LIST = []

        seqNo = 0
        seqno_gte = 0

        skipped_dids = []
        keyerror_list = []

        allow_dids_records = util.fetch_allow_dids()
        # util.debug(json.dumps(allow_dids_records, indent=2)) #! Debug

        for record in allow_dids_records["records"]:
            allow_did = record["fields"].get("DIDs")
            ALLOW_DIDS_LIST.append(allow_did)

        pool, network_name = await self.pool_collection.get_pool(network.id)
        # util.debug(pool, network_name) #! Debug
        # nym_response = await self.getNYM(pool, self.nym)

        util.info("Starting scan. This may take a while ...")

        while True:
            #util.debug(f'Looking for seqNos greater than {seqno_gte}') #! Debug
            indyscan_response = requests.get(INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false')
            indyscan_response = indyscan_response.json()
            #util.debug(json.dumps(indyscan_response, indent=2)) #! Debug
            if not indyscan_response:
                util.info("No more transactions at this time ...")
                break

            if seqNo + 1 == seqno_gte:
                util.debug('_________________________break_________________________') #! Debug
                break

            for item in indyscan_response:
                try:
                    seqNo = item["imeta"]["seqNo"]
                    txn = item["idata"]["expansion"]["idata"]["txn"]["data"]
                    dest = txn["dest"]
                    role = txn["role"]
                    verkey = txn["verkey"]
                except KeyError as key:
                    print(f'Key Error: {key} seqNo:{seqNo} dest: {dest} role:{role} verkey: {verkey}')
                    keyerror_list.append(seqNo)
                if dest in ALLOW_DIDS_LIST:
                    skipped_dids.append(dest)
                    util.info(f'Found Allow DID: {dest} Skipping ...')
                    continue
                util.info(f'Building nym request for {dest} ... SeqNo: {seqNo} Role: {role} Verkey: {verkey}') #! Debug

                nym_response = await self.get_nym(pool, dest)
                nym_test = json.loads(nym_response["data"]) # Remove json encoding
                if nym_test["role"] == "101":
                    print("Is endorser!")
                else:
                    print("Not endorser.")
                    continue

                #TODO Write txn to remove role here
                # submitter_did = "V4SGRU86Z58d6TV7PBUe6f"
                demote_nym_reponse = await self.demote_nym(pool, ident, dest)
                print(demote_nym_reponse)

                exit() #! REMOVE

                #TODO Print txn
                # print(pool_reponse)            
 
                #TODO Submit txn Here

            seqno_gte = seqNo + 1 # Get the last seqNo from the last indyscan response

        if skipped_dids:
            util.log(f'{len(skipped_dids)} allowed DIDs. \n{skipped_dids}')
        if keyerror_list:
            util.log(f'{len(keyerror_list)} keyerrors found. \n{keyerror_list}')

