from flask import Flask, request, jsonify, Response
import requests
import jwt
import urllib3
import json
from collections import OrderedDict
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import ReqCLan_pb2
import QuitClanReq_pb2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

OB = "OB53"

API_INFO = {
    "developer": "M3L",
    "telegram": "not",
    "api_name": "FF GUILD JOIN/LEAVE API",
    "version": OB
}

# Crypto keys
KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

# Headers used for game requests
GAME_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/octet-stream",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": OB,
    "Expect": "100-continue"
}

# Region → Server URL mapping
REGION_SERVER_MAP = {
    "IND": "https://client.ind.freefiremobile.com",
    "ME":  "https://clientbp.ggblueshark.com",
    "VN":  "https://clientbp.ggpolarbear.com",
    "BD":  "https://clientbp.ggwhitehawk.com",
    "PK":  "https://clientbp.ggblueshark.com",
    "SG":  "https://clientbp.ggpolarbear.com",
    "BR":  "https://client.us.freefiremobile.com",
    "NA":  "https://client.us.freefiremobile.com",
    "ID":  "https://clientbp.ggpolarbear.com",
    "RU":  "https://clientbp.ggpolarbear.com",
    "TH":  "https://clientbp.ggpolarbear.com",
}
DEFAULT_SERVER_URL = "https://clientbp.ggblueshark.com"

# Helper: encrypt payload with AES-CBC
def encrypt_payload(data):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

