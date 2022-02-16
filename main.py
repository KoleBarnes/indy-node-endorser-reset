import json
import os
import requests
from dotenv import load_dotenv


from indy_vdr.ledger import (
    build_nym_request,
)
import util

# https://indyscan.io/api/networks/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte=321&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false

if __name__ == "__main__":
    load_dotenv()
    INDYSCAN_BASE_URL = "https://indyscan.io/api/networks/"
    ALLOW_DIDS_LIST = []
    seqno_gte = 264638 
    skipped_dids = []
    keyerror_list = []

    allow_dids_records = util.fetch_allow_dids()

    # util.debug(json.dumps(allow_dids_records, indent=2)) #! DEBUG PRINT

    for record in allow_dids_records["records"]:
        allow_did = record["fields"].get("DIDs")
        ALLOW_DIDS_LIST.append(allow_did)

    print("Starting scan. This may take a while ...")

    while True:
        # util.debug(f'Looking for seqNos greater than {seqno_gte}') #! DEBUG PRINT
        indyscan_response = requests.get(INDYSCAN_BASE_URL + f'/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false')
        indyscan_response = indyscan_response.json()
        # util.debug(json.dumps(indyscan_response, indent=2)) #! DEBUG PRINT
        if not indyscan_response:
            util.info("No more transactions at this time ...")
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
            # util.debug(f'Building nym request for {dest} ... SeqNo: {seqNo} Role: {role} Verkey: {verkey}') #! DEBUG PRINT

            #TODO Write txn to remove role here
            # req = build_nym_request(dest=dest, verkey=verkey, role="")
            # pool_response = pool.submit_request(req)

            #TODO Print txn
            # print(pool_reponse)            

            #TODO Submit txn Here

        seqno_gte = seqNo + 1 # Get the last seqNo from the last indyscan response

    if skipped_dids:
        util.log(f'{len(skipped_dids)} allowed DIDs. \n{skipped_dids}')
    if keyerror_list:
        util.log(f'{len(keyerror_list)} keyerrors found. \n{keyerror_list}')
