import aiohttp
import asyncio
from datetime import datetime
from src.ui.logger import Logger
from src.config.settings import ConfigurationManager

class ContractVerifier:
    API_MAP = {
        "ETH": "https://api.etherscan.io/api",
        "BASE": "https://api.basescan.org/api",
        "OP": "https://api-optimistic.etherscan.io/api",
        "ARB": "https://api.arbiscan.io/api",
        "POLY": "https://api.polygonscan.com/api",
        "BSC": "https://api.bscscan.com/api",
        "AVAX": "https://api.snowtrace.io/api",
    }

    def __init__(self, api_key, network_ticker):
        self.api_key = api_key
        self.network = network_ticker
        self.base_url = self.API_MAP.get(network_ticker)

    async def is_verified(self, contract_address):
        if not self.base_url:
            Logger.log("SYS", "WARNING", f"[Verifier] Network {self.network} not supported via API. Skipping check.")
            return True

        if not self.api_key:
            Logger.log("SYS", "WARNING", "[Verifier] API Key missing. Skipping check.")
            return True

        params = {
            "module": "contract",
            "action": "getabi",
            "address": contract_address,
            "apikey": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()
                    
                    if data['status'] == '1':
                        return True
                    else:
                        if "not verified" in str(data['result']).lower():
                            return False
                        
                        Logger.log("SYS", "WARNING", f"[Verifier API] {data['result']}")
                        return True 

        except Exception as e:
            Logger.log("SYS", "ERROR", f"[Verifier] Connection Error: {e}")
            return True

    async def check_guard(self, contract_address):
        Logger.log("SYS", "INIT", f"Verifying Contract: {contract_address}...")
        is_safe = await self.is_verified(contract_address)
        
        if is_safe:
            Logger.log("SYS", "SUCCESS", "Contract is VERIFIED. Safe to proceed.")
            return True
        else:
            Logger.log("SYS", "FATAL", "⚠️ CONTRACT IS UNVERIFIED! (Potential Honeypot/Scam). Aborting...")
            return False