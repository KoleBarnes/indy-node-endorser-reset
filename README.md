# indy-node-endorser-reset

Indy Node Endorser Reset is a tool used to reset NYM's with an endorsor role on a given network.

## How It Works

Indy Node Endorser Reset collects transactions where a NYM's role is set as endorsers using the [indy scan API](https://github.com/Patrik-Stas/indyscan). Compares it with an allow list (in this instance we are using airtable) to skip certain DID's. It then checks the NYM's on the ledger to comfirm it's role and creates a transaction to set that NYM's role to none. Returns results.

## How To Use 

### Clone the indy-node-monitor repo

Run these commands to clone this repo so that you can run the script.

```bash
git clone 
cd indy-node-endorser-reset/demote_nyms
```

### Run the Script

For a full list of script options run:
``` bash
./run.sh -h
```

To get the details for the known networks available for use with the `--net` option, run:
``` bash
./run.sh --list-nets
```

To run the script, run the following command in your bash terminal from the `demote-nyms` folder in the `indy-node-endorser-reset` clone:
``` bash
IM=1 ./run.sh --net <netId> --seed <SEED>
```