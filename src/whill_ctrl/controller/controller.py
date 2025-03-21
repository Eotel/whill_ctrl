"""
WHILLコントローラークラスを提供するモジュール
OSCとMQTTからの入力を統合的に処理し、WHILLデバイスを制御する
"""

import asyncio

from loguru import logger

from ..whill.interface import AbstractWHILL


class WHILLController:
    """WHILLデバイスを統合的に制御するコントローラー"""

    def __init__(self, whill: AbstractWHILL):
        """
        WHILLコントローラーを初期化

        Args:
            whill: WHILLデバイスインターフェース
        """
        self.whill = whill

        # 排他制御のためのロック
        self.command_lock = asyncio.Lock()

        # 再接続用のフラグとタスク
        self.reconnect_task = None
        self.running = False

    async def start(self) -> bool:
        """コントローラーを開始する"""
        self.running = True

        # 接続監視タスクを開始
        self.reconnect_task = asyncio.create_task(self.monitor_connection())

        logger.info("WHILL controller started")
        return True

    async def stop(self) -> None:
        """コントローラーを停止する"""
        self.running = False

        # 実行中のタスクをキャンセル
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        # WHILLデバイスを切断
        await self.whill.disconnect()

        logger.info("WHILL controller stopped")

    async def handle_osc_command(self, command: str, **kwargs) -> None:
        """
        OSCからのコマンドを処理する

        Args:
            command: コマンド名
            **kwargs: コマンドパラメータ
        """
        async with self.command_lock:
            await self._execute_command(command, **kwargs)

    async def handle_mqtt_command(self, command: str, **kwargs) -> None:
        """
        MQTTからのコマンドを処理する

        Args:
            command: コマンド名
            **kwargs: コマンドパラメータ
        """
        async with self.command_lock:
            await self._execute_command(command, **kwargs)

    async def _execute_command(self, command: str, **kwargs) -> None:
        """
        コマンドを実行する（内部メソッド）

        Args:
            command: コマンド名
            **kwargs: コマンドパラメータ
        """
        if command == "joystick":
            front = kwargs.get("front", 0)
            side = kwargs.get("side", 0)
            await self.whill.send_joystick(front=front, side=side)

        elif command == "power_on":
            await self.whill.send_power_on()

        elif command == "power_off":
            await self.whill.send_power_off()

        elif command == "emergency_stop":
            await self.whill.send_emergency_stop()

    async def change_port(self, new_port: str) -> bool:
        """
        WHILLデバイスの接続ポートを変更する

        Args:
            new_port: 新しいシリアルポート名

        Returns:
            bool: 接続成功状態
        """
        async with self.command_lock:
            logger.info(f"Changing WHILL port to: {new_port}")

            # 接続試行
            return await self.whill.reconnect(port=new_port)

    async def monitor_connection(self) -> None:
        """WHILLデバイスの接続状態を監視し、必要に応じて再接続を試みる"""
        reconnect_interval = 5  # 秒
        max_interval = 60  # 最大間隔（秒）
        current_interval = reconnect_interval

        while self.running:
            try:
                # 接続状態を確認
                if not self.whill.is_connected():
                    logger.info(f"WHILL device disconnected, attempting to reconnect in {current_interval}s...")
                    await asyncio.sleep(current_interval)

                    # 再接続を試みる
                    success = await self.whill.reconnect()

                    if success:
                        logger.info("Successfully reconnected to WHILL device")
                        current_interval = reconnect_interval  # 成功したら間隔をリセット
                    else:
                        # 接続失敗時は間隔を増やす（指数バックオフ）
                        current_interval = min(current_interval * 2, max_interval)
                else:
                    # 接続中は長めの間隔でチェック
                    await asyncio.sleep(10)
                    current_interval = reconnect_interval  # 接続中なら間隔をリセット

            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")
                await asyncio.sleep(current_interval)
