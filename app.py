from datetime import datetime, timedelta
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS
import pytz
from web3 import Web3
from yaml import safe_load
from util import CalculateThread
import threading
from eth_account.messages import encode_defunct
from utils.eth_util import Web3Eth
from utils.secret_util import SignHTTP

app = Flask(__name__)
CORS(app)

# load parameters
params = {}
with open('Configs/config.yaml', 'r') as stream:
    params = safe_load(stream)
central_server_endpoint = params['centralServer']
output_folder = params['outputFolder']
cache_folder = params['cacheFolder']
wallet_address = params['wallet_address']
infura_url = params['infura_url'] + params['infura_product_id']
private_key = params['wallet_private_key']


def is_valid():
    w3 = Web3(Web3.HTTPProvider(infura_url))
    if (w3.isConnected()):
        print('Infural URL is valid.')
    else:
        print('Infural URL is invalid.')
        return False

    if (w3.isAddress(wallet_address)):
        print('Wallet address is valid.')
    else:
        print('Invalid wallet address: {}'.format(wallet_address))
        return False

    try:
        w3.eth.account.sign_message(
            encode_defunct(text='Hello World'),
            private_key=private_key
        )
        print('Private key is valid.')
        return True
    except:
        print('Invalid private key: {}'.format(private_key))
        return False


if (not is_valid()):
    print('The configuration is invalid, please update the configuration and try again.')
    exit(0)
else:
    print('The server is starting.')


def get_short_date():
    tz = pytz.timezone('Asia/Shanghai')
    bjTime = datetime.now(tz)
    if (bjTime >= datetime(bjTime.year, bjTime.month, bjTime.day, 22, 15, tzinfo=tz)):
        short_date = bjTime.strftime('%Y-%m-%d')
    else:
        short_date = (bjTime + timedelta(days=-1)).strftime('%Y-%m-%d')
    return short_date


# Requirement 2.3
@app.route("/api/startCalculate", methods=['POST'])
def start_calculate():
    data = request.get_json()
    # 验证签名
    is_valid = SignHTTP().verify_sign(data)
    if not is_valid:
        return jsonify(
            errorCode=400,
            errorMsg='BadRequest'
        ), 400
    message = data['message']
    # message 即 node_wallet_address，验证是不是此node且在top11里
    if message != wallet_address:
        return jsonify(
            errorCode=400,
            errorMsg='BadRequest'
        ), 400
    top11_infos = Web3Eth(infura_url).get_top11()
    if isinstance(top11_infos, list) and len(top11_infos) > 1:
        top11 = top11_infos[0]
    else:
        top11 = None
    if top11 is None or message not in top11:
        return jsonify(
            errorCode=400,
            errorMsg='StartVerifyError'
        ), 400
    for i in threading.enumerate():
        # 若线程已启动了则不再重复启动
        if i.name == 'thread-1' and i.is_alive():
            return jsonify(
                errorCode=400,
                errorMsg='CalculateStarted'
            ), 400

    new_thread = CalculateThread(
        1, 'thread-1', 1,
        central_server_endpoint=central_server_endpoint,
        wallet_address=wallet_address,
        infura_url=infura_url,
        cache_folder=cache_folder,
        output_folder=output_folder)
    new_thread.start()
    return jsonify(
        errorCode=0,
        errorMsg='OK',
        data={
            "ackowledged": True
        }
    ), 200


# Requirement 2.4
@app.route("/api/getSourceData")
def get_source_data():
    short_date = get_short_date()
    try:
        return send_from_directory(output_folder, 'input_data_' + short_date + '.pickle'), 200
    except FileNotFoundError:
        abort(404)


# Requirement 2.5
@app.route("/api/getPRResult")
def get_pr_rank():
    short_date = get_short_date()
    try:
        return send_from_directory(output_folder, 'pagerank_result_' + short_date + '.json'), 200
    except FileNotFoundError:
        abort(404)


# Requirement 2.6
@app.route("/api/getContractWeight")
def get_contract_weight():
    short_date = get_short_date()
    try:
        return send_from_directory(output_folder, 'importance_result_' + short_date + '.json'), 200
    except FileNotFoundError:
        abort(404)


# Requirement 2.7
@app.route("/")
def hello_world():
    return jsonify(
        errorCode=0,
        errorMsg='OK'
    ), 200


# Requirement 2.8
@app.route("/api/signMessage", methods=['POST'])
def sign_message():
    data = request.get_json()
    # 验证签名
    is_valid = SignHTTP().verify_sign(data)
    if not is_valid:
        return jsonify(
            errorCode=400,
            errorMsg='BadRequest'
        ), 400
    if (data is None) or (data['message'] is None):
        return jsonify(
            errorCode=400,
            errorMsg='BadRequest'
        ), 400
    message = data['message']
    w3 = Web3(infura_url)
    msg = encode_defunct(text=message)
    signed_message = w3.eth.account.sign_message(msg, private_key)
    signed_str = signed_message.signature.hex()
    return jsonify(
        errorCode=0,
        errorMsg='OK',
        signed_str=signed_str
    ), 200


# Requirement 2.9.1
@app.route("/api/getCache1")
def get_cache1():
    short_date = get_short_date()
    try:
        return send_from_directory(output_folder, 'last_day_edge_multi_contract_' + short_date + '.pickle'), 200
    except FileNotFoundError as err:
        abort(404)


# Requirement 2.9.2
@app.route("/api/getCache2")
def get_cache2():
    try:
        return send_from_directory(cache_folder, 'recent_transaction_hash.txt'), 200
    except FileNotFoundError:
        abort(404)
