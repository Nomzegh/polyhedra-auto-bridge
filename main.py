import time
from web3 import Web3
from contracts_abi import nft_abi, bridge_abi, bridge2_abi


# -------------------CONFIG--------------------------#
private_key = "PRIVATE_KEY"  # | Private key with 0x | Приватный ключ без 0x

sleep_between_tx = 1  # Seconds to sleep between each transactions.| Сколько ждать между каждой транзакцией.

BSC_RPC = "https://rpc.ankr.com/bsc"
POLYGON_RPC = "https://rpc.ankr.com/polygon"
CORE_RPC = "https://rpc.coredao.org"
CELO_RPC = "https://rpc.ankr.com/celo"
# CHOICES:
# 1. Approve in all networks
# 2. Bridge according path from path.txt
# 3. Calculate fees
# ---------------------------------------------------#

RPC_ARR = [BSC_RPC, POLYGON_RPC, CORE_RPC, CELO_RPC]

RPC_INFO = {
    BSC_RPC: {
        "name": "BSC",
        "contract": "0x87a218Ae43C136B3148A45EA1A282517794002c8",  # NFT panda contract in bsc
        "chainId": 56,
        "bridge1": "0x3668c325501322CEB5a624E95b9E16A019cDEBe8",  # bridge1 no claim needed
        "bridge2": "0xE09828f0DA805523878Be66EA2a70240d312001e",  # bridge2 claim needed (combo, opbnb)
    },
    POLYGON_RPC: {
        "name": "POLYGON",
        "contract": "0x141A1fb33683C304DA7C3fe6fC6a49B5C0c2dC42",  # NFT panda contract in pol
        "chainId": 137,
        "bridge1": "0xFFdF4Fe05899C4BdB1676e958FA9F21c19ECB9D5",  # bridge1 no claim needed
        "bridge2": "0x2E953a70C37E8CB4553DAe1F5760128237c8820D",  # bridge2 claim needed (combo, opbnb)
    },
    CORE_RPC: {
        "name": "CORE",
        "contract": "0x36e5121618c0Af89E81AcD33B6b8F5CF5cDD961a",  # same description as above...
        "chainId": 1116,
        "bridge1": "0x3701c5897710F16F1f75c6EaE258bf11Ee189a5d",  # ...
        "bridge2": "0x5c5979832A60c17bB06676fa906bEdD1A013e18c",  # ...
    },
    CELO_RPC: {
        "name": "CELO",
        "contract": "0xb404e5233aB7E426213998C025f05EaBaBD41Da6",
        "chainId": 42220,
        "bridge1": "0xe47b0a5F2444F9B360Bd18b744B8D511CfBF98c6",
        "bridge2": "0x24339b7f8d303527C8681382AbD4Ec299757aF63",
    },
}


# Dict of all chain ids
CHAIN_IDS_L0 = {
    "bsc": 102,
    "pol": 109,
    "celo": 125,
    "core": 153,
    "mantle": 181,
    "combo": 114,
    "opbnb": 116,
}


# Mint function
def mint(rpc, private_key):
    web3 = Web3(Web3.HTTPProvider(rpc))
    account = web3.eth.account.from_key(private_key)
    transaction = {
        "to": web3.to_checksum_address(
            RPC_INFO[rpc]["contract"]
        ),  # nft contract from main dict
        "value": 0,
        "gasPrice": web3.eth.gas_price,
        "gas": 260000,  # increase if out of gas
        "data": "0x1249c58b",  # hex object id (mint)
        "nonce": web3.eth.get_transaction_count(account.address),
        "chainId": RPC_INFO[rpc]["chainId"],
    }

    signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
    transaction_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    receipt = web3.eth.wait_for_transaction_receipt(transaction_hash)

    if receipt.status != 1:
        print(f"Transaction {transaction_hash.hex()} failed!")
        return

    network_name = RPC_INFO[rpc]["name"]
    print(f"[{network_name}] Mint hash: {transaction_hash.hex()}")
    time.sleep(sleep_between_tx)


# bridge function for networks where claim is not needed
def bridge_nft(rpc, private_key, tokenId, recipientChain):
    web3 = Web3(Web3.HTTPProvider(rpc))
    account = web3.eth.account.from_key(private_key)

    chain_id = CHAIN_IDS_L0[recipientChain]
    bridge_contract = web3.eth.contract(RPC_INFO[rpc]["bridge1"], abi=bridge_abi)
    reversed_dict = {
        v: k for k, v in CHAIN_IDS_L0.items()
    }  # reverse dict to return network name in "return"

    fee = estimate_fees(rpc, private_key, tokenId, recipientChain)  # estimate fees

    if fee > 0:  # if fee found, :
        transaction = bridge_contract.functions.transferNFT(
            RPC_INFO[rpc]["contract"],  # nft contract
            tokenId,
            chain_id,
            account.address,
            "0x00010000000000000000000000000000000000000000000000000000000000055730",  # adapter params (present almost in every tx)
        ).build_transaction(
            {
                "nonce": web3.eth.get_transaction_count(account.address),
                "from": account.address,
                "value": fee,
                "gasPrice": web3.eth.gas_price,
                "chainId": RPC_INFO[rpc]["chainId"],
            }
        )

        signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
        transaction_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(transaction_hash)

        if receipt.status != 1:
            print(f"Transaction {transaction_hash.hex()} failed!")
            return

        network_name = RPC_INFO[rpc]["name"]  # assign shortened network name from dict
        to_network = reversed_dict.get(chain_id, None)
        print(
            f"Bridged from [{network_name}] to [{to_network}]: {transaction_hash.hex()}"
        )
        print(f"Waiting {sleep_between_tx} seconds...")
        time.sleep(sleep_between_tx)  # wait 30 seconds. Optimal value is 20-30 seconds.
    else:
        pass


