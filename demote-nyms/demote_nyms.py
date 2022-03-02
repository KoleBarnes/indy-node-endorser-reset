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
import datetime

class DemoteNyms(object, metaclass=Singleton):
    """
    DemoteNyms Class
    """
    def __init__(self, verbose, pool_collection: PoolCollection):
        self.verbose = verbose
        self.pool_collection = pool_collection
        self.log_path = "./logs/"
        self.json_log = "json_data.json"

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
        util.log_debug(json.dumps(nym_build_req_body, indent=2)) #* Debug

        nym_build_req_body = json.loads(nym_build_req.body)
        nym_build_req_body["operation"]["role"] = None
        custom_req = build_custom_request(nym_build_req_body)
        util.log_debug(json.dumps(json.loads(custom_req.body), indent=2)) #* Debug

        ident.sign_request(custom_req)
        util.log_debug(json.dumps(json.loads(custom_req.body), indent=2)) #* Debug
        return await pool.submit_request(custom_req)

    async def demote(self, network: Network, ident: DidKey):
        """
        Scans for NYMs in txns with endorser roll and demotes then skiping allowed DIDs.
        """
        INDYSCAN_BASE_URL = network.indy_scan_base_url # read in as base url from networks.json
        ALLOW_DIDS_LIST = []

        result = {}
        skipped_dids_list = []
        keyerror_list = []
        demoted_dids_list = []
        demoted_dids_dict = {}
        seqNo = 0

        if os.path.exists(f'{self.log_path}{self.json_log}'):
            util.info('Found log file! Getting last fetched seqNo!')
            data = util.read_from_file(self.log_path, self.json_log)
            if data:
                seqno_gte = data['last_seqNo']
            else:
              seqno_gte = 0  
        else:
            seqno_gte = 0
        util.info(f'Looking for transaction greater than: {seqno_gte}')

        allow_dids_records = util.fetch_allow_dids()
        util.log_debug(json.dumps(allow_dids_records, indent=2)) #* Debug

        for record in allow_dids_records['records']:
            allow_did = record['fields'].get('DIDs')
            ALLOW_DIDS_LIST.append(allow_did)

        pool, network_name = await self.pool_collection.get_pool(network.id)

        util.info("Starting scan. This may take a while ...")

        while True:
            util.log_debug(f'Looking for seqNos greater than {seqno_gte} ...')
            indyscan_response = requests.get(INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search=101&sortFromRecent=false')
            indyscan_response = indyscan_response.json()
            # util.log_debug(json.dumps(indyscan_response, indent=2)) #* Debug
            if not indyscan_response:
                util.info("No more transactions at this time ...")
                break

            if network_name == "Local von-network":
                if seqNo + 1 == seqno_gte:
                    util.log_debug('End of local txn ... ')
                    break

            for item in indyscan_response:
                try:
                    seqNo = item['imeta']['seqNo']
                    txn = item['idata']['expansion']['idata']['txn']['data']
                    dest = txn['dest']
                    role = txn['role']
                except KeyError as key:
                    util.log(f'Key Error: {key} seqNo:{seqNo} dest: {dest} role:{role}')
                    keyerror_list.append(seqNo)
                if dest in ALLOW_DIDS_LIST:
                    skipped_dids_list.append(dest)
                    util.info(f'Found Allow DID: {dest} Skipping ...')
                    continue

                nym_response = await self.get_nym(pool, dest)
                nym_check = json.loads(nym_response['data']) # Remove json encoding
                if nym_check['role'] == "101":
                    util.info(f'Building demote request for: {dest} SeqNo: {seqNo} Role: {role} ...')
                else:
                    util.log_debug(f'{dest} Not endorser.')
                    continue

                demote_nym_reponse = await self.demote_nym(pool, ident, dest)
                new_txn_seqNo = demote_nym_reponse['txnMetadata']['seqNo']
                demoted_dids_dict['new_txn_seqno'] = new_txn_seqNo
                demoted_dids_dict['did'] = dest
                demoted_dids_list.append(demoted_dids_dict.copy())
                #util.log_debug(json.dumps(demote_nym_reponse, indent=2)) #* Debug

            seqno_gte = seqNo + 1 # Get the last seqNo from the last indyscan response

        result['executing_did'] = ident.did
        result['time'] = str(datetime.datetime.now())
        result['last_seqNo'] = seqNo + 1
        if skipped_dids_list:
            result['allow_dids'] = {'count': len(skipped_dids_list), 'dids': skipped_dids_list}
        if keyerror_list:
            result['errors'] = {'count': len(keyerror_list), 'keyword': keyerror_list}
        if demoted_dids_list:
            result['demoted_dids'] = {'count': len(demoted_dids_list), 'dids': demoted_dids_list}
        util.write_to_file(self.log_path, self.json_log, result)

        return result

