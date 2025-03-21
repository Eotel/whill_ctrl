"""
ロギングユーティリティモジュール
"""

import sys

from loguru import logger

from ..config import get_settings

settings = get_settings()


def setup_logger(debug_mode: bool = False):
    """ロガーの設定"""
    logger.remove()

    # コンソール出力の設定
    log_level = "DEBUG" if debug_mode else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # ファイル出力の設定（ログローテーション付き）
    # debugモードの場合のみDEBUGレベル、それ以外はINFOレベル
    file_log_level = "DEBUG" if debug_mode else "INFO"
    log_file = settings.log_dir / settings.log_file_pattern
    logger.add(
        str(log_file),
        rotation="00:00",  # 日単位でローテーション
        retention="30 days",  # 30日間保持
        compression="zip",  # ログファイルを圧縮
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level=file_log_level,  # デバッグレベルまたはINFOレベル
        backtrace=True,  # エラー時にトレースバックを表示
        enqueue=True,  # 非同期処理に対応
    )

    # ログディレクトリの作成
    settings.log_dir.mkdir(exist_ok=True)
