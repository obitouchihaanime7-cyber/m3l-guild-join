from flask import Flask, request, jsonify, Response
import requests
import jwt
import urllib3
import json
from collections import OrderedDict
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import protobuf files
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

def encrypt_payload(data):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def decode_jwt(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        account_id = str(decoded.get("account_id"))
        nickname = decoded.get("nickname")
        lock_region = decoded.get("lock_region")
        return account_id, nickname, lock_region
    except Exception:
        return None, None, None

def get_server_url(region):
    return REGION_SERVER_MAP.get(region, DEFAULT_SERVER_URL)

def get_jwt_from_uid_pass(uid, password):
    url = f"https://anik-jwt-apis.vercel.app/token?uid={uid}&password={password}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            jwt_token = data.get("jwt") or data.get("token")
            if jwt_token:
                account_id, nickname, region = decode_jwt(jwt_token)
                if account_id:
                    return jwt_token, account_id, nickname, region
        return None, None, None, None
    except Exception:
        return None, None, None, None

def request_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = ReqCLan_pb2.MyMessage()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/RequestJoinClan"
    r = requests.post(url, headers=headers, data=payload, verify=False)
    return r.status_code, r.text

def quit_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = QuitClanReq_pb2.QuitClanReq()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/QuitClan"
    r = requests.post(url, headers=headers, data=payload, verify=False)
    return r.status_code, r.text

# Routes
@app.route("/")
def home():
    data = OrderedDict()
    data["success"] = True
    data["message"] = "Free Fire Clan API - Vercel Hosted"
    data["endpoints"] = {
        "join_clan": "/join?clan_id=123&uid=123456&pass=your_password",
        "quit_clan": "/quit?clan_id=123&uid=123456&pass=your_password",
        "test_auth": "/test?uid=123456&pass=your_password"
    }
    data.update(API_INFO)
    return Response(json.dumps(data, indent=2), mimetype="application/json")

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
            "uid": uid_from_api,
            "name": name,
            "region": region
        })
    else:
        return jsonify({
            "success": False,
            "error": "Invalid UID or Password"
        })

@app.route("/join")
def api_join():
    clan_id = request.args.get("clan_id")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    if not uid:
        return jsonify({"success": False, "error": "uid required"})
    if not password:
        return jsonify({"success": False, "error": "password required"})
    
    jwt_token, uid_from_api, name, region = get_jwt_from_uid_pass(uid, password)
    
    if not jwt_token:
        return jsonify({
            "success": False, 
            "error": "Invalid UID or Password"
        })
    
    code, text = request_clan(jwt_token, clan_id, region)
    success = (code == 200)
    
    return jsonify({
        "success": success,
        "action": "Join Clan",
        "clan_id": clan_id,
        "uid": uid_from_api,
        "name": name,
        "region": region,
        "developer": API_INFO["developer"],
        "api_version": API_INFO["version"],
        "server_response": text
    })

@app.route("/quit")
def api_quit():
    clan_id = request.args.get("clan_id")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    if not uid:
        return jsonify({"success": False, "error": "uid required"})
    if not password:
        return jsonify({"success": False, "error": "password required"})
    
    jwt_token, uid_from_api, name, region = get_jwt_from_uid_pass(uid, password)
    
    if not jwt_token:
        return jsonify({
            "success": False, 
            "error": "Invalid UID or Password"
        })
    
    code, text = quit_clan(jwt_token, clan_id, region)
    success = (code == 200)
    
    return jsonify({
        "success": success,
        "action": "Quit Clan",
        "clan_id": clan_id,
        "uid": uid_from_api,
        "name": name,
        "region": region,
        "developer": API_INFO["developer"],
        "api_version": API_INFO["version"],
        "server_response": text
    })

# Vercel handler
app = app

if __name__ == "__main__":
    app.run()
