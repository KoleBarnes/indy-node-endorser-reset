import json
import csv
import glob
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
    def __init__(self, verbose, network_url, DEMOTE, role, batch: int, pool_collection: PoolCollection):
        self.verbose = verbose
        self.INDYSCAN_BASE_URL = network_url
        self.DEMOTE = DEMOTE
        self.role = role
        if batch: self.batch = int(batch)
        else: self.batch = None
        self.pool_collection = pool_collection
        self.log_path = "./logs/"

    async def get_nym(self, pool, nym):
        """
        Get NYM request
        """
        req = build_get_nym_request(None, nym)
        return await pool.submit_request(req)

    async def demote_nym(self, pool, ident: DidKey, dest):
        """
        Uses build_nym_request to demote NYM.
        """
        pass
        print("DEMOTING DID!!!")
        nym_build_req = build_nym_request(ident.did, dest)
        nym_build_req_body = json.loads(nym_build_req.body)
        # util.log_debug(json.dumps(nym_build_req_body, indent=2)) #* Debug

        nym_build_req_body = json.loads(nym_build_req.body)
        nym_build_req_body["operation"]["role"] = None
        custom_req = build_custom_request(nym_build_req_body)
        # util.log_debug(json.dumps(json.loads(custom_req.body), indent=2)) #* Debug

        ident.sign_request(custom_req)
        # util.log_debug(json.dumps(json.loads(custom_req.body), indent=2)) #* Debug
        return await pool.submit_request(custom_req)

    async def iterate(self, pool, ident: DidKey, ALLOW_DIDS_LIST: list, seqNo, demoted_dids_list: list, skipped_dids_list: list, list_of_dids: list):
        """
        Iterate through list of DID's and demotes them skipping allowed DIDs
        """
        demoted_dids_dict = {}

        for did in list_of_dids:
            if did in ALLOW_DIDS_LIST:
                if did not in skipped_dids_list:
                    skipped_dids_list.append(did)
                util.info(f'Found Allow DID: {did} Skipping ...')
                continue

            nym_response = await self.get_nym(pool, did)
            nym_check = json.loads(nym_response['data']) # Remove json encoding
            seqNo = nym_check['seqNo']
            did = nym_check['dest']
            role = nym_check['role']
            txnTime = nym_check['txnTime']
            if 'alias' in nym_check:
                util.info('yes alias.')
                alias = nym_check['alias']
            else:
                alias = None

            # indyscan_response = requests.get(self.INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22ATTRIB%22]&search={did}&sortFromRecent=false')
            # indyscan_response = indyscan_response.json()
            # # util.log_debug(json.dumps(indyscan_response, indent=2)) #* Debug

            # if indyscan_response:
            #     for item in indyscan_response:
            #         txn = item['txn']['data']
            #         if endpoint in txn:
            #             endpoint = txn['endpoint']
            #         else:
            #             util.info("No end point.")
                        
            # else:
            #     util.info("No attrib ...")

            row = (seqNo, did, role, alias, txnTime)
            csv_file_path = self.log_path + 'CSVlog' + '.csv'
            with open(csv_file_path,'a') as csv_file:
                writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_NONE)
                writer.writerow(row)

            if nym_check['role'] == "101":
                util.info(f'Building demote request for: {did} SeqNo: {seqNo} Role: {role} ...')
            else:
                util.log_debug(f'{did} Not endorser. Role: {role} ...')
                continue

            if self.DEMOTE and self.role == '101': # Check to avoid accidental demotion.
                demote_nym_reponse = await self.demote_nym(pool, ident, did)
                # util.log_debug(json.dumps(demote_nym_reponse, indent=2)) #* Debug
                new_txn_seqNo = demote_nym_reponse['txnMetadata']['seqNo']
                demoted_dids_dict['new_txn_seqno'] = new_txn_seqNo
                demoted_dids_dict['did'] = did
                demoted_dids_list.append(demoted_dids_dict.copy())
            
            if self.batch:
                if self.batch == 0:
                    break
                self.batch = self.batch - 1

        return demoted_dids_list, skipped_dids_list, seqNo

    async def demote(self, network: Network, ident: DidKey):
        """
        Scans for NYMs in txns with endorser roll and sends a list of DID'd to iterate() to get demoted.
        """
        ALLOW_DIDS_LIST = []

        result = {}
        seqNo = 0
        seqno_gte = 0
        data = None
        skipped_dids_list = []
        demoted_dids_list = []
        start_time = datetime.datetime.now()

        if not os.path.exists(f'{self.log_path}'):
            print("Log file not found. Please create folder ./log and try again.")
            print("Exiting ... ")
            exit()

        list_of_files = glob.glob(f'{self.log_path}*.json')
        if list_of_files:
            latest_file_path = max(list_of_files, key=os.path.getctime)
            if os.path.exists(f'{latest_file_path}'):
                util.info('Found log file! Getting last fetched seqNo!')
                data = util.read_from_file(latest_file_path)
                if data:
                    seqno_gte = data['last_seqNo']
        else:
            util.info("No previous log files. Continuing ...") 

        util.info(f'Looking for transaction greater than: {seqno_gte}')

        allow_dids_records = util.fetch_allow_dids()
        # util.log_debug(json.dumps(allow_dids_records, indent=2)) #* Debug
        for record in allow_dids_records['records']:
            allow_did = record['fields'].get('DIDs')
            ALLOW_DIDS_LIST.append(allow_did)

        pool, network_name = await self.pool_collection.get_pool(network.id)

        util.info("Starting scan. This may take a while ...")
        # Check Allow list from previous run to see if they need to be removed.
        util.info("Checking allow DIDs from local file ...")
        if data:
            list_of_dids = []
            util.info("Found allows from previous run. Checking to see if they are still allowed ...")
            if 'allow_dids' in data:
                for did in data['allow_dids']['dids']:
                    list_of_dids.append(did)
                
            demoted_dids_list, skipped_dids_list, seqNo = await self.iterate(pool, ident, ALLOW_DIDS_LIST, seqno_gte, demoted_dids_list, skipped_dids_list, list_of_dids)
        else:
            util.info("No allow DIDs in local file ...")

        # Check IndyScan's transactions.
        util.info("Checking IndyScan Transactions ...")
        list_of_dids = []
        while True:
            util.log_debug(f'Looking for seqNos greater than {seqno_gte} ...')
            indyscan_response = requests.get(self.INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search={self.role}&sortFromRecent=false')
            #print(self.INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search={self.role}&sortFromRecent=false')
            indyscan_response = indyscan_response.json()
            #util.log_debug(json.dumps(indyscan_response, indent=2)) #* Debug

            if network_name == "Local von-network":
                if seqNo + 1 == seqno_gte:
                    util.log_debug('End of local txn ... ')
                    break

            if indyscan_response:
                for item in indyscan_response:
                    txn = item['idata']['expansion']['idata']['txn']['data']
                    did = txn['dest']
                    list_of_dids.append(did)
            else:
                util.info("No more transactions at this time ...")
                break
                
            demoted_dids_list, skipped_dids_list, seqNo = await self.iterate(pool, ident, ALLOW_DIDS_LIST, seqno_gte, demoted_dids_list, skipped_dids_list, list_of_dids)

            seqno_gte = seqNo + 1 # Get the last seqNo from the last indyscan response

        # Build Json Log
        end_time = datetime.datetime.now()
        result['start_time'] = str(start_time)
        result['end_time'] = str(end_time)
        result['time_delta'] = str(end_time - start_time)
        result['executing_did'] = ident.did
        result['last_seqNo'] = seqNo + 1
        if skipped_dids_list:
            result['allow_dids'] = {'count': len(skipped_dids_list), 'dids': skipped_dids_list }
        if demoted_dids_list:
            result['demoted_dids'] = {'count': len(demoted_dids_list), 'dids': demoted_dids_list }
        # if list_of_dids:
        #     result['list_of_dids'] = { 'count': len(list_of_dids), 'dids': list_of_dids }
        date_time = end_time.strftime("%Y-%m-%d--%H_%M_%S")
        new_file_path = self.log_path + date_time + '.json'
        util.write_to_file(new_file_path, result)

        return result