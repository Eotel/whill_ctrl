"""
設定と定数を管理するモジュール
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MQTTブローカー設定
    mqtt_broker: str = Field("localhost", description="MQTTブローカーのホスト名")
    mqtt_port: int = Field(1883, description="MQTTブローカーのポート番号")
    mqtt_topic: str = Field("turntable/command", description="BLEデバイスへのコマンドトピック名")

    # ログ設定
    log_dir: Path = Field(Path("logs"), description="ログディレクトリのパス")
    log_file_pattern: str = Field("whill_ctrl_{time:YYYY-MM-DD}.log", description="ログファイル名のパターン")

    # アプリケーション設定ディレクトリの作成
    def ensure_config_dirs(self):
        """設定ファイルを保存するディレクトリが存在することを確認"""
        os.makedirs(self.log_dir, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
