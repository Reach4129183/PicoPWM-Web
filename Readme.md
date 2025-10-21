# WebSocketを利用してリアルタイムでGPIOを制御する

ssid=PicoPWM

password=12345678

IP=192.168.4.1


https://github.com/user-attachments/assets/8b7a6d24-a129-4077-a73a-60aabc266426



下記のプロンプトでChatGPTが出力したコードに変更を加えたものです。
```
MicroPythonでRaspiPico2Wを制御する
AsyncWiFiAP+Webサーバーを立ち上げ
その中で2つのスライダーを表示する
PWMでG5,G6をスライダーに合わせて変化させる
クライアントとはWebSocketで通信する
```


> [!TIP]
> WebサーバーとAPを非同期処理で行うことで安定性の向上


> [!TIP]
> WebSocket通信によりリアルタイムで値を送信