# Helper: decode JWT without verifying signature
def decode_jwt(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        account_id = str(decoded.get("account_id"))
        nickname = decoded.get("nickname")
        lock_region = decoded.get("lock_region")
        return account_id, nickname, lock_region
    except Exception as e:
        print(f"JWT decode error: {e}")
        return None, None, None

# Helper: get server URL based on region
def get_server_url(region):
    return REGION_SERVER_MAP.get(region, DEFAULT_SERVER_URL)

# Get JWT directly from UID and password - UPDATED WITH DEBUGGING
def get_jwt_from_uid_pass(uid, password):
    url = f"https://anik-jwt-apis.vercel.app/token?uid={uid}&password={password}"
    print(f"Requesting JWT from: {url}")
    
    try:
        r = requests.get(url, timeout=10)
        print(f"Response status code: {r.status_code}")
        print(f"Response text: {r.text[:200]}")  # Print first 200 chars
        
        if r.status_code == 200:
            data = r.json()
            print(f"Parsed JSON: {data}")
            
            # Try different response formats
            jwt_token = None
            
            # Format 1: {"jwt": "token..."}
            if "jwt" in data:
                jwt_token = data["jwt"]
                print("Found JWT in 'jwt' field")
            
            # Format 2: {"token": "token..."}
            elif "token" in data:
                jwt_token = data["token"]
                print("Found JWT in 'token' field")
            
            # Format 3: {"data": {"jwt": "token..."}}
            elif "data" in data and "jwt" in data["data"]:
                jwt_token = data["data"]["jwt"]
                print("Found JWT in 'data.jwt' field")
            
            # Format 4: Direct string response
            elif isinstance(data, str):
                jwt_token = data
                print("Response is direct string, using as JWT")
            
            if jwt_token:
                account_id, nickname, region = decode_jwt(jwt_token)
                if account_id:
                    print(f"Success! UID: {account_id}, Name: {nickname}, Region: {region}")
                    return jwt_token, account_id, nickname, region
                else:
                    print("Failed to decode JWT even though we got one")
                    return None, None, None, None
            else:
                print("No JWT token found in response")
                return None, None, None, None
        else:
            print(f"HTTP Error: {r.status_code}")
            return None, None, None, None
            
    except requests.exceptions.Timeout:
        print("Request timeout")
        return None, None, None, None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw response: {r.text}")
        return None, None, None, None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, None, None, None

# Join clan request
def request_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = ReqCLan_pb2.MyMessage()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/RequestJoinClan"
    
    print(f"Join request URL: {url}")
    print(f"Clan ID: {clan_id}")
    print(f"Region: {region}")
    
    r = requests.post(url, headers=headers, data=payload, verify=False)
    print(f"Join response status: {r.status_code}")
    
    return r.status_code, r.text

# Quit clan request
def quit_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = QuitClanReq_pb2.QuitClanReq()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/QuitClan"
    
    print(f"Quit request URL: {url}")
    print(f"Clan ID: {clan_id}")
    print(f"Region: {region}")
    
    r = requests.post(url, headers=headers, data=payload, verify=False)
    print(f"Quit response status: {r.status_code}")
    
    return r.status_code, r.text

# ---------------------------
# Endpoints
# ---------------------------

@app.route("/")
def home():
    data = OrderedDict()
    data["success"] = True
    data["message"] = "Free Fire Clan API - UID & Password Only"
    data["endpoints"] = {
        "join_clan": "/join?clan_id=123&uid=123456&pass=your_password",
        "quit_clan": "/quit?clan_id=123&uid=123456&pass=your_password",
        "test_auth": "/test?uid=123456&pass=your_password"
    }
    data["example"] = {
        "join": "http://your-api.com/join?clan_id=12345&uid=123456789&pass=mypassword",
        "quit": "http://your-api.com/quit?clan_id=12345&uid=123456789&pass=mypassword"
    }
    data.update(API_INFO)
    return Response(json.dumps(data, indent=2), mimetype="application/json")

# Test authentication endpoint - to debug the JWT API
@app.route("/test")
def test_auth():
    uid = request.args.get("uid")
    password = request.args.get("pass")
    
    if not uid or not password:
        return jsonify({"success": False, "error": "uid and pass required"})
    
    jwt_token, uid_from_api, name, region = get_jwt_from_uid_pass(uid, password)
    
    if jwt_token:
        return jsonify({
            "success": True,
            "message": "Authentication successful",
            "uid": uid_from_api,
            "name": name,
            "region": region,
            "jwt_preview": jwt_token[:50] + "..." if len(jwt_token) > 50 else jwt_token
        })
    else:
        return jsonify({
            "success": False,
            "error": "Authentication failed - Invalid UID or Password",
            "note": "Make sure the UID and password are correct for Free Fire"
        })

# Join clan endpoint
@app.route("/join")
def api_join():
    clan_id = request.args.get("clan_id")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    
    # Validation
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    if not uid:
        return jsonify({"success": False, "error": "uid required"})
    if not password:
        return jsonify({"success": False, "error": "password required"})
    
    # Get JWT from UID & Password
    jwt_token, uid_from_api, name, region = get_jwt_from_uid_pass(uid, password)
    
    if not jwt_token:
        return jsonify({
            "success": False, 
            "error": "Invalid UID or Password. Could not get JWT token.",
            "help": "Use /test endpoint to verify your credentials"
        })
    
    # Send join request
    code, text = request_clan(jwt_token, clan_id, region)
    success = (code == 200)
    
    return jsonify({
        "success": success,
        "action": "Join Clan",
        "clan_id": clan_id,
        "uid": uid_from_api,
        "name": name,
        "region": region,
        "http_status": code,
        "developer": API_INFO["developer"],
        "telegram": API_INFO["telegram"],
        "api_version": API_INFO["version"],
        "server_response": text
    })

# Quit clan endpoint
@app.route("/quit")
def api_quit():
    clan_id = request.args.get("clan_id")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    
    # Validation
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    if not uid:
        return jsonify({"success": False, "error": "uid required"})
    if not password:
        return jsonify({"success": False, "error": "password required"})
    
    # Get JWT from UID & Password
    jwt_token, uid_from_api, name, region = get_jwt_from_uid_pass(uid, password)
    
    if not jwt_token:
        return jsonify({
            "success": False, 
            "error": "Invalid UID or Password. Could not get JWT token.",
            "help": "Use /test endpoint to verify your credentials"
        })
    
    # Send quit request
    code, text = quit_clan(jwt_token, clan_id, region)
    success = (code == 200)
    
    return jsonify({
        "success": success,
        "action": "Quit Clan",
        "clan_id": clan_id,
        "uid": uid_from_api,
        "name": name,
        "region": region,
        "http_status": code,
        "developer": API_INFO["developer"],
        "telegram": API_INFO["telegram"],
        "api_version": API_INFO["version"],
        "server_response": text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)