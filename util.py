from distutils.debug import DEBUG
import os
import requests
import sys
from DidKey import DidKey

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    DEBUG = '\033[35m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log(*args):
    # if verbose:
    print(*args, file=sys.stderr)

def info(*args):
    # if verbose:
    print(bcolors.OKGREEN)
    print(*args, bcolors.ENDC, file=sys.stderr)

def warning(*args):
    # if verbose:
    print(bcolors.WARNING)
    print(*args, bcolors.ENDC, file=sys.stderr)

def fail(*args):
    # if verbose:
    print(bcolors.FAIL)
    print(*args, bcolors.ENDC, file=sys.stderr)

def debug(*args):
    # if verbose:
    print(bcolors.DEBUG)
    print(*args, bcolors.ENDC, file=sys.stderr)

def fetch_allow_dids():
    """
    Builds airtable request using API Key and URL env varibles.
    """
    info("Building Airtable request ...")
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
        info("Airtable responded with empty response!")
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