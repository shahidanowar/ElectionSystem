from web3 import Web3
from eth_account import Account
import os
from dotenv import load_dotenv

load_dotenv()

# Sepolia testnet configuration
SEPOLIA_RPC_URL = "https://sepolia.infura.io/v3/ffc964d1bc7e4f849c622cd675b93a28"
CONTRACT_ADDRESS = "0xCe808658AAa4539Db1bF539ac3e4B949e89cB56c"  # Replace after deploying

# Initialize Web3 with HTTPProvider
w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))

# Print connection status
print(f"Connected to Ethereum: {w3.is_connected()}")
print(f"Using network: {w3.eth.chain_id if w3.is_connected() else 'Not connected'}")

# Contract ABI - Replace with your contract's ABI after deployment
CONTRACT_ABI = [
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "_electionId",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "_candidateId",
                "type": "uint256"
            }
        ],
        "name": "castVote",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "electionId",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "candidateId",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "voter",
                "type": "address"
            }
        ],
        "name": "VoteCast",
        "type": "event"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "_electionId",
                "type": "uint256"
            },
            {
                "internalType": "address",
                "name": "_voter",
                "type": "address"
            }
        ],
        "name": "checkVoted",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "_electionId",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "_candidateId",
                "type": "uint256"
            }
        ],
        "name": "getVoteCount",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            },
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "name": "hasVoted",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "name": "voteCounts",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

def get_contract():
    if not w3.is_connected():
        raise Exception("Not connected to Ethereum network")
    return w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
