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

8.install nodejs\npm

node.js version 18 or higher and npm version 7 or higher is required. Check your local versions like this: node --version && npm --version. Install nodejs by referring to [NODESOURCE](https://deb.nodesource.com/) and [distributions](https://deb.nodesource.com/). npm will be installed synchronously.

    sudo apt-get install -y ca-certificates curl gnupg
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    NODE_MAJOR=20
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
    sudo apt-get update
    sudo apt list nodejs -a
    sudo apt-get install nodejs -y

9.install and configure web3-storage

Reference website [Web3.Storage](https://web3.storage/docs/quickstart/).

    install: sudo npm install -g @web3-storage/w3cli

    authorization: w3 login {email}
    list spaces: w3 space ls # if there is no space, use command 'w3 space create' to create
    select space: w3 space use {space_id}

## 2.Create your account

Generate your account according to the script we provide(pagerank-service/generate_address.py), remember the key file path, your address and your password.

    python generate_address.py

You must transfer some BNB to your account. PR Node needs to interact with smart contracts, it will cost you about 1 BNB a year.

## 3.Modify configuration
Please use text editor to edit project/settings.cfg

    sudo vim project/settings.cfg

3rd row: PRIVATE_PATH, fill in the path of the key file

## 4.Run the service
Enter the root dir of project and run:

    export ATMPD="your password"
    gunicorn -w 4 -t 90 -b 0.0.0.0:5000 manage:app -D

[-b 0.0.0.0:5000]：5000 is the port, you can choose different port as you want.

## 5.Check the service
You can verify whether the service is running through the HTTP GET request

    curl --location --request GET 'http://your_domain:your_port/prod'

## 6.Register PR server 
You need to register the server at [ATM](https://www.atm.network/#/) official website.


## 7.Continue to follow our project and keep using the latest version of code