"""
WHILLデバイスのモック実装
テスト用途や実機がない場合の機能検証に使用
"""

from typing import Any

from loguru import logger

from .interface import AbstractWHILL


class MockWHILL(AbstractWHILL):
    """WHILLデバイスのモック実装"""

    def __init__(self, port: str) -> None:
        super().__init__()
        self._port = port
        self._connected = True
        self._last_error = None
        logger.info(f"Using mock WHILL on port {port}")

    async def send_joystick(self, *, front: int, side: int) -> None:
        async with self._lock:
            logger.debug(f"[Mock] Joystick command: front={front}, side={side}")

    async def send_power_on(self) -> None:
        async with self._lock:
            logger.debug("[Mock] Power on command")

    async def send_power_off(self) -> None:
        async with self._lock:
            logger.debug("[Mock] Power off command")

    async def send_emergency_stop(self) -> None:
        async with self._lock:
            logger.debug("[Mock] Emergency stop command (set velocity to 0)")

    async def disconnect(self) -> None:
        async with self._lock:
            self._connected = False
            logger.info("[Mock] WHILL device disconnected")

    async def reconnect(self, port: str | None = None) -> bool:
        """モックWHILLデバイスに再接続する"""
        async with self._lock:
            if port is not None:
                self._port = port

            self._connected = True
            logger.info(f"[Mock] Reconnected to port {self._port}")
            return True

    def get_status(self) -> dict[str, Any]:
        """モックデバイスの現在のステータスを取得"""
        status = super().get_status()
        status["last_error"] = self._last_error
        return status

    def get_mode(self) -> str:
        return "mock"