# Function for nft, which has to be claimed after bridge (combo, opbnb)
def bridge_nft_claimable(rpc, private_key, tokenId, recipientChain):
    web3 = Web3(Web3.HTTPProvider(rpc))
    account = web3.eth.account.from_key(private_key)
    address = str(account.address)
    chain_id = CHAIN_IDS_L0[recipientChain]
    bridge_contract = web3.eth.contract(RPC_INFO[rpc]["bridge2"], abi=bridge2_abi)
    reversed_dict = {v: k for k, v in CHAIN_IDS_L0.items()}

    fee_wei = bridge_contract.functions.fee(
        chain_id
    ).call()  # now "fee" instead of "estimateFee", because it's another contract

    if fee_wei > 0:
        transaction = bridge_contract.functions.transferNFT(
            RPC_INFO[rpc]["contract"],
            tokenId,
            chain_id,
            "0x000000000000000000000000"
            + address[2:],  # recipient address must be in "bytes" type
        ).build_transaction(
            {
                "nonce": web3.eth.get_transaction_count(account.address),
                "from": account.address,
                "value": fee_wei,
                "gasPrice": web3.eth.gas_price,
                "chainId": RPC_INFO[rpc]["chainId"],
            }
        )

        signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
        transaction_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(transaction_hash)

        if receipt.status != 1:
            print(f"Transaction {transaction_hash.hex()} failed!")
            return

        network_name = RPC_INFO[rpc]["name"]
        to_network = reversed_dict.get(chain_id, None)

        print(
            f"Bridged from [{network_name}] to [{to_network}]: {transaction_hash.hex()}"
        )
        print(f"Waiting {sleep_between_tx} seconds...")
        time.sleep(sleep_between_tx)
    else:
        pass


# Approve function. Approves all 6 nfts in each network. Approves ONLY "contract" addresses from main dict.
def approve_for_all(rpc, private_key, bridge, bridge_num):
    web3 = Web3(Web3.HTTPProvider(rpc))
    account = web3.eth.account.from_key(private_key)
    nft_contract = web3.eth.contract(
        web3.to_checksum_address(RPC_INFO[rpc]["contract"]), abi=nft_abi
    )
    transaction = nft_contract.functions.setApprovalForAll(
        web3.to_checksum_address(bridge), True
    ).build_transaction(
        {
            "nonce": web3.eth.get_transaction_count(account.address),
            "from": account.address,
            "value": 0,
            "gasPrice": web3.eth.gas_price,
            "chainId": RPC_INFO[rpc]["chainId"],
        }
    )
    signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
    transaction_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    receipt = web3.eth.wait_for_transaction_receipt(transaction_hash)

    if receipt.status != 1:
        print(f"Transaction {transaction_hash.hex()} failed!")
        return

    network_name = RPC_INFO[rpc]["name"]
    print(f"[{network_name}] Approve {bridge_num} hash: {transaction_hash.hex()}")
    print(f"Waiting {sleep_between_tx} seconds...")
    time.sleep(sleep_between_tx)


# Fee estimation function for bridge1 transactions
def estimate_fees(rpc, private_key, tokenId, recipientChain):
    web3 = Web3(Web3.HTTPProvider(rpc))
    account = web3.eth.account.from_key(private_key)
    chain_id = CHAIN_IDS_L0[recipientChain]
    params = "0x00010000000000000000000000000000000000000000000000000000000000055730"
    contract = web3.eth.contract(
        web3.to_checksum_address(RPC_INFO[rpc]["bridge1"]), abi=bridge_abi
    )
    fee_wei = contract.functions.estimateFee(
        RPC_INFO[rpc]["contract"],
        tokenId,
        chain_id,
        account.address,
        params,
    ).call()

    return fee_wei


RPC_MAP = {"bsc": BSC_RPC, "pol": POLYGON_RPC, "core": CORE_RPC, "celo": CELO_RPC}

# Script launches here:
if __name__ == "__main__":
    choice = input(
        "1. Approve in all networks\n"
        "2. Bridge according path from path.txt\n"
        "3. Mint 6 pandas in 4 networks\n"
        "Choice: "
    )

    if choice == "1":
        try:
            for _rpc in RPC_ARR:
                approve_for_all(_rpc, private_key, RPC_INFO[_rpc]["bridge1"], 1)
                approve_for_all(_rpc, private_key, RPC_INFO[_rpc]["bridge2"], 2)
        except Exception as e:
            print(f"Approve failed! Error: {e}")
    if choice == "2":
        with open("path.txt", "r") as file:
            for line in file:
                values = [x.strip() for x in line.split(",")]
                token_id, chain_from, chain_to = values
                token_id = int(token_id)

                if chain_from in RPC_MAP:
                    current_rpc = RPC_MAP[chain_from]

                    if chain_to in ["combo", "opbnb"]:
                        bridge_nft_claimable(
                            current_rpc,
                            private_key,
                            token_id,
                            chain_to,
                        )
                    else:
                        bridge_nft(
                            current_rpc,
                            private_key,
                            token_id,
                            chain_to,
                        )

    if choice == "3":
        for _chain in RPC_ARR:
            try:
                for _ in range(6):
                    mint(_chain, private_key)
            except Exception as e:
                print(f"Mint failed, error: {e}")
