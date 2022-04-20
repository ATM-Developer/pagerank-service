import os
from shutil import copyfile
from Configs.eth.eth_config import PLEDGE_ABI
import requests
from utils.eth_util import Web3Eth
import hashlib
from utils.config_util import params

node_list_api = params['atmServer'] + '/server/serverList'
output_folder = 'validation_result'
cache_folder = 'validation_cache'


class GetResultHelper():
    def __init__(self, wallet_address, server_url, cache_folder):
        self.wallet_address = wallet_address
        self.server_url = server_url
        self.cache_folder = cache_folder

    def is_online(self):
        online_response = requests.get(self.server_url, timeout=10)
        if 200 == online_response.status_code:
            print('PR server {} is Online'.format(self.wallet_address))
            return True
        else:
            print('PR server {} is Offline'.format(self.wallet_address))
            return False

    def get_pr_result(self):
        pr_response = requests.get(self.server_url + '/api/getPRResult')
        if 200 == pr_response.status_code:
            self.pr_filename = os.path.join(self.cache_folder, self.wallet_address + '_pr.json')
            with open(self.pr_filename, 'wb') as f:
                f.write(pr_response.content)
        else:
            self.pr_filename = None
            print('No PR Result From: {}'.format(self.server_url))

    def get_individual_pr_result(self):
        individual_pr_response = requests.get(self.server_url + '/api/getIndividualPRResult')
        if 200 == individual_pr_response.status_code:
            self.individual_pr_filename = os.path.join(self.cache_folder, self.wallet_address + '_individual_pr.json')
            with open(self.individual_pr_filename, 'wb') as f:
                f.write(individual_pr_response.content)
        else:
            self.individual_pr_filename = None
            print('No Individual PR Result From: {}'.format(self.server_url))

    def get_weight_result(self):
        weight_response = requests.get(self.server_url + '/api/getContractWeight')
        if 200 == weight_response.status_code:
            self.weight_filename = os.path.join(
                self.cache_folder, self.wallet_address + '_weight.json')
            with open(self.weight_filename, 'wb') as f:
                f.write(weight_response.content)
        else:
            self.weight_filename = None
            print('No Weight Result From: {}'.format(self.server_url))

    def get_source_date(self):
        source_response = requests.get(self.server_url + '/api/getSourceData')
        if 200 == source_response.status_code:
            self.source_filename = os.path.join(
                self.cache_folder, self.wallet_address + '_input_data.pickle')
            with open(self.source_filename, 'wb') as f:
                f.write(source_response.content)
        else:
            self.source_filename = None
            print('No Source From: {}'.format(self.server_url))

    def get_digest(self):
        def get_md5(filename):
            with open(filename, "rb") as f:
                file_hash = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hash.update(chunk)
                return file_hash.hexdigest()

        if self.pr_filename is None or self.individual_pr_filename is None or self.weight_filename is None or self.source_filename is None:
            return None
        else:
            filenames = [self.pr_filename, self.individual_pr_filename, self.weight_filename, self.source_filename]
            digest = ''
            for filename in filenames:
                digest += get_md5(filename)
            return digest

    def run(self):
        if self.is_online():
            self.get_pr_result()
            self.get_individual_pr_result()
            self.get_weight_result()
            self.get_source_date()
            return self.get_digest()
        else:
            return None


def get_node_servers():
    try:
        # get node list with server endpoint
        response = requests.get(node_list_api)
        nodes = response.json()['data']['serverList']
        node_servers = {}
        for node in nodes:
            node_servers[node['walletAddress']] = node['serverUrl']
        return node_servers
    except:
        return None


def get_top11_nodes():
    try:
        # get wallet addresses of top 11 nodes
        w3 = Web3Eth().get_w3()
        contract_instance = w3.eth.contract(
            address=params.PLEDGE_ADDRESS, abi=PLEDGE_ABI)
        top11_nodes = contract_instance.functions.queryNodeRank(
            start=1, end=11).call()[0]
        return top11_nodes
    except:
        return None


def clear_data():
    if (not os.path.exists(cache_folder)):
        os.makedirs(cache_folder)
    for file in os.listdir(cache_folder):
        os.remove(os.path.join(cache_folder, file))

    if (not os.path.exists(output_folder)):
        os.makedirs(output_folder)
    for file in os.listdir(output_folder):
        os.remove(os.path.join(output_folder, file))


def finalize_result(wallet_address):
    source_data_filename = os.path.join(cache_folder, '{}_input_data.pickle'.format(wallet_address))
    source_pr_filename = os.path.join(cache_folder, '{}_pr.json'.format(wallet_address))
    source_individual_pr_filename = os.path.join(cache_folder, '{}_individual_pr.json'.format(wallet_address))
    source_weight_filename = os.path.join(cache_folder, '{}_weight.json'.format(wallet_address))

    copyfile(source_data_filename, os.path.join(output_folder, 'input_data.pickle'))
    copyfile(source_pr_filename, os.path.join(output_folder, 'pr.json'))
    copyfile(source_individual_pr_filename, os.path.join(output_folder, 'individual_pr.json'))
    copyfile(source_weight_filename, os.path.join(output_folder, 'weight.json'))


if __name__ == '__main__':
    node_servers = get_node_servers()
    top11_nodes = get_top11_nodes()
    if (node_servers is None or top11_nodes is None):
        print('Error happened while getting PR nodes information, please try later')
        exit(0)
    clear_data()
    pr_results = {}
    for node in top11_nodes:
        if (node not in node_servers):
            print('Could not find information for node {}, please try later.'.format(node))
            continue
        digest = None
        try:
            print('Starting to get results for node {}'.format(node))
            thread = GetResultHelper(node, node_servers[node], cache_folder)
            digest = thread.run()
            print('Result for node {} has been collected'.format(node))
        except:
            print('Error happened while trying collecting results for node {}, please try again.'.format(node))
            continue
        if digest is None:
            print('Can not handle: {}'.format(node))
            continue
        else:
            if (digest in pr_results):
                pr_results[digest].append(node)
            else:
                pr_results[digest] = [node]
            if (pr_results[digest].__len__() >= 6):
                finalize_result(pr_results[digest][0])
                print('Validation Successful! Please check it out in folder {}'.format(output_folder))
                exit(1)
    print('Validation failed! PR servers did not reach an agreement!')
