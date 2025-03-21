"""
アプリケーションのエントリポイント
コマンドラインインターフェースとアプリケーションの起動処理を提供
"""

import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

import asyncclick as click
from loguru import logger

from ..config import get_settings
from ..controller.controller import WHILLController
from ..mqtt.client import MQTTHandler
from ..osc.server import OSCServer
from ..utils.logger import setup_logger
from ..whill.factory import create_whill_device

# Windows環境の場合、正しいイベントループポリシーを設定
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Application:
    """アプリケーションのメインクラス"""

    def __init__(self):
        self.settings = get_settings()
        self.controller = None
        self.mqtt_handler = None
        self.osc_server = None
        self.shutdown_event = asyncio.Event()
        self.tasks = []

        # 設定ファイルパス
        self.config_dir = Path.home() / ".config" / "whill_ctrl"
        self.config_file = self.config_dir / "settings.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """設定ファイルを読み込む"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.config_file.exists():
            # デフォルト設定
            default_config = {"last_serial_port": "/dev/ttyUSB0"}
            self._save_config(default_config)
            return default_config

        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
            return {"last_serial_port": "/dev/ttyUSB0"}

    def _save_config(self, config: dict):
        """設定ファイルを保存する"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"設定ファイルの保存に失敗しました: {e}")

    def get_last_serial_port(self) -> str:
        """最後に使用したシリアルポートを取得する"""
        return self.config.get("last_serial_port", "/dev/ttyUSB0")

    def save_last_serial_port(self, port: str):
        """最後に使用したシリアルポートを保存する"""
        self.config["last_serial_port"] = port
        self._save_config(self.config)

    async def initialize(
        self,
        serial_port: str | None,
        osc_ip: str,
        osc_port: int,
        mqtt_broker: str,
        mqtt_port: int,
        mqtt_topic: str,
        use_mock: bool,
        osc_only: bool,
        mqtt_only: bool,
    ) -> bool:
        """
        アプリケーションを初期化する

        Args:
            serial_port: WHILLデバイスのシリアルポート（Noneの場合は前回値を使用）
            osc_ip: OSCサーバーのバインドIPアドレス
            osc_port: OSCサーバーのポート番号
            mqtt_broker: MQTTブローカーのホスト名
            mqtt_port: MQTTブローカーのポート番号
            mqtt_topic: MQTTコマンドトピック
            use_mock: モックWHILLを使用するフラグ
            osc_only: OSCのみ使用するフラグ
            mqtt_only: MQTTのみ使用するフラグ

        Returns:
            bool: 初期化成功状態
        """
        try:
            # シリアルポートが指定されていない場合は前回値を使用
            if serial_port is None:
                serial_port = self.get_last_serial_port()
                logger.info(f"シリアルポートが指定されていないため、前回値を使用します: {serial_port}")
            else:
                # 指定されたポートを保存
                self.save_last_serial_port(serial_port)

            # WHILLデバイスを作成
            whill_device = create_whill_device(serial_port, use_mock)

            # コントローラーを初期化
            self.controller = WHILLController(whill_device)
            await self.controller.start()

            # OSCサーバーを初期化（MQTTのみモードでなければ）
            if not mqtt_only:
                self.osc_server = OSCServer(self.controller, osc_ip, osc_port)
                await self.osc_server.start()

            # MQTTハンドラーを初期化（OSCのみモードでなければ）
            if not osc_only:
                self.mqtt_handler = MQTTHandler(
                    self.controller,
                    mqtt_broker,
                    mqtt_port,
                    mqtt_topic,
                    self.settings.mqtt_status_topic,
                    self.settings.mqtt_ctrl_topic,
                )
                await self.mqtt_handler.start()

            return True

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            return False

    def register_signal_handlers(self):
        """シグナルハンドラーを登録する"""
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self._handle_shutdown)

    def _handle_shutdown(self, sig=None, frame=None):
        """シャットダウンを処理する"""
        logger.info("Shutdown signal received, closing connections...")
        asyncio.create_task(self._shutdown())

    async def _shutdown(self):
        """アプリケーションをシャットダウンする"""
        # シャットダウンイベントをセット（先に設定して、他のタスクが終了を確認できるようにする）
        self.shutdown_event.set()

        try:
            # MQTTハンドラーを停止
            if self.mqtt_handler:
                await self.mqtt_handler.stop()

            # OSCサーバーを停止
            if self.osc_server:
                self.osc_server.stop()

            # コントローラーを停止
            if self.controller:
                await self.controller.stop()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def run(self):
        """
        アプリケーションを実行する
        シャットダウンイベントが発火するまで待機
        """
        try:
            # シャットダウンイベントを待機
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            # キャンセルされた場合は静かに終了（トレースバックを表示しない）
            logger.debug("Application run task was cancelled")


# Command-line interface using asyncclick.
@click.command()
@click.option(
    "--serial-port",
    type=str,
    required=False,
    help="Serial port for the WHILL device (e.g. /dev/ttyUSB0). If not specified, uses the last known port.",
)
@click.option(
    "--osc-ip",
    type=str,
    default="0.0.0.0",
    show_default=True,
    help="IP address on which to bind the OSC server",
)
@click.option(
    "--osc-port",
    type=int,
    default=5005,
    show_default=True,
    help="Port number for the OSC server",
)
@click.option(
    "--mqtt-broker",
    type=str,
    default="localhost",
    show_default=True,
    help="MQTT broker hostname",
)
@click.option(
    "--mqtt-port",
    type=int,
    default=1883,
    show_default=True,
    help="MQTT broker port",
)
@click.option(
    "--mqtt-topic",
    type=str,
    default="whill/commands/#",
    show_default=True,
    help="MQTT topic to subscribe for WHILL commands",
)
@click.option(
    "--use-mock",
    is_flag=True,
    default=False,
    help="Use the mock WHILL implementation instead of the actual device",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug mode with additional logging",
)
@click.option(
    "--osc-only",
    is_flag=True,
    default=False,
    help="Use only OSC server (no MQTT)",
)
@click.option(
    "--mqtt-only",
    is_flag=True,
    default=False,
    help="Use only MQTT client (no OSC)",
)
async def main(serial_port, osc_ip, osc_port, mqtt_broker, mqtt_port, mqtt_topic, use_mock, debug, osc_only, mqtt_only):
    """
    WHILL Controller with OSC and MQTT support

    This script can set up both an OSC server and MQTT client to control a WHILL device.
    Both interfaces access the same WHILL instance, allowing control from multiple sources.

    OSC endpoints:
      /whill/joystick   -> expects two numbers; interprets x as 'side' and y as 'front'
      /whill/power_on   -> turns on the WHILL
      /whill/power_off  -> turns off the WHILL
      /whill/emergency_stop -> stops the WHILL immediately (set velocity to 0)

    MQTT topics:
      whill/commands/joystick -> payload: "front,side" (-100 to 100 for each)
      whill/commands/power_on -> any payload
      whill/commands/power_off -> any payload
      whill/commands/emergency_stop -> any payload

    MQTT status topics:
      whill/status/connection -> JSON with connection status info

    MQTT control topics:
      whill/ctrl/serial/change_port -> payload: port name (e.g. "/dev/ttyUSB1")
    """
    # ロガーの設定
    setup_logger(debug_mode=debug)

    logger.info("=== WHILL Controller 起動 ===")
    logger.info(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 設定を取得
    settings = get_settings()

    # 設定ディレクトリの作成
    settings.ensure_config_dirs()

    # Check that not both --osc-only and --mqtt-only are set
    if osc_only and mqtt_only:
        logger.error("Cannot set both --osc-only and --mqtt-only")
        return

    # グローバル例外ハンドラーを設定
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(custom_exception_handler)

    try:
        # アプリケーションを初期化
        app = Application()
        success = await app.initialize(
            serial_port, osc_ip, osc_port, mqtt_broker, mqtt_port, mqtt_topic, use_mock, osc_only, mqtt_only
        )

        if not success:
            logger.error("Application initialization failed")
            return

        # シグナルハンドラーを登録
        app.register_signal_handlers()

        # アプリケーションを実行
        await app.run()

    except asyncio.CancelledError:
        # キャンセルされた場合は静かに終了
        pass
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("WHILL Controller shutdown complete")


def custom_exception_handler(loop, context):
    """非同期例外のカスタムハンドラー"""
    # CancelledError は特別扱い（静かに終了）
    exception = context.get("exception")
    if isinstance(exception, asyncio.CancelledError):
        logger.debug("A task was cancelled (expected during shutdown)")
        return

    # その他の例外は通常どおり処理
    msg = context.get("message")
    if exception:
        formatted_exception = f"{type(exception).__name__}: {exception}"
    else:
        formatted_exception = "Unknown exception"

    task = context.get("task")
    logger.error(f"Unhandled exception in {task}: {msg or formatted_exception}")
