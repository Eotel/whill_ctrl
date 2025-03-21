"""
OSCサーバーの実装
WHILLコントローラーからの指示を受け取り、OSCメッセージに応じてWHILLを制御する
"""

import asyncio

from loguru import logger
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

from ..controller.controller import WHILLController


class WHILLOSCController:
    """WHILLデバイスをOSC経由で制御するクラス"""

    def __init__(self, controller: WHILLController) -> None:
        """
        OSCコントローラーを初期化

        Args:
            controller: WHILLコントローラーインスタンス
        """
        self.controller = controller
        self.dispatcher = Dispatcher()
        self.register_callbacks()

    def register_callbacks(self) -> None:
        """OSCコールバックを登録する"""
        self.dispatcher.map("/whill/joystick", self.osc_joystick_callback)
        self.dispatcher.map("/whill/power_on", self.power_on_callback)
        self.dispatcher.map("/whill/power_off", self.power_off_callback)
        self.dispatcher.map("/whill/emergency_stop", self.emergency_stop_callback)

    def osc_joystick_callback(self, address: str, *args) -> None:
        """
        OSCジョイスティックコマンドのコールバック

        Args:
            address: OSCアドレス
            args: OSCパラメータ (x, y)値を期待
        """
        try:
            if len(args) < 2:
                raise ValueError("At least 2 parameters required: x and y values.")

            # OSCからの値は -1 ～ 1 のスケールなので、100倍して -100 ～ 100 に変換する
            x_raw, y_raw = args[0], args[1]
            side = int(round(x_raw * 100))
            front = int(round(y_raw * 100))

            # 念のため範囲を -100～100 にクリッピングする
            side = max(min(side, 100), -100)
            front = max(min(front, 100), -100)

            logger.debug(f"[OSC {address}] Received x: {x_raw:.2f}, y: {y_raw:.2f} => side: {side}, front: {front}")

            # 非同期処理をタスクとして実行
            asyncio.create_task(self.controller.handle_osc_command("joystick", front=front, side=side))
        except Exception as e:
            logger.error(f"Error in OSC joystick callback: {e}")

    def power_on_callback(self, address: str, *args) -> None:
        """
        OSC電源オンコマンドのコールバック

        Args:
            address: OSCアドレス
            args: OSCパラメータ (未使用)
        """
        logger.debug(f"[OSC {address}] Power on command received")
        asyncio.create_task(self.controller.handle_osc_command("power_on"))

    def power_off_callback(self, address: str, *args) -> None:
        """
        OSC電源オフコマンドのコールバック

        Args:
            address: OSCアドレス
            args: OSCパラメータ (未使用)
        """
        logger.debug(f"[OSC {address}] Power off command received")
        asyncio.create_task(self.controller.handle_osc_command("power_off"))

    def emergency_stop_callback(self, address: str, *args) -> None:
        """
        OSC緊急停止コマンドのコールバック

        Args:
            address: OSCアドレス
            args: OSCパラメータ (未使用)
        """
        logger.debug(f"[OSC {address}] Emergency stop command received")
        asyncio.create_task(self.controller.handle_osc_command("emergency_stop"))


class OSCServer:
    """OSCサーバークラス"""

    def __init__(self, controller: WHILLController, ip: str, port: int):
        """
        OSCサーバーを初期化

        Args:
            controller: WHILLコントローラーインスタンス
            ip: バインドするIPアドレス
            port: バインドするポート番号
        """
        self.controller = controller
        self.ip = ip
        self.port = port
        self.osc_controller = WHILLOSCController(controller)
        self.server = None
        self.transport = None
        self.protocol = None

    async def start(self) -> bool:
        """OSCサーバーを起動する"""
        try:
            self.server = AsyncIOOSCUDPServer(
                (self.ip, self.port), self.osc_controller.dispatcher, asyncio.get_running_loop()
            )
            self.transport, self.protocol = await self.server.create_serve_endpoint()
            logger.info(f"OSC Server started on {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start OSC server: {e}")
            return False

    def stop(self) -> None:
        """OSCサーバーを停止する"""
        if self.transport:
            self.transport.close()
            logger.info("OSC server stopped")
