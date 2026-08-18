"""
Comprehensive test suite for Sweetsnipe.
Tests critical functionality without requiring live RPC connections.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# Import components to test
from src.shared.validators import validator, ValidationError
from src.shared.circuit_breaker import CircuitBreaker, with_retry_and_timeout, ExecutionTimeoutError
from src.shared.constants import *


class TestValidators:
    """Test input validation"""

    def test_validate_ethereum_address_valid(self):
        """Test valid Ethereum address"""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
        result = validator.validate_ethereum_address(address)
        assert result.startswith("0x")
        assert len(result) == 42

    def test_validate_ethereum_address_invalid_length(self):
        """Test invalid address length"""
        with pytest.raises(ValidationError, match="42 characters"):
            validator.validate_ethereum_address("0x123")

    def test_validate_ethereum_address_no_prefix(self):
        """Test address without 0x prefix"""
        with pytest.raises(ValidationError, match="start with 0x"):
            validator.validate_ethereum_address("742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")

    def test_validate_ethereum_address_invalid_chars(self):
        """Test address with invalid characters"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validator.validate_ethereum_address("0xGGGd35Cc6634C0532925a3b844Bc9e7595f0bEb0")

    def test_validate_private_key_valid(self):
        """Test valid private key"""
        pk = "0x" + "a" * 64
        result = validator.validate_private_key(pk)
        assert len(result) == 66
        assert result.startswith("0x")

    def test_validate_private_key_without_prefix(self):
        """Test private key without 0x prefix gets normalized"""
        pk = "a" * 64
        result = validator.validate_private_key(pk)
        assert result.startswith("0x")
        assert len(result) == 66

    def test_validate_mint_function_allowed(self):
        """Test allowed mint function"""
        result = validator.validate_mint_function_name("mint")
        assert result == "mint"

    def test_validate_mint_function_not_allowed(self):
        """Test disallowed function name"""
        with pytest.raises(ValidationError, match="not allowed"):
            validator.validate_mint_function_name("exploit")

    def test_validate_mint_function_special_chars(self):
        """Test function name with special characters"""
        with pytest.raises(ValidationError, match="invalid characters"):
            validator.validate_mint_function_name("mint(); drop table users;")

    def test_validate_email_valid(self):
        """Test valid email"""
        result = validator.validate_email("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_invalid(self):
        """Test invalid email"""
        with pytest.raises(ValidationError, match="Invalid email"):
            validator.validate_email("not-an-email")

    def test_validate_password_strong(self):
        """Test strong password"""
        validator.validate_password("StrongPass123")  # Should not raise

    def test_validate_password_weak(self):
        """Test weak password"""
        with pytest.raises(ValidationError):
            validator.validate_password("weak")

    def test_validate_quantity_valid(self):
        """Test valid quantity"""
        result = validator.validate_quantity(5)
        assert result == 5

    def test_validate_quantity_too_high(self):
        """Test quantity exceeds maximum"""
        with pytest.raises(ValidationError, match="cannot exceed"):
            validator.validate_quantity(150)


class TestCircuitBreaker:
    """Test circuit breaker pattern"""

    def test_circuit_breaker_closed(self):
        """Test circuit breaker in closed state"""
        cb = CircuitBreaker(failure_threshold=3)

        def successful_func():
            return "success"

        result = cb.call(successful_func)
        assert result == "success"
        assert cb.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        cb = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise Exception("Error")

        # First 3 failures should increment counter
        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)

        # Circuit should now be open
        assert cb.failure_count >= 3

    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self):
        """Test async circuit breaker"""
        cb = CircuitBreaker(failure_threshold=2)

        async def async_func():
            return "async success"

        result = await cb.call_async(async_func)
        assert result == "async success"

    @pytest.mark.asyncio
    async def test_retry_with_timeout_success(self):
        """Test retry mechanism with successful call"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"

        result = await with_retry_and_timeout(
            flaky_func,
            max_attempts=5,
            max_duration=10,
            retry_delay=0.1
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_timeout_max_attempts(self):
        """Test retry exhausts max attempts"""
        async def always_fails():
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Max attempts"):
            await with_retry_and_timeout(
                always_fails,
                max_attempts=3,
                max_duration=10,
                retry_delay=0.1
            )

    @pytest.mark.asyncio
    async def test_retry_with_timeout_exceeds_duration(self):
        """Test retry exceeds max duration"""
        async def slow_func():
            await asyncio.sleep(2)
            raise Exception("Too slow")

        with pytest.raises(ExecutionTimeoutError):
            await with_retry_and_timeout(
                slow_func,
                max_attempts=10,
                max_duration=3,
                retry_delay=0.5
            )


class TestConstants:
    """Test that constants are defined correctly"""

    def test_gas_constants_defined(self):
        """Test gas-related constants"""
        assert GAS_ESTIMATE_BUFFER == 1.2
        assert GAS_PRICE_BUFFER == 1.1
        assert EIP1559_BASE_FEE_MULTIPLIER == 1.5

    def test_retry_constants_defined(self):
        """Test retry constants"""
        assert MAX_RETRY_ATTEMPTS == 50
        assert MAX_EXECUTION_TIME == 3600
        assert TRANSACTION_RECEIPT_TIMEOUT == 120

    def test_cache_ttl_constants(self):
        """Test cache TTL constants"""
        assert GAS_PRICE_CACHE_TTL == 10
        assert CONTRACT_METADATA_CACHE_TTL == 3600

    def test_rate_limit_constants(self):
        """Test rate limit constants"""
        assert RATE_LIMIT_REGISTER == "5/minute"
        assert RATE_LIMIT_LOGIN == "10/minute"
        assert RATE_LIMIT_JOB_CREATE == "10/minute"


class TestProductionConfig:
    """Test production-safe configuration handling for Railway deployment."""

    def test_settings_accept_boolean_debug(self):
        """DEBUG should accept bool values without startup validation failure."""
        from cryptography.fernet import Fernet
        from web.backend.config import Settings

        settings = Settings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY=Fernet.generate_key().decode(),
            DATABASE_URL="sqlite:///:memory:",
            DEBUG=False,
        )

        assert settings.DEBUG is False

    def test_settings_support_railway_port(self):
        """Railway's PORT variable must be available as an integer setting."""
        import os
        from cryptography.fernet import Fernet
        from web.backend.config import Settings

        os.environ["PORT"] = "8080"
        settings = Settings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY=Fernet.generate_key().decode(),
            DATABASE_URL="sqlite:///:memory:",
            DEBUG=False,
        )

        assert settings.PORT == 8080


class TestGasOracle:
    """Test gas oracle service"""

    @pytest.mark.asyncio
    async def test_gas_price_caching(self):
        """Test gas price is cached"""
        from src.shared.gas_oracle import GasOracle

        oracle = GasOracle()

        # Mock web3
        mock_w3 = Mock()
        mock_w3.eth.gas_price = AsyncMock(return_value=50_000_000_000)

        # First call should fetch
        price1 = await oracle.get_gas_price(mock_w3, "ETH")

        # Second call should use cache
        price2 = await oracle.get_gas_price(mock_w3, "ETH")

        assert price1 == price2
        # Should only call RPC once due to caching
        assert mock_w3.eth.gas_price.call_count == 1


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
