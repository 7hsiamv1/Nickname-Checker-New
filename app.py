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
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-main: #0B0F19;
    --card-bg: rgba(17, 24, 39, 0.7);
    --border-color: rgba(255, 255, 255, 0.1);
    --accent: #00E5FF;
    --accent-hover: #00B3CC;
    --text-main: #F9FAFB;
    --text-muted: #9CA3AF;
    --success-bg: rgba(16, 185, 129, 0.1);
    --success-text: #10B981;
    --error-bg: rgba(239, 68, 68, 0.1);
    --error-text: #EF4444;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: var(--bg-main);
    background-image: 
      radial-gradient(at 0% 0%, rgba(0, 229, 255, 0.1) 0px, transparent 50%),
      radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.1) 0px, transparent 50%);
    background-attachment: fixed;
    color: var(--text-main);
    font-family: 'Poppins', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    overflow-x: hidden;
  }

  .container {
    width: 100%;
    max-width: 540px;
    position: relative;
    z-index: 1;
    animation: fadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  @keyframes fadeIn {
    0% { opacity: 0; transform: translateY(20px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  .header {
    text-align: center;
    margin-bottom: 35px;
  }

  .logo-wrapper {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(0, 229, 255, 0.05));
    border: 1px solid rgba(0, 229, 255, 0.3);
    margin-bottom: 16px;
    box-shadow: 0 8px 32px rgba(0, 229, 255, 0.15);
  }

  .logo-wrapper svg {
    width: 28px;
    height: 28px;
    color: var(--accent);
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.05); opacity: 0.8; }
    100% { transform: scale(1); opacity: 1; }
  }

  h1 {
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
    background: linear-gradient(to right, #FFFFFF, var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .subtitle {
    font-size: 14px;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
  }

  .card {
    background: var(--card-bg);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    padding: 32px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    margin-bottom: 24px;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }

  .field-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 10px;
    display: block;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .input-group {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
  }

  .input-control {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-main);
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    padding: 14px 18px;
    border-radius: 12px;
    outline: none;
    transition: all 0.2s ease;
  }

  .uid-input {
    flex: 1;
    width: 100%;
  }

  .region-select {
    width: 110px;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239CA3AF'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    background-size: 16px;
    padding-right: 36px;
  }

  .region-select option { background: var(--bg-main); }

  .input-control:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(0, 229, 255, 0.15);
  }

  .input-control::placeholder { color: rgba(156, 163, 175, 0.5); }

  .btn {
    width: 100%;
    padding: 16px;
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 12px;
    font-family: 'Poppins', sans-serif;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .btn:hover:not(:disabled) {
    background: var(--accent-hover);
    transform: translateY(-2px);
    box-shadow: 0 10px 20px rgba(0, 229, 255, 0.2);
  }

  .btn:active:not(:disabled) { transform: translateY(0); }

  .btn:disabled {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-muted);
    cursor: not-allowed;
  }

  .result-box {
    margin-top: 24px;
    padding: 20px;
    border-radius: 12px;
    display: none;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.4s ease;
  }

  .result-box.visible {
    display: block;
    opacity: 1;
    transform: translateY(0);
  }

  .result-box.success {
    background: var(--success-bg);
    border: 1px solid rgba(16, 185, 129, 0.2);
  }

  .result-box.error {
    background: var(--error-bg);
    border: 1px solid rgba(239, 68, 68, 0.2);
  }

  .result-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    color: var(--text-muted);
  }

  .result-nickname {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-main);
    word-break: break-all;
    line-height: 1.2;
    margin-bottom: 4px;
  }

  .result-box.success .result-nickname { color: var(--accent); }

  .result-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
  }

  .error-text {
    font-size: 15px;
    color: var(--error-text);
  }

  .tutorial {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
  }

  .tutorial-header {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .tutorial-header::before {
    content: '';
    display: inline-block;
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
  }

  .code-block {
    background: #0B0F19;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .code-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
    word-break: break-all;
    padding-right: 20px;
  }

  .code-text span { color: var(--accent); }

  .copy-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-main);
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .copy-btn:hover {
    background: rgba(0, 229, 255, 0.1);
    color: var(--accent);
    border-color: rgba(0, 229, 255, 0.3);
  }

  .footer {
    margin-top: 30px;
    text-align: center;
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    background: var(--success-text);
    border-radius: 50%;
    box-shadow: 0 0 10px var(--success-text);
    animation: blink 2s infinite;
  }

  .dev-credit {
    font-weight: 600;
    letter-spacing: 0.5px;
    color: rgba(255, 255, 255, 0.6);
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(0, 0, 0, 0.2);
    border-top-color: #000;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { 100% { transform: rotate(360deg); } }

  @media (max-width: 480px) {
    .card { padding: 24px; }
    .input-group { flex-direction: column; }
    .region-select { width: 100%; }
    h1 { font-size: 28px; }
  }
</style>
</head>
<body>

<div class="container">
  <div class="header">
    <div class="logo-wrapper">
      <svg fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <h1>Nickname Checker</h1>
    <p class="subtitle">API Lookup System &bull; Fast & Secure</p>
  </div>

  <div class="card">
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
      <span id="btnText">Check Nickname</span>
    </button>

    <div class="result-box" id="resultBox">
      <div class="result-label" id="resultLabel">Result</div>
      <div class="result-nickname" id="resultNickname"></div>
      <div class="result-meta" id="resultMeta"></div>
    </div>
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

  <div class="footer">
    <div class="status">
      <span class="status-dot"></span>
      API is Online & Active
    </div>
    <div class="dev-credit">DEVELOPED BY 7H SIAM</div>
  </div>
</div>

<script>
  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      btn.style.color = 'var(--accent)';
      btn.style.borderColor = 'var(--accent)';
      setTimeout(() => { 
        btn.textContent = orig; 
        btn.style.color = ''; 
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
      // Updated Endpoint to /player-name as requested
      const res  = await fetch(`/${region}/player-name?uid=${encodeURIComponent(uid)}`);
      const data = await res.json();

      if (!res.ok || data.error) {
        showError(data.error || 'Player not found.');
      } else {
        setTimeout(() => {
          resultBox.classList.add('visible', 'success');
          resultLabel.textContent = 'Player Found';
          resultNick.textContent = data.nickname || '—';
          resultMeta.textContent = `UID: ${uid} • Region: ${region}`;
        }, 100); 
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
      resultLabel.textContent = 'Error';
      resultNick.innerHTML = `<span class="error-text">${msg}</span>`;
      resultMeta.textContent = '';
    }, 100);
  }

  function setLoading(state) {
    checkBtn.disabled = state;
    if(state) {
        checkBtn.innerHTML = '<div class="spinner"></div><span id="btnText">Fetching Data...</span>';
    } else {
        checkBtn.innerHTML = '<span id="btnText">Check Nickname</span>';
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