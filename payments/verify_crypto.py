import requests
import logging

logger = logging.getLogger(__name__)

# USDC contract addresses per chain (checksummed)
USDC_CONTRACTS = {
    "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "polygon": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    "arbitrum": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "avalanche": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
}

# USDC decimals per chain (BSC uses 18, rest use 6)
USDC_DECIMALS = {
    "ethereum": 6,
    "base": 6,
    "polygon": 6,
    "arbitrum": 6,
    "bsc": 18,
    "avalanche": 6,
}

# Block explorer API base URLs
EXPLORER_APIS = {
    "ethereum": "https://api.etherscan.io/api",
    "base": "https://api.basescan.org/api",
    "polygon": "https://api.polygonscan.com/api",
    "arbitrum": "https://api.arbiscan.io/api",
    "bsc": "https://api.bscscan.com/api",
    "avalanche": "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api",
}

# 10 USDC with +-3% tolerance
EXPECTED_AMOUNT_USD = 10
TOLERANCE = 0.03


def _expected_range(chain):
    """Return (min_amount, max_amount) in token units for 10 USDC on this chain."""
    decimals = USDC_DECIMALS[chain]
    base = EXPECTED_AMOUNT_USD * (10 ** decimals)
    return int(base * (1 - TOLERANCE)), int(base * (1 + TOLERANCE))


def verify_crypto_payment(chain, tx_hash, wallet_address):
    """
    Verify a crypto payment on-chain.
    
    Returns dict:
        {"verified": True/False, "reason": str, "amount": int|None}
    """
    chain = chain.lower()
    if chain not in EXPLORER_APIS:
        return {"verified": False, "reason": f"unsupported chain: {chain}", "amount": None}

    wallet_address = wallet_address.lower()
    usdc_contract = USDC_CONTRACTS[chain].lower()
    api_url = EXPLORER_APIS[chain]

    # Method 1: Check token transfers for the tx hash
    # We use eth_getTransactionReceipt to check if tx is confirmed,
    # then tokentx to find the USDC transfer details
    try:
        result = _check_via_receipt_and_logs(api_url, chain, tx_hash, wallet_address, usdc_contract)
        if result is not None:
            return result
    except Exception as e:
        logger.warning(f"Receipt method failed for {chain}/{tx_hash}: {e}")

    # Method 2: Fallback - check via tokentx for the wallet
    try:
        result = _check_via_tokentx(api_url, chain, tx_hash, wallet_address, usdc_contract)
        if result is not None:
            return result
    except Exception as e:
        logger.warning(f"tokentx method failed for {chain}/{tx_hash}: {e}")

    return {"verified": False, "reason": "could not verify transaction on-chain", "amount": None}


def _check_via_receipt_and_logs(api_url, chain, tx_hash, wallet_address, usdc_contract):
    """Check tx receipt for confirmation and parse ERC20 Transfer logs."""
    resp = requests.get(api_url, params={
        "module": "proxy",
        "action": "eth_getTransactionReceipt",
        "txhash": tx_hash,
    }, timeout=15)
    data = resp.json()

    receipt = data.get("result")
    if not receipt or receipt == "null" or isinstance(receipt, str):
        return {"verified": False, "reason": "transaction not found or not yet confirmed", "amount": None}

    # Check tx succeeded (status 0x1)
    status = receipt.get("status", "")
    if status != "0x1":
        return {"verified": False, "reason": "transaction reverted or failed", "amount": None}

    # Parse logs for ERC20 Transfer event
    # Transfer(address,address,uint256) topic = 0xddf252ad...
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    min_amount, max_amount = _expected_range(chain)

    for log in receipt.get("logs", []):
        log_address = log.get("address", "").lower()
        topics = log.get("topics", [])

        if log_address != usdc_contract:
            continue
        if len(topics) < 3 or topics[0].lower() != transfer_topic:
            continue

        # topics[2] is the 'to' address (zero-padded)
        to_addr = "0x" + topics[2][-40:]
        if to_addr.lower() != wallet_address:
            continue

        # data is the amount
        amount_hex = log.get("data", "0x0")
        amount = int(amount_hex, 16)

        if min_amount <= amount <= max_amount:
            return {"verified": True, "reason": "confirmed", "amount": amount}
        else:
            return {
                "verified": False,
                "reason": f"amount mismatch: got {amount}, expected {min_amount}-{max_amount}",
                "amount": amount,
            }

    return None  # No matching transfer found in logs, try next method


def _check_via_tokentx(api_url, chain, tx_hash, wallet_address, usdc_contract):
    """Check via tokentx API for the receiving wallet."""
    resp = requests.get(api_url, params={
        "module": "account",
        "action": "tokentx",
        "address": wallet_address,
        "sort": "desc",
        "page": 1,
        "offset": 50,
    }, timeout=15)
    data = resp.json()

    if data.get("status") != "1" or not data.get("result"):
        return None

    min_amount, max_amount = _expected_range(chain)

    for tx in data["result"]:
        if tx.get("hash", "").lower() != tx_hash.lower():
            continue
        if tx.get("contractAddress", "").lower() != usdc_contract:
            return {"verified": False, "reason": "wrong token contract", "amount": None}
        if tx.get("to", "").lower() != wallet_address:
            return {"verified": False, "reason": "wrong recipient", "amount": None}

        amount = int(tx.get("value", "0"))

        if min_amount <= amount <= max_amount:
            return {"verified": True, "reason": "confirmed", "amount": amount}
        else:
            return {
                "verified": False,
                "reason": f"amount mismatch: got {amount}, expected {min_amount}-{max_amount}",
                "amount": amount,
            }

    return None  # tx_hash not found in recent transfers
