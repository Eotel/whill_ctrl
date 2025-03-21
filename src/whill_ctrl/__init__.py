"""
WHILL Controller - OSCとMQTTによる電動車椅子WHILL制御アプリケーション

WHILLをOSCとMQTTの両方のプロトコルで制御するブリッジサーバー
"""

__version__ = "0.1.0"

# エントリポイントをパッケージルートから公開
from .core.app import main
