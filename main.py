import json
import requests

from indy_vdr.ledger import (
    build_nym_request,
)

# https://indyscan.io/api/networks/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte=321&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false

BASE_URL = "https://indyscan.io/api/networks/"

if __name__ == "__main__":
    seqNo_Gte = 259500

    while True:
        print(f'\033[1;92;40mLooking for seqNos greater than {seqNo_Gte}\033[0m\n')
        response = requests.get(BASE_URL + f'/SOVRIN_STAGINGNET/ledgers/domain/txs?seqNoGte={seqNo_Gte}&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false')
        response = response.json()
        
        # print(json.dumps(response, indent=2))

        if not response:
            print("\033[1;92;40mNo more transactions at this time ...\033[0m\n")
            break

        for item in response:
            seqNo = item["imeta"]["seqNo"]
            dest = item["idata"]["expansion"]["idata"]["txn"]["data"]["dest"]
            role = item["idata"]["expansion"]["idata"]["txn"]["data"]["role"]
            verkey = item["idata"]["expansion"]["idata"]["txn"]["data"]["verkey"]
            print(seqNo, dest, role, verkey)

            # Write txn to remove role here
            # Print txn
            # Submit txn Here

            seqNo_Gte = seqNo + 1 # Get the last seqNo from the last response