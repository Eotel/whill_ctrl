"""
WHILL制御のための抽象インターフェースクラスを提供します
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class AbstractWHILL(ABC):
    """WHILLデバイスの抽象インターフェース"""

    def __init__(self):
        # デバイスのロックはasyncioベースに変更
        self._lock = asyncio.Lock()
        self._connected = False
        self._port = ""

    @abstractmethod
    async def send_joystick(self, *, front: int, side: int) -> None:
        """Send joystick command with given front and side values."""
        pass

    @abstractmethod
    async def send_power_on(self) -> None:
        """Send power on command."""
        pass

    @abstractmethod
    async def send_power_off(self) -> None:
        """Send power off command."""
        pass

    @abstractmethod
    async def send_emergency_stop(self) -> None:
        """Send emergency stop command (typically set velocity to 0)."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the WHILL device."""
        pass

    @abstractmethod
    async def reconnect(self, port: str | None = None) -> bool:
        """Reconnect to WHILL device, optionally using a new port."""
        pass

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the WHILL device."""
        return {"connected": self._connected, "port": self._port, "mode": self.get_mode(), "last_error": None}

    @abstractmethod
    def get_mode(self) -> str:
        """Get the mode of the WHILL interface (real or mock)."""
        pass

    def is_connected(self) -> bool:
        """Check if the WHILL device is connected."""
        return self._connected

    @property
    def port(self):
        return self._port
