"""
実際のWHILLデバイスに接続するための実装
"""

from typing import Any

from loguru import logger

from .interface import AbstractWHILL

# Real implementation using the WHILL Python SDK.
try:
    from whill import ComWHILL
except ImportError:
    ComWHILL = None


class RealWHILL(AbstractWHILL):
    """実機のWHILLデバイスを制御するクラス"""

    def __init__(self, port: str) -> None:
        super().__init__()
        if ComWHILL is None:
            raise ImportError("whill Python SDK is not installed.")
        self._port = port
        self._device = None
        self._last_error = None
        self._connect(port)

    def _connect(self, port: str) -> None:
        """低レベル接続処理 - 例外を発生させる可能性あり"""
        try:
            self._device = ComWHILL(port=port)
            self._connected = True
            self._port = port
            self._last_error = None
            logger.info(f"Connected to WHILL device on port {port}")
        except Exception as e:
            self._connected = False
            self._last_error = str(e)
            logger.error(f"Failed to connect to WHILL device on port {port}: {e}")
            raise

    async def send_joystick(self, *, front: int, side: int) -> None:
        async with self._lock:
            if not self._connected or self._device is None:
                logger.warning("Cannot send joystick command: device not connected")
                return

            try:
                logger.debug(f"Sending joystick command: front={front}, side={side}")
                self._device.send_joystick(front=front, side=side)
            except Exception as e:
                logger.error(f"Error sending joystick command: {e}")
                self._connected = False
                self._last_error = str(e)

    async def send_power_on(self) -> None:
        async with self._lock:
            if not self._connected or self._device is None:
                logger.warning("Cannot send power on command: device not connected")
                return

            try:
                logger.debug("Sending power on command")
                self._device.send_power_on()
            except Exception as e:
                logger.error(f"Error sending power on command: {e}")
                self._connected = False
                self._last_error = str(e)

    async def send_power_off(self) -> None:
        async with self._lock:
            if not self._connected or self._device is None:
                logger.warning("Cannot send power off command: device not connected")
                return

            try:
                logger.debug("Sending power off command")
                self._device.send_power_off()
            except Exception as e:
                logger.error(f"Error sending power off command: {e}")
                self._connected = False
                self._last_error = str(e)

    async def send_emergency_stop(self) -> None:
        async with self._lock:
            if not self._connected or self._device is None:
                logger.warning("Cannot send emergency stop command: device not connected")
                return

            try:
                logger.debug("Sending emergency stop command")
                self._device.send_joystick(front=0, side=0)
            except Exception as e:
                logger.error(f"Error sending emergency stop command: {e}")
                self._connected = False
                self._last_error = str(e)

    async def disconnect(self) -> None:
        async with self._lock:
            if self._device is None:
                return

            try:
                self._device.com.close()
                logger.info("WHILL device disconnected")
            except Exception as e:
                logger.error(f"Failed to close serial port: {e}")
            finally:
                self._connected = False
                self._device = None

    async def reconnect(self, port: str | None = None) -> bool:
        """WHILLデバイスに再接続する"""
        async with self._lock:
            # 既存の接続を閉じる
            if self._device is not None:
                try:
                    self._device.com.close()
                except Exception as e:
                    logger.error(f"Error closing existing connection: {e}")

            # 接続先のポートを決定
            target_port = port if port is not None else self._port

            # 再接続を試みる
            try:
                self._connect(target_port)
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect to port {target_port}: {e}")
                self._connected = False
                self._last_error = str(e)
                return False

    def get_status(self) -> dict[str, Any]:
        """デバイスの現在のステータスを取得"""
        status = super().get_status()
        status["last_error"] = self._last_error
        return status

    def get_mode(self) -> str:
        return "real"
