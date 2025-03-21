#!/bin/bash
# WHILL Controller systemdサービス設定スクリプト

set -e  # エラー時に停止

# Root権限チェック
if [ "$(id -u)" -ne 0 ]; then
    echo "このスクリプトはroot権限で実行する必要があります。"
    echo "sudo $0 を実行してください。"
    exit 1
fi

# スクリプトのディレクトリを取得
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ユーザー確認
USER=${SUDO_USER:-$(whoami)}
HOME_DIR=$(eval echo ~"$USER")
echo "サービスを $USER ユーザーとして設定します。"
echo "ホームディレクトリ: $HOME_DIR"
echo "作業ディレクトリ: $SCRIPT_DIR"

# uvのインストール確認とインストール
UV_PATH="$HOME_DIR/.local/bin/uv"
if ! [ -x "$UV_PATH" ]; then
    echo "uv がインストールされていません。インストールします..."
    sudo -u "$USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo "uv がインストールされました。"
else
    echo "uv がインストール済みです: $UV_PATH"
fi

# パッケージのインストール確認
if ! sudo -u "$USER" "$UV_PATH" run -- python -c "import whill_ctrl" 2>/dev/null; then
    echo "whill_ctrlパッケージがインストールされていません。"
    echo "パッケージをインストールします: uv pip install -e ."
    cd "$SCRIPT_DIR"
    sudo -u "$USER" "$UV_PATH" pip install -e .

    # インストール後に再確認
    if ! sudo -u "$USER" "$UV_PATH" run -- python -c "import whill_ctrl" 2>/dev/null; then
        echo "パッケージのインストールに失敗しました。"
        exit 1
    fi
    echo "パッケージがインストールされました。"
else
    echo "whill_ctrlパッケージがインストール済みです。"
fi

# シリアルポートのデフォルト設定
DEFAULT_PORT="/dev/ttyUSB0"
read -p "WHILLのシリアルポートを指定してください [デフォルト: $DEFAULT_PORT]: " SERIAL_PORT
SERIAL_PORT=${SERIAL_PORT:-$DEFAULT_PORT}

# モックモードの確認
read -p "モックモードを使用しますか？ (y/N): " USE_MOCK
if [[ $USE_MOCK =~ ^[Yy]$ ]]; then
    MOCK_OPTION="--use-mock"
    echo "モックモードが有効化されました。"
else
    MOCK_OPTION=""
    echo "実機モードが選択されました。"
fi

# MQTT設定
read -p "MQTTブローカーのホスト名を指定してください [デフォルト: localhost]: " MQTT_HOST
MQTT_HOST=${MQTT_HOST:-localhost}
read -p "MQTTブローカーのポート番号を指定してください [デフォルト: 1883]: " MQTT_PORT
MQTT_PORT=${MQTT_PORT:-1883}

# OSC設定
read -p "OSCサーバーのIPアドレスを指定してください [デフォルト: 0.0.0.0]: " OSC_IP
OSC_IP=${OSC_IP:-0.0.0.0}
read -p "OSCサーバーのポート番号を指定してください [デフォルト: 5005]: " OSC_PORT
OSC_PORT=${OSC_PORT:-5005}

# サービスファイルの配置
cat > /etc/systemd/system/whill-ctrl.service << EOF
[Unit]
Description=WHILL Controller Service
After=network.target bluetooth.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$HOME_DIR/.local/bin/uv run -- whill-ctrl --serial-port $SERIAL_PORT --mqtt-broker $MQTT_HOST --mqtt-port $MQTT_PORT --osc-ip $OSC_IP --osc-port $OSC_PORT $MOCK_OPTION
Restart=always
RestartSec=10

# ログ関連の設定
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Mosquitto 設定ファイルのコピー
if [ -f "$SCRIPT_DIR/mosquitto.conf" ]; then
    echo "Mosquitto設定ファイルを配置します..."

    # Mosquitto ディレクトリの存在確認
    if [ ! -d "/etc/mosquitto/conf.d" ]; then
        echo "Mosquittoの設定ディレクトリが存在しません。作成します..."
        mkdir -p /etc/mosquitto/conf.d
    fi

    # 設定ファイルをコピー
    cp "$SCRIPT_DIR/mosquitto.conf" /etc/mosquitto/conf.d/whill-ctrl.conf
    echo "Mosquitto設定ファイルを /etc/mosquitto/conf.d/whill-ctrl.conf にコピーしました"

    # Mosquittoサービスの再起動（インストールされている場合）
    if systemctl list-unit-files | grep -q mosquitto; then
        echo "Mosquittoサービスを再起動します..."
        systemctl restart mosquitto
    else
        echo "Mosquittoサービスが見つかりません。手動でインストールと起動が必要かもしれません。"
        echo "  例: apt install mosquitto mosquitto-clients"
    fi
else
    echo "mosquitto.confファイルが見つかりません。Mosquitto設定はスキップします。"
fi

# ログディレクトリの作成
mkdir -p "$HOME_DIR"/logs
chown "$USER":"$USER" "$HOME_DIR"/logs

# systemd設定を再読み込み
systemctl daemon-reload

# サービスを有効化
systemctl enable whill-ctrl.service

# サービスを開始
systemctl start whill-ctrl.service

echo "インストール完了！"
echo "サービスステータスの確認: systemctl status whill-ctrl.service"
echo "ログの確認: journalctl -u whill-ctrl.service -f"
