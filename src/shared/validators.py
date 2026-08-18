"""
Input validation utilities for security.
"""
import re
from typing import Optional, Tuple
from web3 import Web3
from src.shared.constants import (
    ETHEREUM_ADDRESS_LENGTH,
    ETHEREUM_PRIVATE_KEY_LENGTH,
    ALLOWED_MINT_FUNCTIONS
)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class InputValidator:
    """Validates user inputs for security."""

    @staticmethod
    def validate_ethereum_address(address: str) -> str:
        """
        Validate Ethereum address format and checksum.
        Returns checksummed address.
        Raises ValidationError if invalid.
        """
        if not address:
            raise ValidationError("Address cannot be empty")

        if not isinstance(address, str):
            raise ValidationError("Address must be a string")

        if not address.startswith("0x"):
            raise ValidationError("Address must start with 0x")

        if len(address) != ETHEREUM_ADDRESS_LENGTH:
            raise ValidationError(f"Address must be {ETHEREUM_ADDRESS_LENGTH} characters long")

        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            raise ValidationError("Address contains invalid characters")

        try:
            checksummed = Web3.to_checksum_address(address)
            return checksummed
        except ValueError as e:
            raise ValidationError(f"Invalid address checksum: {e}")

    @staticmethod
    def validate_private_key(private_key: str) -> str:
        """
        Validate private key format.
        Returns normalized private key.
        Raises ValidationError if invalid.
        """
        if not private_key:
            raise ValidationError("Private key cannot be empty")

        if not isinstance(private_key, str):
            raise ValidationError("Private key must be a string")

        # Normalize: add 0x prefix if missing
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        if len(private_key) != ETHEREUM_PRIVATE_KEY_LENGTH:
            raise ValidationError(f"Private key must be {ETHEREUM_PRIVATE_KEY_LENGTH} characters long")

        if not re.match(r'^0x[a-fA-F0-9]{64}$', private_key):
            raise ValidationError("Private key contains invalid characters")

        return private_key

    @staticmethod
    def validate_mint_function_name(func_name: str) -> str:
        """
        Validate mint function name against whitelist.
        Returns sanitized function name.
        Raises ValidationError if invalid.
        """
        if not func_name:
            raise ValidationError("Function name cannot be empty")

        if not isinstance(func_name, str):
            raise ValidationError("Function name must be a string")

        # Remove any special characters
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', func_name)

        if sanitized != func_name:
            raise ValidationError("Function name contains invalid characters")

        if sanitized not in ALLOWED_MINT_FUNCTIONS:
            raise ValidationError(
                f"Function '{sanitized}' not allowed. "
                f"Allowed functions: {', '.join(ALLOWED_MINT_FUNCTIONS)}"
            )

        return sanitized

    @staticmethod
    def validate_network(network: str, available_networks: list) -> str:
        """
        Validate network ticker against available networks.
        Returns uppercase network ticker.
        Raises ValidationError if invalid.
        """
        if not network:
            raise ValidationError("Network cannot be empty")

        network_upper = network.upper()

        if network_upper not in available_networks:
            raise ValidationError(
                f"Network '{network}' not supported. "
                f"Available: {', '.join(available_networks)}"
            )

        return network_upper

    @staticmethod
    def validate_quantity(quantity: int, min_qty: int = 1, max_qty: int = 100) -> int:
        """
        Validate mint quantity.
        Returns validated quantity.
        Raises ValidationError if invalid.
        """
        if not isinstance(quantity, int):
            raise ValidationError("Quantity must be an integer")

        if quantity < min_qty:
            raise ValidationError(f"Quantity must be at least {min_qty}")

        if quantity > max_qty:
            raise ValidationError(f"Quantity cannot exceed {max_qty}")

        return quantity

    @staticmethod
    def validate_email(email: str) -> str:
        """
        Validate email format.
        Returns lowercase email.
        Raises ValidationError if invalid.
        """
        if not email:
            raise ValidationError("Email cannot be empty")

        email = email.lower().strip()

        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Invalid email format")

        if len(email) > 255:
            raise ValidationError("Email too long")

        return email

    @staticmethod
    def validate_password(password: str, min_length: int = 8) -> None:
        """
        Validate password strength.
        Raises ValidationError if invalid.
        """
        if not password:
            raise ValidationError("Password cannot be empty")

        if len(password) < min_length:
            raise ValidationError(f"Password must be at least {min_length} characters")

        # Check for at least one uppercase, one lowercase, one digit
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")

        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")

        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit")

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """
        Sanitize string input by removing potentially dangerous characters.
        """
        if not value:
            return ""

        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

        # Trim to max length
        return sanitized[:max_length].strip()


# Create singleton instance
validator = InputValidator()
