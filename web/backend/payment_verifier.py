import asyncio
import logging
from decimal import Decimal
from typing import Optional, Tuple
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.types import TxReceipt

from backend.config import settings

logger = logging.getLogger(__name__)

# Standard ERC20 ABI for transfer events and balance checks
ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# Common stablecoin addresses by network
STABLECOINS = {
    "ETH": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    },
    "BASE": {
        "USDT": "0xfde4C96c8593536E31F229EA8F37b2ADA2699bb2",
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    },
    "OP": {
        "USDT": "0x94b9F57A7EA5D63b9e3f96FF35569B4264152E1D",
        "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
    },
    "ARB": {
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "POLY": {
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    },
    "BSC": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    },
    "AVAX": {
        "USDT": "0x9702230A8Ea53601F5cD2dc00fDBc13d4dF4A8c7",
        "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
    },
    "BERA": {
        "USDT": "0xB75A6E7D326A190B1C3f32eB1FEe37c89B056d6D",
        "USDC": "0xd988097fBa208b7af75a1ECdbE4aF16E5f2Aea8d",
    },
}

class PaymentVerifier:
    def __init__(self):
        self.network = settings.TREASURY_NETWORK
        self.treasury = settings.TREASURY_ADDRESS.lower()
        self.rpc_list = settings.RPC_NETWORKS.get(self.network, [])
        self.w3: Optional[AsyncWeb3] = None
        self._current_rpc = 0

    async def _init_web3(self):
        if not self.rpc_list:
            return False
        url = self.rpc_list[self._current_rpc % len(self.rpc_list)]
        self.w3 = AsyncWeb3(AsyncHTTPProvider(url))
        return True

    async def _rotate_rpc(self):
        self._current_rpc += 1
        if self._current_rpc >= len(self.rpc_list):
            self._current_rpc = 0
        return await self._init_web3()

    async def verify_payment(self, tx_hash: str, expected_amount: float, currency: str = "ETH") -> Tuple[bool, Optional[str]]:
        if not self.treasury:
            return False, "Treasury address not configured"

        if not await self._init_web3():
            return False, "No RPC configured for network"

        try:
            tx = await self.w3.eth.get_transaction(tx_hash)
            if not tx:
                return False, "Transaction not found"

            receipt = await self.w3.eth.get_transaction_receipt(tx_hash)
            if not receipt:
                return False, "Transaction receipt not found"
            if receipt.status != 1:
                return False, "Transaction failed on-chain"

            block = await self.w3.eth.get_block(receipt.blockNumber)
            confirmations = 1
            current_block = await self.w3.eth.block_number
            if current_block and block:
                confirmations = current_block - block.number + 1

            min_confirmations = 3 if self.network == "ETH" else 1
            if confirmations < min_confirmations:
                return False, f"Transaction has {confirmations} confirmations, needs {min_confirmations}"

            currency = currency.upper()
            if currency == "ETH":
                return await self._verify_eth_payment(tx, receipt, expected_amount)
            else:
                return await self._verify_erc20_payment(tx, receipt, expected_amount, currency)

        except Exception as e:
            logger.error(f"Verification error for {tx_hash}: {e}")
            return False, f"Verification error: {str(e)}"

    async def _verify_eth_payment(self, tx, receipt, expected_amount: float) -> Tuple[bool, Optional[str]]:
        if tx.to and tx.to.lower() == self.treasury:
            amount_eth = float(tx.value) / 1e18
            if amount_eth >= expected_amount:
                return True, None
            return False, f"ETH amount too low: {amount_eth:.6f} < {expected_amount}"
        return False, "Transaction not sent to treasury address"

    async def _verify_erc20_payment(self, tx, receipt, expected_amount: float, currency: str) -> Tuple[bool, Optional[str]]:
        token_address = STABLECOINS.get(self.network, {}).get(currency)
        if not token_address:
            return False, f"Unsupported token {currency} on {self.network}"

        contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)

        try:
            logs = contract.events.Transfer().process_receipt(receipt, errors='DISCARD')
        except Exception as e:
            return False, f"Failed to parse token transfer: {e}"

        for log in logs:
            if log.args.to and log.args.to.lower() == self.treasury:
                decimals = await contract.functions.decimals().call()
                amount_token = float(log.args.value) / (10 ** decimals)
                if amount_token >= expected_amount:
                    return True, None
                return False, f"{currency} amount too low: {amount_token:.2f} < {expected_amount}"

        return False, f"No {currency} transfer to treasury found"

payment_verifier = PaymentVerifier()
