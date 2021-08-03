from reader import prepare_data
from network import directed_graph
import json
import pickle
import os

_checkpoint_dir = 'saved_checkpoint'
instance_name = 'network_instance.pkl'
default_network_instance_add = os.path.join(_checkpoint_dir,instance_name)

recent_transaction_hash_name = 'recent_transaction_hash.txt'
default_recent_transaction_hash_add = os.path.join(_checkpoint_dir,recent_transaction_hash_name)

def save_network(network_instance,add_=default_network_instance_add):
    # save the whole network
    with open(add_, 'wb') as directed_graph_instance:
        pickle.dump(network_instance, directed_graph_instance, pickle.HIGHEST_PROTOCOL)

def load_network(add=default_network_instance_add):
    # load the whole network
    with open(add, 'rb') as directed_graph_instance:
        g = pickle.load(directed_graph_instance)
    
    return g


if __name__ == '__main__':
    
    if not os.path.exists(_checkpoint_dir):
        os.mkdir(_checkpoint_dir)
        

    transactionHash_list,info_list = prepare_data()
    
    if transactionHash_list == []:

        print('no transaction record')
    else:

        with open(default_recent_transaction_hash_add,'r') as f:
            f = f.read()
        last_transaction_yesterday = f.strip()
        last_transaction_today = transactionHash_list[-1]
        

        recorded_index = -1
        for index,i in enumerate(transactionHash_list):
            if i==last_transaction_yesterday:
                recorded_index=index

        recorded = info_list[:recorded_index+1]
        if len(info_list)>recorded_index+1:
            unrecorded = info_list[recorded_index+1:]
        else:
            unrecorded = []
        
        if os.path.exists(default_network_instance_add):
            g = load_network(default_network_instance_add)
        else:
            g = directed_graph()
        
        for i in recorded:
            if i['isAward_']==False:
                # delete_contract()
            else:
                continue
        

        for transction_info in unrecorded:
            g.build_from_new_transction(transction_info)
        
        save_network(g,add_=default_network_instance_add)
        
        with open(default_recent_transaction_hash_add,'w') as f:
            f.write(last_transaction_today)
        
    add2pr,importance_dict = g.generate_api_info()

    _dir = 'output'
    if not os.path.exists(_dir):
        os.mkdir(_dir)
    with open(os.path.join(_dir,'pagerank_result.json'), 'w') as f:
        json.dump(add2pr, f)
    
    with open(os.path.join(_dir,'importance_result.json'), 'w') as f:
        json.dump(importance_dict, f)
    
    with open(os.path.join(_dir,'input_data.pickle'), 'wb') as f:
        pickle.dump(info_list,f)
        
    
