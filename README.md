# ATM-PageRank-Node

So far the PageRank server is only responsible for calculating PageRank scores. The centre server will validate the result of RageRank calculation and issuanceof reward.

We will keep improving PageRank server and achieve decentralized PageRank server cluster.

## 1.Environments
python >= 3.6

pip >= 21.0.0

gcc >= 4.8.5

Enter the root dir of project and run:

    pip install -r requirements.txt

## 2.Modify configuration
Please use text editor to edit Configs/config.yaml

22th row: wallet_address, fill in the address of your ethereum wallet

23th row: wallet_private_key, fill in the private key of your ethereum account

## 3.Run the service
Enter the root dir of project and run:

    gunicorn -w 2 -b 0.0.0.0:5000 app:app -D

[-w 2]：set up this parameter (number of workers) based on the hardware configuration in your server. 

[-b 0.0.0.0:5000]：5000 is the port, you can choose different port as you want.

## 4.Register PR server 
You need to register the server at ATM official website.

## 5.Validate today's calculation result of PageRank score
If your server isn't chosen to calculate the PageRank score, you can use the program we provided to validate the result.

The validating program can get the calculation result of the chosen 11 pageRank servers and validate the calculated PageRank score.

The validating program is located at the root dir of project, you need to run:

    python validation_script.py

If the validation fails, we will see the details at the console. 

If the validation succeeds, the validation result will be saved at the validation_result dir at the root dir of project.

