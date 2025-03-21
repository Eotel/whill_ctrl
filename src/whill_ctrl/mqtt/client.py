"""
MQTTクライアントの実装
WHILLコントローラーからの指示を受け取り、MQTTメッセージに応じてWHILLを制御する
"""

import asyncio
import json
from datetime import datetime

from aiomqtt import Client, Message, MqttError, Will
from loguru import logger

from ..controller.controller import WHILLController


class MQTTHandler:
    """MQTTクライアントハンドラー"""

    def __init__(
        self,
        controller: WHILLController,
        broker: str,
        port: int,
        command_topic: str,
        status_topic: str,
        ctrl_topic: str,
    ):
        """
        MQTTハンドラーを初期化

        Args:
            controller: WHILLコントローラーインスタンス
            broker: MQTTブローカーホスト名
            port: MQTTブローカーポート
            command_topic: コマンド受信用トピック
            status_topic: 状態通知用トピックのベースパス
            ctrl_topic: 制御コマンド受信用トピック
        """
        self.controller = controller
        self.broker = broker
        self.port = port
        self.command_topic = command_topic
        self.status_topic = status_topic
        self.ctrl_topic = ctrl_topic
        self.client = None
        self.running = False
        self.client_task = None

    async def start(self) -> bool:
        """MQTTクライアントを起動する"""
        self.running = True
        self.client_task = asyncio.create_task(self._run_mqtt_client())
        return True

    async def stop(self) -> None:
        """MQTTクライアントを停止する"""
        self.running = False
        if self.client_task:
            # タスクをキャンセルする前に最後のステータスを送信
            await self.publish_status(force_offline=True)
            self.client_task.cancel()
            try:
                await self.client_task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT client stopped")

    async def _run_mqtt_client(self) -> None:
        """MQTTクライアントのメインループ"""
        while self.running:
            try:
                # Last Willメッセージを設定
                will_payload = json.dumps(
                    {
                        "connected": False,
                        "port": self.controller.whill.port,
                        "mode": self.controller.whill.get_mode(),
                        "last_update": datetime.now().isoformat(),
                    }
                )

                will = Will(topic=f"{self.status_topic}/connection", payload=will_payload, qos=1, retain=True)

                # MQTTクライアントに接続
                async with Client(
                    hostname=self.broker, port=self.port, identifier=f"whill-controller-{id(self)}", will=will
                ) as client:
                    self.client = client

                    # コマンドトピックとコントロールトピックを購読
                    await self.client.subscribe(self.command_topic)
                    await self.client.subscribe(self.ctrl_topic)

                    logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
                    logger.info(f"Subscribed to topics: {self.command_topic} and {self.ctrl_topic}")

                    # 現在の状態を発行
                    await self.publish_status()

                    # メッセージ受信ループ
                    async for message in self.client.messages:
                        if not self.running:
                            break
                        await self._process_message(message)

            except MqttError as e:
                logger.error(f"MQTT connection error: {e}")
                logger.info("Reconnecting to MQTT broker in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected MQTT error: {e}")
                logger.info("Reconnecting to MQTT broker in 5 seconds...")
                await asyncio.sleep(5)

    async def _process_message(self, message: Message) -> None:
        """
        MQTTメッセージを処理する

        Args:
            message: 受信したMQTTメッセージ
        """
        topic = message.topic.value
        payload = message.payload.decode("utf-8").strip()

        logger.debug(f"Received MQTT message on topic {topic}: {payload}")

        # Retainメッセージのチェック（コマンド系のRetainは不要）
        if message.retain and topic.startswith("whill/commands/"):
            logger.warning(f"Ignoring retained command on topic {topic}")
            return

        # トピックに基づいて適切な処理を行う
        topic_parts = topic.split("/")
        if len(topic_parts) < 3:
            logger.warning(f"Unrecognized topic format: {topic}")
            return

        # WHILL制御コマンド
        if topic_parts[0] == "whill" and topic_parts[1] == "commands":
            command = topic_parts[2]

            if command == "joystick":
                # ペイロードからジョイスティック値を解析
                try:
                    values = payload.split(",")
                    if len(values) < 2:
                        raise ValueError("Joystick command requires two values: front,side")

                    front, side = map(int, values)
                    # 値の範囲を-100～100にクリッピング
                    front = max(min(front, 100), -100)
                    side = max(min(side, 100), -100)

                    logger.debug(f"[MQTT {topic}] Joystick command: front={front}, side={side}")
                    await self.controller.handle_mqtt_command("joystick", front=front, side=side)
                except Exception as e:
                    logger.error(f"Invalid joystick payload: {payload}, error: {e}")

            elif command == "power_on":
                logger.debug(f"[MQTT {topic}] Power on command received")
                await self.controller.handle_mqtt_command("power_on")

            elif command == "power_off":
                logger.debug(f"[MQTT {topic}] Power off command received")
                await self.controller.handle_mqtt_command("power_off")

            elif command == "emergency_stop":
                logger.debug(f"[MQTT {topic}] Emergency stop command received")
                await self.controller.handle_mqtt_command("emergency_stop")

            else:
                logger.warning(f"Unknown command in topic: {topic}")

        # WHILL制御系コマンド（設定変更など）
        elif topic_parts[0] == "whill" and topic_parts[1] == "ctrl":
            if len(topic_parts) >= 4 and topic_parts[2] == "serial" and topic_parts[3] == "change_port":
                await self.controller.change_port(payload)

    async def publish_status(self, force_offline: bool = False) -> None:
        """
        WHILLデバイスの現在の状態をMQTTで発行する

        Args:
            force_offline: 強制的にオフライン状態として発行するフラグ
        """
        if self.client is None:
            return

        try:
            # 基本的な状態情報を取得
            status = self.controller.whill.get_status()

            if force_offline:
                status["connected"] = False

            # 現在時刻を追加
            status["last_update"] = datetime.now().isoformat()

            # JSON形式に変換
            status_json = json.dumps(status)

            # 接続状態をパブリッシュ
            await self.client.publish(f"{self.status_topic}/connection", status_json, qos=1, retain=True)

            logger.debug(f"Published status: {status_json}")

        except Exception as e:
            logger.error(f"Error publishing status: {e}")
