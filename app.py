import logging
import traceback
import threading
from web3 import Web3
from yaml import safe_load
from flask_cors import CORS
from flask import Flask, abort, jsonify, request, send_from_directory

from utils.log_util import *
from util import CalculateThread
from eth_account.messages import encode_defunct
from utils.eth_util import Web3Eth
from utils.secret_util import SignHTTP
from utils.date_util import get_pagerank_date

app = Flask(__name__)
CORS(app)
logger = logging.getLogger('main')

# load parameters
params = {}
with open('Configs/config.yaml', 'r') as stream:
    params = safe_load(stream)
central_server_endpoint = params['centralServer']
output_folder = params['outputFolder']
cache_folder = params['cacheFolder']
wallet_address = params['wallet_address']
infura_url = params['infura_url'] + params['infura_project_id']
private_key = params['wallet_private_key']
port = params['node_port']


def is_valid():
    w3 = Web3(Web3.HTTPProvider(infura_url))
    if (w3.isConnected()):
        print('Infural URL is valid.')
        logger.info('Infural URL is valid.')
    else:
        print('Infural URL is invalid.')
        logger.info('Infural URL is invalid.')
        return False

    if (w3.isAddress(wallet_address)):
        print('Wallet address is valid.')
        logger.info('Wallet address is valid.')
    else:
        print('Invalid wallet address: {}'.format(wallet_address))
        logger.info('Invalid wallet address: {}'.format(wallet_address))
        return False

    try:
        w3.eth.account.sign_message(
            encode_defunct(text='Hello World'),
            private_key=private_key
        )
        print('Private key is valid.')
        logger.info('Private key is valid.')
        return True
    except:
        logger.error(traceback.format_exc())
        print('Invalid private key: {}'.format(private_key))
        return False


if (not is_valid()):
    print('The configuration is invalid, please update the configuration and try again.')
    logger.info('The configuration is invalid, please update the configuration and try again.')
    exit(0)
else:
    print('The server is starting.')
    logger.info('The server is starting.')


@app.route("/api/startCalculate", methods=['POST'])
def start_calculate():
    try:
        data = request.get_json()
        logger.info('api start calculate data: {}'.format(data))
        # 验证签名
        is_valid = SignHTTP().verify_sign(data)
        if not is_valid:
            logger.info('invalid sign')
            return jsonify(
                errorCode=400,
                errorMsg='BadRequest'
            ), 400
        message = data['message']
        # validate wallet address
        if message != wallet_address.lower():
            logger.info('not this wallet address: {}'.format(wallet_address.lower()))
            return jsonify(
                errorCode=400,
                errorMsg='BadRequest'
            ), 400
        top11_infos = Web3Eth(infura_url).get_top11()
        if isinstance(top11_infos, list) and len(top11_infos) > 1:
            top11 = top11_infos[0]
            top11 = [i.lower() for i in top11]
        else:
            top11 = None
        if top11 is None or message not in top11:
            logger.info('message address not in top11. top11: {}'.format(top11))
            return jsonify(
                errorCode=400,
                errorMsg='StartVerifyError'
            ), 400
        for i in threading.enumerate():
            # check wether thread is running or not
            if i.name == 'pagerank-calculation-thread' and i.is_alive():
                logger.info('haved this calculate thread.')
                return jsonify(
                    errorCode=400,
                    errorMsg='CalculateStarted'
                ), 400

        new_thread = CalculateThread(
            1, 'pagerank-calculation-thread', 1,
            central_server_endpoint=central_server_endpoint,
            wallet_address=wallet_address,
            infura_url=infura_url,
            cache_folder=cache_folder,
            output_folder=output_folder)
        new_thread.start()
        logger.info('calculate thread start.')
        return jsonify(
            errorCode=0,
            errorMsg='OK',
            data={
                "ackowledged": True
            }
        ), 200
    except:
        logger.error(traceback.format_exc())
        return jsonify(
            errorCode=500,
            errorMsg='error'
        ), 500


@app.route("/api/getSourceData")
def get_source_data():
    short_date = get_pagerank_date()
    logger.info('api get source data date: {}'.format(short_date))
    try:
        return send_from_directory(output_folder, 'input_data_' + short_date + '.pickle'), 200
    except FileNotFoundError:
        logger.error(traceback.format_exc())
        abort(404)


@app.route("/api/getPRResult")
def get_pr_rank():
    short_date = get_pagerank_date()
    logger.info('api get pr result data date: {}'.format(short_date))
    try:
        return send_from_directory(output_folder, 'pagerank_result_' + short_date + '.json'), 200
    except FileNotFoundError:
        logger.error(traceback.format_exc())
        abort(404)


@app.route("/api/getContractWeight")
def get_contract_weight():
    short_date = get_pagerank_date()
    logger.info('api get contract weight data date: {}'.format(short_date))
    try:
        return send_from_directory(output_folder, 'importance_result_' + short_date + '.json'), 200
    except FileNotFoundError:
        logger.error(traceback.format_exc())
        abort(404)


@app.route("/")
def hello_world():
    return jsonify(
        errorCode=0,
        errorMsg='OK'
    ), 200


@app.route("/api/signMessage", methods=['POST'])
def sign_message():
    try:
        data = request.get_json()
        logger.info('api sign message data: {}'.format(data))
        # 验证签名
        is_valid = SignHTTP().verify_sign(data)
        if not is_valid:
            logger.info('invalid sign')
            return jsonify(
                errorCode=400,
                errorMsg='BadRequest'
            ), 400
        if (data is None) or (data['message'] is None):
            logger.info('invalid param')
            return jsonify(
                errorCode=400,
                errorMsg='BadRequest'
            ), 400
        message = data['message']
        w3 = Web3(infura_url)
        msg = encode_defunct(text=message)
        signed_message = w3.eth.account.sign_message(msg, private_key)
        signed_str = signed_message.signature.hex()
        logger.info('message address: {}, signed str: {}'.format(message, signed_str))
        return jsonify(
            errorCode=0,
            errorMsg='OK',
            signed_str=signed_str
        ), 200
    except:
        logger.error(traceback.format_exc())
        return jsonify(
            errorCode=500,
            errorMsg='error'
        ), 500


@app.route("/api/getCache1")
def get_cache1():
    short_date = get_pagerank_date()
    logger.info('api get cache1 data date: {}'.format(short_date))
    try:
        return send_from_directory(output_folder, 'last_day_edge_multi_contract_' + short_date + '.pickle'), 200
    except FileNotFoundError as err:
        logger.error(traceback.format_exc())
        abort(404)


@app.route("/api/getCache2")
def get_cache2():
    try:
        logger.info('api get cache2 data:')
        return send_from_directory(cache_folder, 'recent_transaction_hash.txt'), 200
    except FileNotFoundError:
        logger.error(traceback.format_exc())
        abort(404)


if __name__ == "__main__":
    print('>>>>> Starting PageRank Node Server <<<<<')
    app.run(host='0.0.0.0', port=port, threaded=True)
    print('Done')
