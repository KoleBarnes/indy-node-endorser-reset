import json
import requests

from indy_vdr.ledger import (
    build_nym_request,
)

# https://indyscan.io/api/networks/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte=321&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false

BASE_URL = "https://indyscan.io/api/networks/"

if __name__ == "__main__":
    seqNo_Gte = 279500

    while True:
        print(f'\033[1;92;40mLooking for seqNos greater than {seqNo_Gte}\033[0m\n')
        indyscan_response = requests.get(BASE_URL + f'/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte={seqNo_Gte}&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false')
        indyscan_response = indyscan_response.json()
        # print(json.dumps(indyscan_response, indent=2))
        if not indyscan_response:
            print("\033[1;92;40mNo more transactions at this time ...\033[0m\n")
            break

        for item in indyscan_response:
            seqNo = item["imeta"]["seqNo"]
            dest = item["idata"]["expansion"]["idata"]["txn"]["data"]["dest"]
            role = item["idata"]["expansion"]["idata"]["txn"]["data"]["role"]
            verkey = item["idata"]["expansion"]["idata"]["txn"]["data"]["verkey"]
            # print(seqNo, dest, role, verkey)

            # for dest_allow in dest_allow_list:
                # if dest_allow != dest: 
                 # Build the NYM request ...
                # print(f'Skiping dest: {dest} as it is in the allow list ...')
            
            print(f'Building nym request for {dest} ... SeqNo: {seqNo} Role: {role} Verkey: {verkey}')

            #TODO Write txn to remove role here
            # req = build_nym_request(dest=dest, verkey=verkey, role="")
            # pool_response = pool.submit_request(req)
            
            #TODO Print txn
            # print(pool_reponse)            

            #TODO Submit txn Here
            
        seqNo_Gte = seqNo + 1 # Get the last seqNo from the last indyscan response