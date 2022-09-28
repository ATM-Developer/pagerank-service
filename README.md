# ATM-PageRank-Node-Decentralized

## 1.Environments

Server minimum configuration: 

    2 CPU cores
    16Gb RAM
    5Mb/s public access network
    50Gb disk space.

Installation process example under Ubuntu:

1.Update packages

    sudo apt update

2.Install python >= 3.8

    sudo apt install python3.8

3.Install pip >= 21.0.0

    sudo apt install python3-pip
    
4.Install gunicorn >= 20.1.0

    sudo apt install gunicorn
    
5.Enter the root directory of the project

    cd pagerank-service
    
6.Install requirements

    sudo pip install -r requirements.txt

## 2.Modify configuration
Please use text editor to edit project/settings.cfg

    sudo vim project/settings.cfg

3rd row: WALLET_ADDRESS, fill in the address of your BNB Smart Chain Mainnet account. You must have some BNB in your account(Node needs to interact with smart contracts, it will cost you about 1 BNB a year)


4th row: WALLET_PRIVATE_KEY, fill in the private key of your account


5th row: IPFS_SERVICE_TOKEN, fill in the [Web3.Storage](https://web3.storage/) API token which you registered. 

## 3.Run the service
Enter the root dir of project and run:

    sudo gunicorn -t 90 -b 0.0.0.0:5000 manage:app -D

[-b 0.0.0.0:5000]：5000 is the port, you can choose different port as you want.

## 4.Check the service
You can verify whether the service is running through the HTTP GET request

    curl --location --request GET 'http://your_domain:your_port/prod'

## 5.Register PR server 
You need to register the server at [ATM](https://www.atm.network/#/) official website.


## 6.Continue to follow our project and keep using the latest version of code
