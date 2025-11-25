"""
Pydantic models for ADMZ API requests and responses.
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    """Request model for creating a device."""

    device_id: str = Field(..., description="Unique device identifier")
    host: str = Field(..., description="Device IP or hostname")
    nickname: Optional[str] = Field(None, description="Human-readable device nickname")
    ip_address: Optional[str] = Field(None, description="IP address")
    serial_number: Optional[str] = Field(None, description="Device serial number")
    mac_address: Optional[str] = Field(None, description="MAC address")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    model: Optional[str] = Field(None, description="Device model")
    warranty_expiration: Optional[str] = Field(
        None, description="Warranty expiration date"
    )
    location: Optional[str] = Field(None, description="Physical location")
    tags: Optional[List[str]] = Field(default_factory=list, description="Device tags")
    network: Optional[Dict[str, Any]] = Field(
        None, description="Network configuration (vlan, subnet)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional device metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "front-door",
                "host": "192.168.1.100",
                "nickname": "Front Door Camera",
                "serial_number": "ACCC12345678",
                "model": "AXIS P1455-LE",
                "location": "Main Entrance",
                "tags": ["entrance", "outdoor"],
            }
        }


class DeviceUpdate(BaseModel):
    """Request model for updating a device."""

    host: Optional[str] = Field(None, description="Device IP or hostname")
    nickname: Optional[str] = Field(None, description="Human-readable device nickname")
    ip_address: Optional[str] = Field(None, description="IP address")
    serial_number: Optional[str] = Field(None, description="Device serial number")
    mac_address: Optional[str] = Field(None, description="MAC address")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    model: Optional[str] = Field(None, description="Device model")
    warranty_expiration: Optional[str] = Field(
        None, description="Warranty expiration date"
    )
    location: Optional[str] = Field(None, description="Physical location")
    tags: Optional[List[str]] = Field(None, description="Device tags")
    network: Optional[Dict[str, Any]] = Field(
        None, description="Network configuration (vlan, subnet)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional device metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "nickname": "Front Door Camera",
                "location": "Main Entrance - North Side",
                "firmware_version": "11.8.65",
            }
        }


class DeviceResponse(BaseModel):
    """Response model for device information."""

    device_id: str = Field(..., description="Unique device identifier")
    host: str = Field(..., description="Device IP or hostname")
    nickname: Optional[str] = Field(None, description="Human-readable device nickname")
    ip_address: Optional[str] = Field(None, description="IP address")
    serial_number: Optional[str] = Field(None, description="Device serial number")
    mac_address: Optional[str] = Field(None, description="MAC address")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    model: Optional[str] = Field(None, description="Device model")
    warranty_expiration: Optional[str] = Field(
        None, description="Warranty expiration date"
    )
    location: Optional[str] = Field(None, description="Physical location")
    tags: Optional[List[str]] = Field(default_factory=list, description="Device tags")
    network: Optional[Dict[str, Any]] = Field(
        None, description="Network configuration (vlan, subnet)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional device metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "front-door",
                "host": "192.168.1.100",
                "nickname": "Front Door Camera",
                "serial_number": "ACCC12345678",
                "model": "AXIS P1455-LE",
                "firmware_version": "11.8.65",
                "location": "Main Entrance",
                "tags": ["entrance", "outdoor"],
            }
        }


class AccountCreate(BaseModel):
    """Request model for creating a device account."""

    account_id: str = Field(..., description="Account identifier")
    username: str = Field(..., description="Account username")
    password: str = Field(..., description="Account password")
    account_type: Optional[str] = Field(
        "service", description="Account type (service, admin, etc.)"
    )
    purpose: Optional[str] = Field(None, description="Account purpose description")
    permissions: Optional[List[str]] = Field(
        default_factory=list, description="Account permissions"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional account metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "aoa-agent",
                "username": "aoa-service",
                "password": "secure-password-here",
                "account_type": "service",
                "purpose": "AOA agent access",
                "permissions": ["read", "configure"],
            }
        }


class AccountResponse(BaseModel):
    """Response model for account information (without password)."""

    account_id: str = Field(..., description="Account identifier")
    username: str = Field(..., description="Account username")
    account_type: Optional[str] = Field(
        None, description="Account type (service, admin, etc.)"
    )
    purpose: Optional[str] = Field(None, description="Account purpose description")
    permissions: Optional[List[str]] = Field(
        default_factory=list, description="Account permissions"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional account metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "aoa-agent",
                "username": "aoa-service",
                "account_type": "service",
                "purpose": "AOA agent access",
                "permissions": ["read", "configure"],
            }
        }


class CredentialsResponse(BaseModel):
    """Response model for device credentials."""

    username: str = Field(..., description="Account username")
    password: str = Field(..., description="Account password")
    host: str = Field(..., description="Device IP or hostname")
    account_type: Optional[str] = Field(
        None, description="Account type (service, admin, etc.)"
    )
    purpose: Optional[str] = Field(None, description="Account purpose description")
    permissions: Optional[List[str]] = Field(
        default_factory=list, description="Account permissions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "username": "aoa-service",
                "password": "secure-password-here",
                "host": "192.168.1.100",
                "account_type": "service",
                "purpose": "AOA agent access",
                "permissions": ["read", "configure"],
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "DeviceNotFoundError",
                "message": "Device 'unknown-device' not found",
            }
        }
