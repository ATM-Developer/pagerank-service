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

2.Install python >= 3.10

    sudo apt install python3.10

3.Install pip >= 21.0.0

    sudo apt install python3-pip

4.Install gunicorn >= 20.1.0

    sudo apt install gunicorn

5.Enter the root directory of the project

    cd pagerank-service

6.Install requirements

    sudo pip install -r requirements.txt

7.set password

    export ATMPD="your password"

## 2.Create your account

Generate your account according to the script we provide(pagerank-service/generate_address.py), remember the key file path, your address and your password.

    python generate_address.py

You must transfer some BNB to your account. PR Node needs to interact with smart contracts, it will cost you about 1 BNB a year.

## 3.Modify configuration
Please use text editor to edit project/settings.cfg

    sudo vim project/settings.cfg

3rd row: PRIVATE_PATH, fill in the path of the key file

4th row: IPFS_SERVICE_TOKEN, fill in the [Web3.Storage](https://web3.storage/) API token which you registered. 

## 4.Run the service
Enter the root dir of project and run:

    export ATMPD="your password"
    sudo gunicorn -w 4 -t 90 -b 0.0.0.0:5000 manage:app -D

[-b 0.0.0.0:5000]：5000 is the port, you can choose different port as you want.

## 5.Check the service
You can verify whether the service is running through the HTTP GET request

    curl --location --request GET 'http://your_domain:your_port/prod'

## 6.Register PR server 
You need to register the server at [ATM](https://www.atm.network/#/) official website.


## 7.Continue to follow our project and keep using the latest version of code