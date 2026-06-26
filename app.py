import time
import httpx
import json
import threading
from collections import defaultdict
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from cachetools import TTLCache
from typing import Tuple
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
import base64

# === Settings ===

MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB54"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EUROPE"}

# === Flask App Setup ===

app = Flask(__name__)
CORS(app)
cache = TTLCache(maxsize=100, ttl=300)
cached_tokens = defaultdict(dict)

# === Persistent sync httpx client with connection pooling ===
_sync_client = httpx.Client(
    timeout=httpx.Timeout(8.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
)

# === Homepage HTML ===

HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Premium FF Nickname Checker</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-dark: #0f172a;
    --glass-bg: rgba(30, 41, 59, 0.45);
    --glass-border: rgba(255, 255, 255, 0.1);
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    --accent-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    --accent-hover: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%);
    --text-primary: #ffffff;
    --text-secondary: #94a3b8;
    --success-bg: rgba(16, 185, 129, 0.15);
    --success-border: rgba(16, 185, 129, 0.4);
    --success-text: #34d399;
    --error-bg: rgba(239, 68, 68, 0.15);
    --error-border: rgba(239, 68, 68, 0.4);
    --error-text: #f87171;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: var(--bg-dark);
    color: var(--text-primary);
    font-family: 'Poppins', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    overflow-x: hidden;
    position: relative;
  }

  /* Animated Glassmorphism Background Shapes */
  .bg-shape {
    position: absolute;
    border-radius: 50%;
    filter: blur(100px);
    z-index: 0;
    animation: float 20s infinite ease-in-out alternate;
  }
  .shape-1 {
    width: 400px; height: 400px;
    background: rgba(99, 102, 241, 0.4);
    top: -10%; left: -10%;
  }
  .shape-2 {
    width: 500px; height: 500px;
    background: rgba(168, 85, 247, 0.3);
    bottom: -20%; right: -10%;
    animation-delay: -5s;
  }
  .shape-3 {
    width: 300px; height: 300px;
    background: rgba(56, 189, 248, 0.3);
    top: 40%; left: 60%;
    animation-duration: 25s;
  }

  @keyframes float {
    0% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(30px, -50px) scale(1.1); }
    100% { transform: translate(-30px, 30px) scale(0.9); }
  }

  .container {
    width: 100%;
    max-width: 540px;
    position: relative;
    z-index: 10;
    animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  @keyframes slideUp {
    0% { opacity: 0; transform: translateY(40px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  /* Main Glass Card */
  .glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--glass-border);
    border-radius: 32px;
    padding: 40px;
    box-shadow: var(--glass-shadow);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }

  .header { text-align: center; margin-bottom: 32px; }

  .logo-wrapper {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 16px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    position: relative;
    overflow: hidden;
  }
  
  .logo-wrapper::before {
    content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: shine 3s infinite;
  }

  @keyframes shine {
    100% { left: 100%; }
  }

  .logo-wrapper svg {
    width: 32px; height: 32px;
    color: #a855f7;
    filter: drop-shadow(0 0 8px rgba(168, 85, 247, 0.6));
  }

  h1 {
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 8px;
    background: linear-gradient(to right, #fff, #cbd5e1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .subtitle { font-size: 14px; color: var(--text-secondary); font-weight: 400; }

  .field-label {
    font-size: 13px; font-weight: 500; color: var(--text-secondary);
    margin-bottom: 12px; display: block; padding-left: 4px;
  }

  .input-group { display: flex; gap: 16px; margin-bottom: 28px; }

  .input-control {
    background: rgba(15, 23, 42, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-primary);
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    padding: 16px 20px;
    border-radius: 18px;
    outline: none;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    backdrop-filter: blur(10px);
  }

  .uid-input { flex: 1; width: 100%; }
  .uid-input::placeholder { color: rgba(148, 163, 184, 0.5); font-family: 'Poppins', sans-serif; font-size: 15px;}

  .region-select {
    width: 120px; cursor: pointer; appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 16px center; background-size: 16px;
    padding-right: 40px; font-family: 'Poppins', sans-serif; font-weight: 500;
  }
  .region-select option { background: #1e293b; color: white; }

  .input-control:focus {
    border-color: #818cf8;
    background: rgba(15, 23, 42, 0.6);
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
    transform: translateY(-2px);
  }

  /* Flutter-style Elevated Button */
  .btn {
    width: 100%;
    padding: 18px;
    background: var(--accent-gradient);
    color: white;
    border: none;
    border-radius: 18px;
    font-family: 'Poppins', sans-serif;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.5px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    display: flex; align-items: center; justify-content: center; gap: 12px;
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
    position: relative; overflow: hidden;
  }

  .btn::after {
    content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    background: linear-gradient(to bottom, rgba(255,255,255,0.2) 0%, transparent 100%);
    border-radius: 18px; opacity: 0; transition: opacity 0.3s;
  }

  .btn:hover:not(:disabled) {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 12px 28px rgba(99, 102, 241, 0.4);
    background: var(--accent-hover);
  }
  .btn:hover:not(:disabled)::after { opacity: 1; }
  .btn:active:not(:disabled) { transform: translateY(0) scale(0.98); }
  .btn:disabled { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); cursor: not-allowed; box-shadow: none; }

  /* Animated Result Box */
  .result-box {
    margin-top: 24px; padding: 24px; border-radius: 20px;
    display: none; opacity: 0; transform: translateY(15px);
    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter: blur(12px);
  }
  .result-box.visible { display: block; opacity: 1; transform: translateY(0); }
  .result-box.success { background: var(--success-bg); border: 1px solid var(--success-border); box-shadow: 0 10px 30px rgba(16, 185, 129, 0.1); }
  .result-box.error { background: var(--error-bg); border: 1px solid var(--error-border); box-shadow: 0 10px 30px rgba(239, 68, 68, 0.1); }

  .result-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; color: var(--text-secondary); }
  .result-nickname { font-size: 28px; font-weight: 700; color: var(--text-primary); word-break: break-all; line-height: 1.3; margin-bottom: 8px; }
  .result-box.success .result-nickname { background: linear-gradient(to right, #34d399, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .result-meta { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-secondary); opacity: 0.8; }
  .error-text { font-size: 16px; color: var(--error-text); }

  /* Inner Glass Tutorial Section */
  .tutorial {
    background: rgba(15, 23, 42, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 24px;
    padding: 28px;
    margin-top: 32px;
  }
  .tutorial-header { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
  .tutorial-header::before {
    content: ''; display: inline-block; width: 10px; height: 10px;
    background: linear-gradient(135deg, #6366f1, #a855f7); border-radius: 50%;
    box-shadow: 0 0 10px rgba(168, 85, 247, 0.5);
  }

  .code-block {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 16px;
    display: flex; align-items: center; justify-content: space-between;
    transition: background 0.3s;
  }
  .code-block:hover { background: rgba(0, 0, 0, 0.4); border-color: rgba(255,255,255,0.1); }
  .code-text { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-secondary); word-break: break-all; padding-right: 16px; line-height: 1.5; }
  .code-text span { color: #818cf8; font-weight: 500; }

  .copy-btn {
    background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-primary); font-family: 'Poppins', sans-serif; font-size: 12px; font-weight: 500;
    padding: 8px 16px; border-radius: 10px; cursor: pointer; transition: all 0.2s; backdrop-filter: blur(4px);
  }
  .copy-btn:hover { background: rgba(99, 102, 241, 0.2); color: #818cf8; border-color: rgba(99, 102, 241, 0.4); transform: scale(1.05); }

  .footer { margin-top: 32px; text-align: center; display: flex; flex-direction: column; gap: 8px; z-index: 10; }
  .status {
    display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    background: rgba(15, 23, 42, 0.4); padding: 8px 16px; border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.05); backdrop-filter: blur(10px);
    font-size: 12px; font-weight: 500; color: var(--text-secondary); margin: 0 auto;
  }
  .status-dot {
    width: 8px; height: 8px; background: var(--success-text); border-radius: 50%;
    box-shadow: 0 0 12px var(--success-text); animation: pulse-dot 2s infinite;
  }
  @keyframes pulse-dot { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.2); } 100% { opacity: 1; transform: scale(1); } }
  .dev-credit { font-size: 12px; font-weight: 600; letter-spacing: 1px; color: rgba(255, 255, 255, 0.4); margin-top: 4px; }

  .spinner {
    width: 20px; height: 20px; border: 3px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff; border-radius: 50%; animation: spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }
  @keyframes spin { 100% { transform: rotate(360deg); } }

  @media (max-width: 500px) {
    .glass-card { padding: 30px 24px; border-radius: 24px; }
    .input-group { flex-direction: column; gap: 12px; }
    .region-select { width: 100%; }
    h1 { font-size: 26px; }
    .tutorial { padding: 20px; margin-top: 24px; }
    .code-block { flex-direction: column; align-items: flex-start; gap: 12px; }
    .copy-btn { align-self: flex-end; }
  }
</style>
</head>
<body>

<div class="bg-shape shape-1"></div>
<div class="bg-shape shape-2"></div>
<div class="bg-shape shape-3"></div>

<div class="container">
  <div class="glass-card">
    <div class="header">
      <div class="logo-wrapper">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5" />
        </svg>
      </div>
      <h1>Nickname Checker</h1>
      <p class="subtitle">Premium API Lookup System &bull; Fast & Secure</p>
    </div>

    <span class="field-label">Player UID & Region</span>
    <div class="input-group">
      <input
        class="input-control uid-input"
        id="uidInput"
        type="text"
        placeholder="Enter Player UID..."
        maxlength="20"
        inputmode="numeric"
        autocomplete="off"
      />
      <select class="input-control region-select" id="regionSelect">
        <option value="IND">IND</option>
        <option value="BD" selected>BD</option>
        <option value="BR">BR</option>
        <option value="CIS">CIS</option>
        <option value="EUROPE">EU</option>
        <option value="ID">ID</option>
        <option value="ME">ME</option>
        <option value="NA">NA</option>
        <option value="PK">PK</option>
        <option value="RU">RU</option>
        <option value="SAC">SAC</option>
        <option value="SG">SG</option>
        <option value="TH">TH</option>
        <option value="TW">TW</option>
        <option value="US">US</option>
        <option value="VN">VN</option>
      </select>
    </div>

    <button class="btn" id="checkBtn" onclick="checkNickname()">
      <span id="btnText">Verify Nickname</span>
    </button>

    <div class="result-box" id="resultBox">
      <div class="result-label" id="resultLabel">Result</div>
      <div class="result-nickname" id="resultNickname"></div>
      <div class="result-meta" id="resultMeta"></div>
    </div>

    <div class="tutorial">
      <div class="tutorial-header">Developer API Guide</div>
      
      <div class="code-block">
        <div class="code-text">/<span>{REGION}</span>/player-name?uid=<span>{UID}</span></div>
        <button class="copy-btn" onclick="copyText('/{REGION}/player-name?uid={UID}', this)">Copy</button>
      </div>

      <div class="code-block">
        <div class="code-text">https://nickname-checker-ob53.vercel.app/<span>BD</span>/player-name?uid=<span>2815662785</span></div>
        <button class="copy-btn" onclick="copyText('https://nickname-checker-ob53.vercel.app/BD/player-name?uid=2815662785', this)">Copy</button>
      </div>
    </div>
  </div>

  <div class="footer">
    <div class="status">
      <span class="status-dot"></span>
      API Services Online
    </div>
    <div class="dev-credit">DESIGNED & DEVELOPED BY 7H SIAM</div>
  </div>
</div>

<script>
  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      btn.style.color = '#fff';
      btn.style.backgroundColor = 'rgba(99, 102, 241, 0.4)';
      btn.style.borderColor = 'rgba(99, 102, 241, 0.8)';
      setTimeout(() => { 
        btn.textContent = orig; 
        btn.style.color = ''; 
        btn.style.backgroundColor = '';
        btn.style.borderColor = ''; 
      }, 2000);
    });
  }

  const uidInput   = document.getElementById('uidInput');
  const checkBtn   = document.getElementById('checkBtn');
  const btnText    = document.getElementById('btnText');
  const resultBox  = document.getElementById('resultBox');
  const resultNick = document.getElementById('resultNickname');
  const resultMeta = document.getElementById('resultMeta');
  const resultLabel = document.getElementById('resultLabel');

  uidInput.addEventListener('keydown', e => { if (e.key === 'Enter') checkNickname(); });

  async function checkNickname() {
    const uid    = uidInput.value.trim();
    const region = document.getElementById('regionSelect').value;

    if (!uid) {
      showError('Please enter a valid UID.');
      return;
    }
    if (!/^\d+$/.test(uid)) {
      showError('UID must contain numbers only.');
      return;
    }

    setLoading(true);
    resultBox.className = 'result-box'; 

    try {
      const res  = await fetch(`/${region}/player-name?uid=${encodeURIComponent(uid)}`);
      const data = await res.json();

      if (!res.ok || data.error) {
        showError(data.error || 'Player not found.');
      } else {
        setTimeout(() => {
          resultBox.classList.add('visible', 'success');
          resultLabel.textContent = 'Player Discovered';
          resultNick.textContent = data.nickname || '—';
          resultMeta.textContent = `UID: ${uid} • Region: ${region}`;
        }, 150); 
      }
    } catch (err) {
      showError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function showError(msg) {
    setTimeout(() => {
      resultBox.classList.add('visible', 'error');
      resultLabel.textContent = 'Lookup Failed';
      resultNick.innerHTML = `<span class="error-text">${msg}</span>`;
      resultMeta.textContent = '';
    }, 150);
  }

  function setLoading(state) {
    checkBtn.disabled = state;
    if(state) {
        checkBtn.innerHTML = '<div class="spinner"></div><span id="btnText">Connecting...</span>';
    } else {
        checkBtn.innerHTML = '<span id="btnText">Verify Nickname</span>';
    }
  }
</script>
</body>
</html>"""

# === Helper Functions ===

def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance

def json_to_proto_sync(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def get_account_credentials(region: str) -> str:
    r = region.upper()
    if r == "IND":
        return "uid=3933356115&password=CA6DDAEE7F32A95D6BC17B15B8D5C59E091338B4609F25A1728720E8E4C107C4"
    elif r in {"BR", "US", "SAC", "NA"}:
        return "uid=4044223479&password=EB067625F1E2CB705C7561747A46D502480DC5D41497F4C90F3FDBC73B8082ED"
    else:
        return "uid=4298793342&password=7H_SIAM_M66FX_BY_SPIDEERIO_GAMING_92NWR"

# === Token Generation (sync) ===

def get_access_token_sync(account: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/x-www-form-urlencoded"
    }
    resp = _sync_client.post(url, data=payload, headers=headers)
    data = resp.json()
    return data.get("access_token", "0"), data.get("open_id", "0")

def create_jwt_sync(region: str):
    account = get_account_credentials(region)
    token_val, open_id = get_access_token_sync(account)
    body = json.dumps({"open_id": open_id, "open_id_type": "4", "login_token": token_val, "orign_platform_type": "4"})
    proto_bytes = json_to_proto_sync(body, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'Expect': "100-continue",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': RELEASEVERSION
    }
    resp = _sync_client.post(url, data=payload, headers=headers)
    msg = json.loads(json_format.MessageToJson(decode_protobuf(resp.content, FreeFire_pb2.LoginRes)))
    cached_tokens[region] = {
        'token': f"Bearer {msg.get('token','0')}",
        'region': msg.get('lockRegion','0'),
        'server_url': msg.get('serverUrl','0'),
        'expires_at': time.time() + 25200
    }

def initialize_tokens_sync():
    print("[*] Initializing tokens for all regions...")
    threads = [threading.Thread(target=create_jwt_sync, args=(r,)) for r in SUPPORTED_REGIONS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("[+] All tokens initialized successfully.")

def refresh_tokens_periodically():
    while True:
        time.sleep(25200)  # 7 hours
        print("[*] Refreshing tokens in background...")
        initialize_tokens_sync()

def get_token_info_sync(region: str) -> Tuple[str, str, str]:
    info = cached_tokens.get(region)
    if info and time.time() < info['expires_at']:
        return info['token'], info['region'], info['server_url']
    create_jwt_sync(region)
    info = cached_tokens[region]
    return info['token'], info['region'], info['server_url']

def GetAccountInformation_sync(uid, unk, region, endpoint):
    payload = json_to_proto_sync(json.dumps({'a': uid, 'b': unk}), main_pb2.GetPlayerPersonalShow())
    data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, payload)
    token, lock, server = get_token_info_sync(region)
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'Expect': "100-continue",
        'Authorization': token,
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': RELEASEVERSION
    }
    resp = _sync_client.post(server + endpoint, data=data_enc, headers=headers)
    return json.loads(json_format.MessageToJson(decode_protobuf(resp.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))

# === Caching Decorator ===

def cached_endpoint(ttl=300):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            key = request.path + "?" + request.query_string.decode()
            if key in cache:
                return cache[key]
            res = fn(*a, **k)
            cache[key] = res
            return res
        return wrapper
    return decorator

# === Flask Routes ===

@app.route('/')
def home():
    return HOME_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}

# Endpoint changed to /player-name
@app.route('/<region>/player-name')
@cached_endpoint()
def get_account_info(region):
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Please provide UID."}), 400

    region_upper = region.upper()
    if region_upper not in SUPPORTED_REGIONS:
        return jsonify({"error": f"Invalid Region. Supported regions: {', '.join(SUPPORTED_REGIONS)}"}), 400

    try:
        return_data = GetAccountInformation_sync(uid, "7", region_upper, "/GetPlayerPersonalShow")

        if not return_data or 'basicInfo' not in return_data:
            return jsonify({"error": "Player not found in this region."}), 404

        basic_info = return_data['basicInfo']
        filtered_data = {"nickname": basic_info.get("nickname")}

        formatted_json = json.dumps(filtered_data, indent=2, ensure_ascii=False)
        return formatted_json, 200, {'Content-Type': 'application/json; charset=utf-8'}

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve data for UID {uid} in {region_upper}.", "details": str(e)}), 500

@app.route('/refresh', methods=['GET', 'POST'])
def refresh_tokens_endpoint():
    try:
        initialize_tokens_sync()
        return jsonify({'message': 'Tokens refreshed for all regions.'}), 200
    except Exception as e:
        return jsonify({'error': f'Refresh failed: {e}'}), 500

# === Startup ===

if __name__ == '__main__':
    # Initialize tokens in parallel (no asyncio needed)
    initialize_tokens_sync()

    # Background thread for auto token refresh every 7 hours
    threading.Thread(target=refresh_tokens_periodically, daemon=True).start()

    # Run Flask App
    app.run(host='0.0.0.0', port=5000, debug=False)
