"""
WHILLデバイスのファクトリクラス
必要に応じて実機またはモックインスタンスを提供
"""

from loguru import logger

from .interface import AbstractWHILL
from .mock import MockWHILL
from .real import RealWHILL


def create_whill_device(port: str, use_mock: bool = False) -> AbstractWHILL:
    """
    WHILLデバイスのインスタンスを作成する

    Args:
        port: シリアルポート名
        use_mock: モックを使用するかどうか

    Returns:
        WHILLデバイスインターフェース
    """
    if use_mock:
        logger.info(f"Creating mock WHILL device for port {port}")
        return MockWHILL(port)
    else:
        logger.info(f"Creating real WHILL device for port {port}")
        try:
            return RealWHILL(port)
        except Exception as e:
            logger.error(f"Failed to create real WHILL device: {e}")
            raise
