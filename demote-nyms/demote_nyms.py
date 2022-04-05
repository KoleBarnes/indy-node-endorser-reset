import json
import csv
import glob
import os
import requests
from indy_vdr.ledger import (
    build_get_nym_request,
    build_nym_request,
    build_custom_request,
    build_get_txn_request,
    LedgerType,
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
    def __init__(self, verbose, network, DEMOTE, role, batch: int, pool_collection: PoolCollection):
        self.verbose = verbose
        self.INDYSCAN_BASE_URL = network.indy_scan_base_url
        self.DEMOTE = DEMOTE
        self.role = role
        if batch: self.batch = int(batch)
        else: self.batch = -1
        self.pool_collection = pool_collection
        self.log_path = f'./logs/{network.name}/'

        # Create directory.
        if not os.path.exists(self.log_path):
            os.mkdir(self.log_path)
            print(f'Directory {self.log_path} created ...')

    async def get_nym(self, pool, nym):
        """
        Get NYM request
        """
        req = build_get_nym_request(None, nym)
        return await pool.submit_request(req)

    async def get_txn(self, pool, seq_no: int):
        req = build_get_txn_request(None, LedgerType.DOMAIN, seq_no)
        return await pool.submit_request(req)

    async def demote_nym(self, pool, ident: DidKey, dest):
        """
        Uses build_nym_request to demote NYM.
        """
        print("DEMOTING DID!!!")
        nym_build_req = build_nym_request(ident.did, dest)
        nym_build_req_body = json.loads(nym_build_req.body)
        #* Debug util.log_debug(json.dumps(nym_build_req_body, indent=2))

        nym_build_req_body = json.loads(nym_build_req.body)
        nym_build_req_body["operation"]["role"] = None
        custom_req = build_custom_request(nym_build_req_body)
        #* Debug util.log_debug(json.dumps(json.loads(custom_req.body), indent=2))

        ident.sign_request(custom_req)
        #* Debug util.log_debug(json.dumps(json.loads(custom_req.body), indent=2))
        return await pool.submit_request(custom_req)

    async def demote(self, network: Network, ident: DidKey):
        """
        Scans for NYMs in txns with endorser roll and sends a list of DID'd to iterate() to get demoted.
        """
        ALLOW_DIDS_LIST = []

        result = {}
        seqNo = 0
        seqno_gte = 0
        data = None
        list_of_dids = []
        skipped_dids_list = []
        demoted_dids_list = []
        start_time = datetime.datetime.now()

        if not os.path.exists(f'{self.log_path}'):
            print("Log file not found. Please create folder ./logs and try again.")
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
        #* Debug util.log_debug(json.dumps(allow_dids_records, indent=2))
        for record in allow_dids_records['records']:
            allow_did = record['fields'].get('DIDs')
            ALLOW_DIDS_LIST.append(allow_did)

        pool, network_name = await self.pool_collection.get_pool(network.id)

        util.info("Starting scan. This may take a while ...")

        # Check Allow list DID's from previous run to see if they need to be removed. Append them to a list to check current state from ledger.
        util.info("Checking allow DIDs from local file ...")
        if data:
            util.info("Found allows from previous run. Checking to see if they are still allowed ...")
            if 'allow_dids' in data:
                for did in data['allow_dids']['dids']:
                    list_of_dids.append(did)
        else:
            util.info("No allow DIDs in local file ...")

        # Check IndyScan's transactions.
        util.info("Checking IndyScan Transactions ...")
        while True:
            # Get Nym transactions with specified role from indy scan
            util.log_debug(f'Looking for seqNos greater than {seqno_gte} ...')
            indyscan_response = requests.get(self.INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search={self.role}&sortFromRecent=false')
            indyscan_response = indyscan_response.json()
            #* Debug util.log_debug(json.dumps(indyscan_response, indent=2))

            if network_name == "Local von-network":
                if seqNo + 1 == seqno_gte:
                    util.log_debug('End of local txn ... ')
                    break
            
            # Add NYM's DID with specified role, append them to a list to check current state from ledger.
            if indyscan_response:
                for item in indyscan_response:
                    txn = item['idata']['expansion']['idata']['txn']['data']
                    did = txn['dest']
                    list_of_dids.append(did)
            else:
                util.info("No more transactions at this time ...")
                break

            # Iterate through list_of_dids and check the current state on the ledger. Get info and demote if not allowed. 
            demoted_dids_dict = {}
            for did in list_of_dids:
                # Check DID state from ledger. Gather info.
                # Get NYM info
                nym_response = await self.get_nym(pool, did)
                nym_check = json.loads(nym_response['data']) # Remove json encoding
                seqNo = nym_check['seqNo']
                did = nym_check['dest']
                role = nym_check['role']
                txnTime = nym_check['txnTime']
                txn_date_time = datetime.datetime.fromtimestamp(txnTime)  

                # Get transaction info for alias.
                txn_response = await self.get_txn(pool, seqNo)
                if 'alias' in txn_response['data']['txn']['data']:
                    alias = txn_response['data']['txn']['data']['alias']
                else:
                    alias = None

                # Get endpoint from ATTRIB transaction.
                indyscan_response = requests.get(self.INDYSCAN_BASE_URL + f'/{network.indy_scan_network_id}/ledgers/domain/txs?filterTxNames=[%22ATTRIB%22]&search={did}&sortFromRecent=true')
                indyscan_response = indyscan_response.json()
                #* Debug util.log_debug(json.dumps(indyscan_response, indent=2)) 

                if indyscan_response:
                    for item in indyscan_response:
                        txn = item['idata']['expansion']['idata']['txn']['data']
                        if 'endpoint' in txn:
                            endpoint = txn['endpoint']
                            break
                        else:
                            endpoint = None
                            break
                else:
                    endpoint = None

                if role == None:
                    role_alias = 'USER'
                elif role == '0':
                    role_alias = 'TRUSTEE'
                elif role == '2':
                    role_alias = 'STEWARD'
                elif role == '101':
                    role_alias = 'ENDORSER'
                elif role == '201':
                    role_alias = 'NETWORK_MONITOR'

                # Write data to csv file.
                row = (seqNo, did, role_alias, alias, endpoint, txn_date_time)
                csv_file_path = f'{self.log_path}log.csv'
                with open(csv_file_path,'a') as csv_file:
                    writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_NONE)
                    writer.writerow(row)
                util.info(f'Info from {did} collected in CSV log.')

                # Skip Allowed DID's
                if did in ALLOW_DIDS_LIST:
                    if did not in skipped_dids_list:
                        skipped_dids_list.append(did)
                    util.info(f'Found Allow DID: {did} Skipping ...')
                    continue

                # Demote if condisions allow. Collect the seqNo of the demote transaction and the DID that was demoted.
                if self.DEMOTE and self.role == '101': # Check to avoid accidental demotion.
                    
                    # Demote if not allowed and role is set as endorsor. 
                    if nym_check['role'] == "101":
                        util.info(f'Building demote request for: {did} SeqNo: {seqNo} Role: {role} ...')
                    else:
                        util.log_debug(f'{did} Not endorser. Role: {role} ...')
                        continue

                    demote_nym_reponse = await self.demote_nym(pool, ident, did)
                    #* Debug util.log_debug(json.dumps(demote_nym_reponse, indent=2))
                    new_txn_seqNo = demote_nym_reponse['txnMetadata']['seqNo']
                    demoted_dids_dict['new_txn_seqno'] = new_txn_seqNo
                    demoted_dids_dict['did'] = did
                    demoted_dids_list.append(demoted_dids_dict.copy())
                
                if self.batch != -1:
                    if self.batch == 1:
                        break
                    self.batch = self.batch - 1
                # End of for loop.

            if self.batch != -1 and self.batch == 1:
                util.log("Hit batch limit. Finishing up ...")
                break

            seqno_gte = seqNo + 1 # Get the last seqNo from the last indyscan response
            list_of_dids = []
            # end of while loop

        # Build Json Log
        end_time = datetime.datetime.now()
        result['start_time'] = str(start_time)
        result['end_time'] = str(end_time)
        result['time_delta'] = str(end_time - start_time)
        result['executing_did'] = ident.did
        if seqNo == 0:
            result['last_seqNo'] = seqno_gte
        else:
            result['last_seqNo'] = seqNo + 1
        if skipped_dids_list:
            result['allow_dids'] = {'count': len(skipped_dids_list), 'dids': skipped_dids_list }
        if demoted_dids_list:
            result['demoted_dids'] = {'count': len(demoted_dids_list), 'dids': demoted_dids_list }
        # if list_of_dids:
        #     result['list_of_dids'] = { 'count': len(list_of_dids), 'dids': list_of_dids }
        date_time = end_time.strftime("%Y-%m-%d--%H_%M_%S")
        new_file_path = f'{self.log_path}{date_time}.json'
        util.write_to_file(new_file_path, result)

        return result