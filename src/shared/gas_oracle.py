"""
Shared Gas Oracle Service - Eliminates duplicate gas price logic.
Provides centralized gas price management with caching.
"""
import asyncio
import time
from typing import Optional, Dict, Union
from web3 import AsyncWeb3
from src.shared.constants import (
    GAS_ESTIMATE_BUFFER,
    GAS_PRICE_BUFFER,
    EIP1559_BASE_FEE_MULTIPLIER,
    EIP1559_PRIORITY_FEE_MULTIPLIER,
    GAS_PRICE_CACHE_TTL
)


class GasOracle:
    """Centralized gas price oracle with caching."""

    def __init__(self):
        self._cache: Dict[str, tuple[int | Dict, float]] = {}
        self._lock = asyncio.Lock()

    async def get_gas_price(
        self,
        w3: AsyncWeb3,
        network: str,
        force_refresh: bool = False
    ) -> Union[int, Dict[str, int]]:
        """
        Get gas price with caching.
        Returns either legacy gas price (int) or EIP-1559 dict.
        """
        cache_key = f"{network}_gas_price"

        if not force_refresh and cache_key in self._cache:
            cached_price, cached_time = self._cache[cache_key]
            if time.time() - cached_time < GAS_PRICE_CACHE_TTL:
                return cached_price

        async with self._lock:
            # Try EIP-1559 first
            try:
                fee_history = await w3.eth.fee_history(1, 'latest')
                if fee_history and fee_history.get('baseFeePerGas'):
                    next_base_fee = fee_history['baseFeePerGas'][-1]
                    priority = fee_history.get('reward', [[0]])[-1][-1] if fee_history.get('reward') else 0

                    gas_params = {
                        "maxFeePerGas": int(next_base_fee * EIP1559_BASE_FEE_MULTIPLIER),
                        "maxPriorityFeePerGas": max(int(priority * EIP1559_PRIORITY_FEE_MULTIPLIER), int(next_base_fee * 0.1))
                    }

                    self._cache[cache_key] = (gas_params, time.time())
                    return gas_params
            except Exception:
                pass

            # Fallback to legacy gas price
            gas_price = await w3.eth.gas_price
            buffered_price = int(gas_price * GAS_PRICE_BUFFER)
            self._cache[cache_key] = (buffered_price, time.time())
            return buffered_price

    async def apply_gas_strategy(
        self,
        w3: AsyncWeb3,
        network: str,
        tx_data: dict,
        manual_gas_gwei: Optional[float] = None
    ) -> dict:
        """Apply gas strategy to transaction data."""
        if manual_gas_gwei:
            # User-specified gas price
            tx_data["gasPrice"] = int(manual_gas_gwei * 1e9)
            tx_data.pop("maxFeePerGas", None)
            tx_data.pop("maxPriorityFeePerGas", None)
        else:
            gas_strategy = await self.get_gas_price(w3, network)
            if isinstance(gas_strategy, dict):
                tx_data["maxFeePerGas"] = gas_strategy["maxFeePerGas"]
                tx_data["maxPriorityFeePerGas"] = gas_strategy["maxPriorityFeePerGas"]
                tx_data.pop("gasPrice", None)
            else:
                tx_data["gasPrice"] = gas_strategy
                tx_data.pop("maxFeePerGas", None)
                tx_data.pop("maxPriorityFeePerGas", None)

        return tx_data

    async def estimate_gas_with_buffer(
        self,
        w3: AsyncWeb3,
        tx_data: dict,
        default_gas_limit: int
    ) -> int:
        """Estimate gas with buffer or use default."""
        try:
            estimated_gas = await w3.eth.estimate_gas(tx_data)
            return int(estimated_gas * GAS_ESTIMATE_BUFFER)
        except Exception:
            return default_gas_limit

    def clear_cache(self):
        """Clear all cached gas prices."""
        self._cache.clear()


# Global singleton instance
gas_oracle = GasOracle()
