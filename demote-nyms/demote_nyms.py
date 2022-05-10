import time
import json
import csv
import glob
import os
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from indy_vdr.ledger import (
    build_get_nym_request,
    build_nym_request,
    build_custom_request,
    build_get_txn_request,
    build_get_txn_author_agreement_request,
    prepare_txn_author_agreement_acceptance,
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
    def __init__(self, verbose, network, DEMOTE, role: int, batch: int, pool_collection: PoolCollection):
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

    async def submit_pool_request(self, pool, request):
        attempt = 3
        while attempt:
            try:
                data = await pool.submit_request(request)
                return data
            except BaseException as e:
                util.warning("Unable to submit pool request. Trying again ...")
                util.warning(e)
                pool_status = await pool.get_status()
                print(pool_status)
                if not attempt:
                    util.fail("Unable to submit pool request.  3 attempts where made.  Exiting ...")
                    exit()
                attempt -= 1
                time.sleep(10)
                continue

    async def get_nym(self, pool, nym):
        """
        Get NYM request
        """
        attempt = 3
        while attempt:
            try:
                req = build_get_nym_request(None, nym)
                return await pool.submit_request(req)
            except BaseException as e:
                util.warning("Get NYM Function")
                util.warning("Unable to submit pool request. Trying again ...")
                print(e)
                attempt -= 1
                if not attempt:
                    util.fail("Unable to submit pool request.  3 attempts where made.  Exiting ...")
                    exit()
                time.sleep(10)
                continue

    async def get_txn(self, pool, seq_no: int):
        req = build_get_txn_request(None, LedgerType.DOMAIN, seq_no)
        return await self.submit_pool_request(pool, req)

    async def demote_nym(self, pool, author_agreement, ident: DidKey, dest):
        """
        Uses build_nym_request to demote NYM.
        """
        #print("DEMOTING DID!!!")
        attempt = 3
        while attempt:
            try:
                nym_build_req = build_nym_request(ident.did, dest)
                nym_build_req_body = json.loads(nym_build_req.body)
                #* Debug util.log_debug(json.dumps(nym_build_req_body, indent=2))

                nym_build_req_body["operation"]["role"] = None
                custom_req = build_custom_request(nym_build_req_body)
                custom_req.set_txn_author_agreement_acceptance(author_agreement)
                #* Debug util.log_debug(json.dumps(json.loads(custom_req.body), indent=2))

                ident.sign_request(custom_req)
                #* Debug util.log_debug(json.dumps(json.loads(custom_req.body), indent=2))
                return await pool.submit_request(custom_req)
            except BaseException as e:
                util.warning("Demote NYM Function")
                util.warning("Unable to submit pool request. Trying again ...")
                print(e)
                attempt -= 1
                if not attempt:
                    util.fail("Unable to submit pool request.  3 attempts where made.  Exiting ...")
                    exit()
                time.sleep(10)
                continue

    async def demote(self, network: Network, ident: DidKey):
        """
        Scans for NYMs in txns with endorser roll to get info or demoted.
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

        # Build resquests Session with retry.
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=1)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

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

        allow_dids_records = util.fetch_allow_dids()
        #* Debug util.log_debug(json.dumps(allow_dids_records, indent=2))
        for record in allow_dids_records['records']:
            allow_did = record['fields'].get('DIDs').strip()
            ALLOW_DIDS_LIST.append(allow_did)

        pool, network_name = await self.pool_collection.get_pool(network.id)
        taa_request = build_get_txn_author_agreement_request()
        taa = await self.submit_pool_request(pool, taa_request)
        taa_text = taa['data']['text']
        taa_version = taa['data']['version']
        taa_digest = taa['data']['digest']
        author_agreement = prepare_txn_author_agreement_acceptance(text=taa_text, version=taa_version, taa_digest=taa_digest, mechanism='for_session')

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
            util.info(f'Looking for seqNos greater than {seqno_gte} ...')
            
            indyscan_nym_url = f"{self.INDYSCAN_BASE_URL}{network.indy_scan_network_id}/ledgers/domain/txs?seqNoGte={seqno_gte}&filterTxNames=[%22NYM%22]&search='{self.role}'&sortFromRecent=false"
            with session.get(indyscan_nym_url) as nym_response:
                indyscan_nym_response = nym_response.json()

            print(indyscan_nym_url)  #* Debug 
            #* Debug util.log_debug(json.dumps(indyscan_nym_response, indent=2)) 

            if network_name == "Local von-network":
                if seqNo + 1 == seqno_gte:
                    util.log_debug('End of local txn ... ')
                    break
            
            # Add NYM's DID with specified role, append them to a list to check current state from ledger.
            if indyscan_nym_response:
                for item in indyscan_nym_response:
                    seqNo = item['imeta']['seqNo']
                    did = item['idata']['expansion']['idata']['txn']['data']['dest']
                    list_of_dids.append(did)
            else:
                util.info("No more transactions at this time ...")
                break

            util.info(f'Found {len(list_of_dids)} DIDs with role = {self.role} ...')

            # Iterate through list_of_dids and check the current state on the ledger. Get info and demote if not allowed. 
            demoted_dids_dict = {}
            for did in list_of_dids:
                # Check DID state from ledger. Gather info.
                # Get NYM info
                nym_response = await self.get_nym(pool, did)
                nym_check = json.loads(nym_response['data']) # Remove json encoding
                ledger_seqNo = nym_check['seqNo']
                did = nym_check['dest']
                role = nym_check['role']
                if role == None:
                    util.log_debug(f'{did} has been demoted to an Author role at {ledger_seqNo}. Skipping ...')
                    continue
                    role_alias = 'AUTHOR'
                elif role == '0':
                    role_alias = 'TRUSTEE'
                elif role == '2':
                    role_alias = 'STEWARD'
                elif role == '101':
                    role_alias = 'ENDORSER'
                elif role == '201':
                    role_alias = 'NETWORK_MONITOR'

                txnTime = nym_check['txnTime']
                identifier = nym_check['identifier']
                if txnTime:
                    txn_date_time = datetime.datetime.fromtimestamp(txnTime)
                else: 
                    txn_date_time = txnTime

                if not self.DEMOTE:
                    util.log_debug('Not Demoting. Looking for information and posting to csv log.')
                    # Get transaction info for alias.
                    txn_response = await self.get_txn(pool, ledger_seqNo)
                    if 'alias' in txn_response['data']['txn']['data']:
                        alias = txn_response['data']['txn']['data']['alias']
                    else:
                        alias = None

                    # Get endpoint from ATTRIB transaction.
                    indyscan_attrib_url = f'{self.INDYSCAN_BASE_URL}{network.indy_scan_network_id}/ledgers/domain/txs?filterTxNames=[%22ATTRIB%22]&search={did}&sortFromRecent=true'
                    with session.get(indyscan_attrib_url) as attrib_response:
                        indyscan_attrib_response = attrib_response.json()
                    #* Debug print(indyscan_attrib_url)
                    #* Debug util.log_debug(json.dumps(indyscan_attrib_response, indent=2)) 

                    # Default endpoint to None
                    endpoint = None
                    if indyscan_attrib_response:
                        txn = indyscan_attrib_response[0]['idata']['expansion']['idata']['txn']['data']
                        if 'endpoint' in txn:
                            endpoint = txn['endpoint']

                    # Write data to csv file.
                    row = (ledger_seqNo, did, role_alias, alias, endpoint, txn_date_time, identifier)
                    #* Debug print(row)
                    csv_file_path = f'{self.log_path}log.csv'
                    with open(csv_file_path,'a') as csv_file:
                        writer = csv.writer(csv_file, delimiter=',', quotechar='"',escapechar='~', quoting=csv.QUOTE_NONE)
                        writer.writerow(row)
                    util.info(f'Info from {did} collected in CSV log.')

                # Skip Allowed DID's
                if did in ALLOW_DIDS_LIST:
                    if did not in skipped_dids_list:
                        skipped_dids_list.append(did)
                    util.info(f'Found Allow DID: {did} Skipping ...')
                    
                    # Write data to csv file.
                    row = (None, did, None, None, 'SKIPPED')
                    #* Debug print(row)
                    csv_file_path = f'{self.log_path}DEMOTED.csv'
                    with open(csv_file_path,'a') as csv_file:
                        writer = csv.writer(csv_file, delimiter=',', quotechar='"',escapechar='~', quoting=csv.QUOTE_NONE)
                        writer.writerow(row)
                    continue

                # Demote if condisions allow. Collect the seqNo of the demote transaction and the DID that was demoted.
                if self.DEMOTE and self.role == '101': # Check to avoid accidental demotion.
                    #* Debug util.log_debug(f'DEMOTING DIDs with {self.role} ...')
                    # Demote if not allowed and role is set as endorsor. 
                    if nym_check['role'] == "101":
                        util.info(f'Building demote request for: {did} SeqNo: {ledger_seqNo} Role: {role} ...')
                    else:
                        util.log_debug(f'{did} Not endorser. Role: {role} ...')
                        continue

                    demote_nym_reponse = await self.demote_nym(pool, author_agreement, ident, did)
                    #* Debug util.log_debug(json.dumps(demote_nym_reponse, indent=2))
                    new_txn_seqNo = demote_nym_reponse['txnMetadata']['seqNo']
                    demoted_dids_dict['new_txn_seqno'] = new_txn_seqNo
                    demoted_dids_dict['did'] = did
                    demoted_dids_list.append(demoted_dids_dict.copy())

                    # Write data to csv file.
                    row = (ledger_seqNo, did, role, new_txn_seqNo, 'DEMOTED')
                    #* Debug print(row)
                    csv_file_path = f'{self.log_path}DEMOTED.csv'
                    with open(csv_file_path,'a') as csv_file:
                        writer = csv.writer(csv_file, delimiter=',', quotechar='"',escapechar='~', quoting=csv.QUOTE_NONE)
                        writer.writerow(row)
                    util.info(f'Info from {did} collected in CSV DEMOTED log.')
                
                if self.batch != -1:
                    if self.batch == 1:
                        util.log("Hit batch limit ...")
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
        #util.write_to_file(new_file_path, result) #!REMOVE COMMENT

        return result