import os
import sys
import requests
from DidKey import DidKey

verbose = False
debug = False

def enable_verbose(args_verbose, args_debug):
    global verbose
    global debug
    verbose = args_verbose
    debug = args_debug

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92mINFO: '
    DEBUG = '\033[35mDEBUG: '
    WARNING = '\033[93mWARNING: '
    FAIL = '\033[91mERROR: '
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log(*args):
    if verbose:
        print(*args, file=sys.stderr)

def info(*args):
    if verbose:
        join_args = "".join(args)
        built_str = bcolors.OKGREEN + join_args + bcolors.ENDC
        print(built_str, file=sys.stderr)

def warning(*args):
    if verbose:
        join_args = "".join(args)
        built_str = bcolors.WARNING + join_args + bcolors.ENDC
        print(built_str, file=sys.stderr)

def fail(*args):
    if verbose:
        join_args = "".join(args)
        built_str = bcolors.FAIL + join_args + bcolors.ENDC
        print(built_str, file=sys.stderr)

def log_debug(*args):
    if verbose and debug:
        join_args = "".join(args)
        built_str = bcolors.DEBUG + join_args + bcolors.ENDC
        print(built_str, file=sys.stderr)

def fetch_allow_dids():
    """
    Builds airtable request using API Key and URL env varibles.
    """
    log("Building Airtable request ...")
    AIRTABLE_API_KEY = os.environ.get('Airtable_API_Key')
    STAGING_ALLOW_DID_URL = os.environ.get('Airtable_Stagingnet_DIDs_URL')

    headers = {"Authorization": "Bearer " + AIRTABLE_API_KEY}
    allow_did_records = get_records(STAGING_ALLOW_DID_URL, headers)
    return allow_did_records

def get_records(url, headers):
    """
    fetches airtable request.

    Args:
        url: airtable sheet URL.
        headers: API Key.
    """
    print('Submitting Airtable request ...')
    response = requests.get(url, headers=headers)
    airtable_response = response.json()
    has_items = bool(airtable_response["records"])
    if not has_items:
        warning("Airtable responded with empty response!")
    return airtable_response

def create_did(seed):
    ident = None
    if seed:
        try:
            ident = DidKey(seed)
            log("DID:", ident.did, " Verkey:", ident.verkey)
        except:
            log("Invalid seed. Valid seed needed to continue. Exiting ... ")
            exit()
    return ident

def get_last_seqNo():
    f = open("LastSeqNo.txt", "r")
    last_seqNo = f.read()
    f.close()
    return last_seqNo

def write_last_seqNo(lastSeqNo):
    # try:
    f = open("LastSeqNo.txt", "w")
    f.write(lastSeqNo)
    f.close()
    # except:
    #     fail(f'Could not save last seqNo to file!')
    # else: 
    #     info("Last seqNo written to file.")
