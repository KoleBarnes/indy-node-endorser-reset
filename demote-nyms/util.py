import json
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

    with requests.get(url, headers=headers, stream=True) as response:
        airtable_response = response.json()

    log("Got Airtable response. FOR STAGINGNET...")
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

def read_from_file(file_path):
    """
    Reads json file.
    
    Args:
        file_path: path of file. ex: ./[Path]/[File]
    """
    with open(f'{file_path}', 'r') as json_file:
        data = None
        try:
            data = json.load(json_file)
        except:
            log("No data in file. Continuing ...")
    return data

def write_to_file(file_path, result):
    """
    Writes results to json file.

    Args:
        file_path: path of file. ex: ./[Path]/[File]
        result: json serializable.
    """
    with open(f'{file_path}', 'w') as outfile:
        json.dump(result, outfile, indent=2)
        info('Result written to file.')
