import requests
import json


# TODO 根据之前的job形式改写逻辑

# TODO 查询NFT项目列表并保存

# TODO 正式环境地址待定

def query_nft_list():
    url = "http://atmapi.5544444455.com/nft/projectList"
    response = requests.get(url)
    result = json.loads(response.text)
    nft_list = result['data']['nftProjectList']
    return nft_list


def query_nft_price(nft_address):
    # query slug
    url = "https://testnets-api.opensea.io/api/v1/asset_contract/{}"
    nft_response = requests.get(url.format(nft_address))
    nft_result = json.loads(nft_response.text)
    slug = nft_result['collection']['slug']
    # query price
    url = "https://testnets-api.opensea.io/api/v1/collection/{}/stats"
    headers = {"Accept": "application/json"}
    price_response = requests.get(url.format(slug), headers=headers)
    price_result = json.loads(price_response.text)
    # this is eth price
    eth_amount = price_result['stats']['floor_price']
    return eth_amount


def get_nft_info():
    nft_info = {}
    nft_list = query_nft_list()
    for nft_project in nft_list:
        symbol = nft_project['symbol']
        address = nft_project['address']
        # coefficient = nft_project['coefficient']  # TODO wait for update
        coefficient = 1
        price = query_nft_price(address)
        nft_info[address] = {'symbol': symbol, 'coefficient': coefficient, 'price': price}
    return nft_info


if __name__ == '__main__':
    info = get_nft_info()
    print(info)
