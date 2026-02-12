"""Custom exceptions for SD recovery tool."""


class SDRecoveryError(Exception):
    """Base exception for SD recovery operations."""
    pass


class DeviceNotFoundError(SDRecoveryError):
    """Device not found or invalid device path."""
    pass


class UnsafeDeviceError(SDRecoveryError):
    """Device failed safety checks (e.g., internal disk)."""
    pass


class PhotoRecNotFoundError(SDRecoveryError):
    """PhotoRec executable not found."""
    pass


class PhotoRecExecutionError(SDRecoveryError):
    """PhotoRec execution failed."""
    pass


class ValidationError(SDRecoveryError):
    """File validation failed."""
    pass


class MountError(SDRecoveryError):
    """Failed to mount or unmount device."""
    pass
