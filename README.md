# WHILL Controller

OSCとMQTTを使って電動車椅子WHILLを制御するブリッジサーバー

## 機能

- MQTTとOSCの両方のプロトコルをサポート
- 実機またはモックモードで動作
- WebUI経由での操作に対応
- シリアルポートの動的変更が可能
- systemdサービスとしてインストール可能

## インストール

### 依存パッケージ

- Python 3.8以上
- uv (pip/venvの代替パッケージマネージャ)
- Mosquitto MQTT ブローカー (WebSocket対応)

### 直接実行

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/whill_ctrl.git
cd whill_ctrl

# uvで依存関係をインストール
uv sync

# 実行
uv run -- whill-ctrl --serial-port /dev/ttyUSB0 --use-mock
```

### systemdサービスとしてインストール

```bash
sudo ./install.sh
```

このスクリプトは以下を行います：

- uvが存在しない場合はインストールします
- パッケージをインストールします
- systemdサービスファイルを作成します
- mosquittoの設定ファイルを配置します
- サービスを有効化して起動します

## 使用方法

### コマンドラインオプション

```
Usage: whill-ctrl [OPTIONS]

  WHILL Controller with OSC and MQTT support

Options:
  --serial-port TEXT      Serial port for the WHILL device (e.g. /dev/ttyUSB0).
                          If not specified, uses the last known port.
  --osc-ip TEXT           IP address on which to bind the OSC server
                          [default: 0.0.0.0]
  --osc-port INTEGER      Port number for the OSC server  [default: 5005]
  --mqtt-broker TEXT      MQTT broker hostname  [default: localhost]
  --mqtt-port INTEGER     MQTT broker port  [default: 1883]
  --mqtt-topic TEXT       MQTT topic to subscribe for WHILL commands
                          [default: whill/commands/#]
  --use-mock              Use the mock WHILL implementation instead of the
                          actual device
  --debug                 Enable debug mode with additional logging
  --osc-only              Use only OSC server (no MQTT)
  --mqtt-only             Use only MQTT client (no OSC)
  --help                  Show this message and exit.
```

### OSCエンドポイント

- `/whill/joystick` - ジョイスティック制御 (x, y値: -1.0〜1.0)
- `/whill/power_on` - 電源ON
- `/whill/power_off` - 電源OFF
- `/whill/emergency_stop` - 緊急停止

### MQTTトピック

- `whill/commands/joystick` - ジョイスティック制御 (ペイロード: "front,side" 例: "50,-20")
- `whill/commands/power_on` - 電源ON
- `whill/commands/power_off` - 電源OFF
- `whill/commands/emergency_stop` - 緊急停止
- `whill/ctrl/serial/change_port` - シリアルポート変更（ペイロード: ポート名）

### ステータストピック

- `whill/status/connection` - 接続状態（JSON形式）

## WebUIの使用方法

付属のWebUIを使用してブラウザからWHILLを操作できます：

```bash
# HTTPサーバーを起動
cd web
python -m http.server 8000

# ブラウザでアクセス
# http://localhost:8000/whill_controller.html
```

## サービス管理

systemdサービスとしてインストールした場合：

```bash
# サービスの状態確認
sudo systemctl status whill-ctrl

# サービスの起動
sudo systemctl start whill-ctrl

# サービスの停止
sudo systemctl stop whill-ctrl

# サービスの再起動
sudo systemctl restart whill-ctrl

# ログの確認
journalctl -u whill-ctrl -f
```

## トラブルシューティング

### シリアルポートに接続できない

- ポート名が正しいか確認してください
- 権限の問題がある場合は、ユーザーをdialoutグループに追加してください: `sudo usermod -a -G dialout $USER`

### MQTTに接続できない

- mosquittoが起動しているか確認してください: `systemctl status mosquitto`
- WebSocket機能が有効になっているか確認してください
- ファイアウォールが9000ポートを許可しているか確認してください

### OSCが受信できない

- ファイアウォールが5005ポートを許可しているか確認してください
- OSCクライアントが正しいIPアドレスとポートを使用しているか確認してください
