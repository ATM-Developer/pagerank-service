# ATM-PageRank-Node-Decentralized

## 1.Environments

Linux server, 2 cpu cores, 16Gb RAM, 5Mb/s public access network, 50Gb disk space.

python >= 3.8

    sudo yum install python38

pip >= 21.0.0

    sudo pip install --upgrade pip

gcc >= 4.8.5

    sudo yum install gcc

gunicorn >= 20.1.0

    sudo yum install gunicorn

Enter the root dir of project and run:

    sudo pip install -r requirements.txt

## 2.Modify configuration
Please use text editor to edit project/settings.cfg

3rd row: WALLET_ADDRESS, fill in the address of your Binance wallet. You must have some BNB in your wallet(Node needs to interact with smart contracts, it will cost you about 1 BNB a year)

4th row: WALLET_PRIVATE_KEY, fill in the private key of your Binance account

5th row: INFURA_URI, fill in the [Infura](https://infura.io/) Ethereum project mainnet https endpoint which you registered.

6th row: IPFS_SERVICE_TOKEN, fill in the [Web3.Storage](https://web3.storage/) API token which you registered. 

## 3.Run the service
Enter the root dir of project and run:

    sudo gunicorn -t 90 -w 2 -b 0.0.0.0:5000 manage:app -D

[-w 2]：set up this parameter (number of workers) based on the hardware configuration in your server. 

[-b 0.0.0.0:5000]：5000 is the port, you can choose different port as you want.

## 4.Register PR server 
You need to register the server at [ATM](https://www.atm.network/#/) official website.
