import network, socket, uasyncio as asyncio
from machine import Pin, PWM
import json

# ==== WiFi AP設定 ====
ap = network.WLAN(network.AP_IF)
ap.config(essid='PicoPWM', password='12345678')
ap.active(True)
print('AP started:', ap.ifconfig())

# ==== PWM初期化 ====
pwm5 = PWM(Pin(5))
pwm6 = PWM(Pin(6))
pwm5.freq(1000)
pwm6.freq(1000)

# ==== HTTPサーバー ====
HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pico PWM Controller</title>
<style>
  body { font-family: sans-serif; text-align: center; margin: 30px auto; max-width: 400px; }
  input[type=range] { width: 100%; height: 40px; touch-action: none; }
  .value { font-size: 20px; font-weight: bold; color: #333; }
</style>
</head>
<body>
<h2>Pico PWM Controller</h2>
<p>GPIO 5<br>
<input type="range" id="slider1" min="0" max="65535" value="0">
<br><span class="value" id="val1">0</span></p>
<p>GPIO 6<br>
<input type="range" id="slider2" min="0" max="65535" value="0">
<br><span class="value" id="val2">0</span></p>
<p id="status">Connecting...</p>
<script>
let ws;
function connect() {
  ws = new WebSocket("ws://" + location.hostname + ":81/ws");
  
  ws.onopen = () => {
    console.log("Connected to Pico");
    document.getElementById("status").textContent = "Connected";
    document.getElementById("status").style.color = "green";
  };
  
  ws.onclose = () => {
    console.log("Disconnected");
    document.getElementById("status").textContent = "Disconnected - Retrying...";
    document.getElementById("status").style.color = "red";
    setTimeout(connect, 2000);
  };
  
  ws.onerror = (e) => {
    console.log("WebSocket error", e);
  };
}

function sendValues() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const v1 = parseInt(slider1.value);
    const v2 = parseInt(slider2.value);
    ws.send(JSON.stringify({ g5: v1, g6: v2 }));
    document.getElementById("val1").textContent = v1;
    document.getElementById("val2").textContent = v2;
  }
}

slider1.oninput = sendValues;
slider2.oninput = sendValues;

connect();
</script>
</body>
</html>
"""

async def handle_http(reader, writer):
    try:
        req = await reader.readline()
        if not req:
            await writer.aclose()
            return
        
        # HTTPヘッダの読み飛ばし
        while True:
            line = await reader.readline()
            if line == b'\r\n' or not line:
                break
        
        # index.htmlを返す
        writer.write(b'HTTP/1.1 200 OK\r\n')
        writer.write(b'Content-Type: text/html; charset=utf-8\r\n')
        writer.write(b'Connection: close\r\n\r\n')
        writer.write(HTML)
        await writer.drain()
    except Exception as e:
        print("HTTP error:", e)
    finally:
        await writer.aclose()

async def http_server():
    print("HTTP server starting on port 80")
    server = await asyncio.start_server(handle_http, '0.0.0.0', 80)
    print("HTTP server started")
    await server.wait_closed()

# ==== WebSocketサーバー(リアルタイムで通信を行う) ====
async def handle_websocket(reader, writer):
    try:
        # HTTPリクエストを読む
        req = b''
        while True:
            line = await reader.readline()
            req += line
            if line == b'\r\n':
                break
        
        # WebSocketハンドシェイク
        if b"Upgrade: websocket" not in req:
            await writer.aclose()
            return
        
        # Sec-WebSocket-Keyを抽出
        key = None
        for line in req.split(b'\r\n'):
            if b'Sec-WebSocket-Key:' in line:
                key = line.split(b': ')[1]
                break
        
        if not key:
            await writer.aclose()
            return
        
        # ハンドシェイク応答
        import ubinascii, hashlib
        accept = ubinascii.b2a_base64(
            hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
        ).strip()
        
        resp = b"HTTP/1.1 101 Switching Protocols\r\n" \
               b"Upgrade: websocket\r\n" \
               b"Connection: Upgrade\r\n" \
               b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n"
        writer.write(resp)
        await writer.drain()
        
        print("WebSocket client connected")
        
        # データ受信ループ
        while True:
            # フレームヘッダを読む
            header = await reader.readexactly(2)
            if not header:
                break
            
            payload_len = header[1] & 127
            
            # マスクキーを読む
            mask = await reader.readexactly(4)
            
            # ペイロードを読む
            enc_payload = await reader.readexactly(payload_len)
            
            # デコード
            decoded = bytes(b ^ mask[i % 4] for i, b in enumerate(enc_payload))
            
            try:
                msg = json.loads(decoded)
                if "g5" in msg:
                    pwm5.duty_u16(msg["g5"])
                if "g6" in msg:
                    pwm6.duty_u16(msg["g6"])
            except Exception as e:
                print("JSON parse error:", e)
                
    except Exception as e:
        print("WebSocket error:", e)
    finally:
        # WebSocket切断時にPWMを0にリセット
        pwm5.duty_u16(0)
        pwm6.duty_u16(0)
        print("PWM reset to 0")
        await writer.aclose()
        print("WebSocket client disconnected")

async def ws_server():
    print("WebSocket server starting on port 81")
    server = await asyncio.start_server(handle_websocket, '0.0.0.0', 81)
    print("WebSocket server started")
    await server.wait_closed()

# ==== メイン ====
async def main():
    asyncio.create_task(http_server())
    await ws_server()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nServer stopped")
