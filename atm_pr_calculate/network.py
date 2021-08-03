import numpy as np
import random
from tqdm import tqdm
import copy
import networkx as nx
import matplotlib.pyplot as plt
import math
import numpy as np



class directed_graph:
    
    def __init__(self):
        # directed_graph
        self.graph = nx.DiGraph()
        self.nodes = list(self.graph.nodes)
        self.edges = list(self.graph.edges)
        
        self.add2index = {}
        self.index2add = {}
    
        self.old_pr = {}
    
    def build_from_new_transction(self,info):
        # parse the info
        userA_ = info['userA_']
        userB_ = info['userB_']
        amountA_ = info['amountA_']
        amountB_ = info['amountB_']
        percentA_ = info['percentA_']
        totalPlan_ = info['totalPlan_']
        lockDays_ = info['lockDays_']
        startTime_ = info['startTime_']
        status_ = info['status_']
        link_contract = info['link_contract']
        isAward = info['isAward']
        

        if not isAward:
            return None
        # new add --> new index+1
        if userA_ not in self.add2index:
            if self.index2add == {}:
                index_A = 1
            else:
                index_A = max(self.index2add)+1
            # update add2index and index2add
            self.add2index[userA_] = index_A
            self.index2add[index_A] = userA_
        
        else:
            index_A = self.add2index[userA_]
            
        if userB_ not in self.add2index:
            index_B = max(self.index2add)+1
            # update add2index and index2add
            self.add2index[userB_] = index_B
            self.index2add[index_B] = userB_
        else:
            index_B = self.add2index[userB_]
            
        # add node into the network
        if index_A not in self.graph.nodes:
            self.graph.add_node(index_A)
        
        if index_B not in self.graph.nodes:
            self.graph.add_node(index_B)
            
        # add edge into the network
        edge_AB = (index_A,index_B)
        edge_BA = (index_B,index_A)
        
        if edge_AB not in self.graph.edges():
            self.graph.add_edge(edge_AB[0],edge_AB[1])
        else:
            print('edge({},{}) is already in the network.'.format(str(index_A),str(index_B)))
        
        if edge_BA not in self.graph.edges():
            self.graph.add_edge(edge_BA[0],edge_BA[1])
        else:
            print('edge({},{}) is already in the network.'.format(str(index_B),str(index_A)))
            

        # set weight to the edge in network -- status
        self.graph.edges[edge_AB]['status']=status_
        self.graph.edges[edge_BA]['status']=status_
        
        # set weight to the edge in network -- link_contract
        self.graph.edges[edge_AB]['link_contract']=link_contract
        self.graph.edges[edge_BA]['link_contract']=link_contract
        
        # set weight to the edge in network -- time_last
        self.graph.edges[edge_AB]['time_last']=1
        self.graph.edges[edge_BA]['time_last']=1
        
        # set weight to the edge in network -- money
        self.graph.edges[edge_AB]['money']=amountB_
        self.graph.edges[edge_BA]['money']=amountA_
        
        # set weight to the edge in network -- init_value
        # 1st turn, all_init_value = 0.5
        # pa = pb = 0.5
        if self.old_pr == {}:
            init_value_A = 0.5
            init_value_B = 0.5
    
        # 2 new users
        # pa = pb = _mean_old_pr
        elif index_A not in self.old_pr and index_B not in self.old_pr:
            _mean_old_pr = np.mean(list(self.old_pr.values()))
            init_value_A = _mean_old_pr
            init_value_B = _mean_old_pr
        
        # A in network, B is new
        # pa = old_pr[A]
        # pb = _mean_old_pr
        elif index_A in self.old_pr and index_B not in self.old_pr:
            _mean_old_pr = np.mean(list(self.old_pr.values()))
            init_value_A = self.old_pr[index_A]
            init_value_B = _mean_old_pr
            
        # B in network, A is new
        # pa = _mean_old_pr
        # pb = old_pr[B]
        elif index_A in self.old_pr and index_B not in self.old_pr:
            _mean_old_pr = np.mean(list(self.old_pr.values()))
            init_value_A = _mean_old_pr
            init_value_B = self.old_pr[index_B]
        
        # both A and B are in the network
        # pa = old_pr[A]
        # pb = old_pr[B]
        else:
            init_value_A = self.old_pr[index_A]
            init_value_B = self.old_pr[index_B]
        
        init_value_AB = init_value_B
        init_value_BA = init_value_A
        
        self.graph.edges[edge_AB]['init_value']=init_value_AB
        self.graph.edges[edge_BA]['init_value']=init_value_BA
        
        
        # set weight to the edge in network -- distance
        try:
            
            distance_len_AB = nx.shortest_path_length(self.graph,index_A,index_B)
            distance_len_BA = nx.shortest_path_length(self.graph,index_B,index_A)
            
            assert distance_len_AB==distance_len_BA,'path_len({}-->{}) != path_len({}-->{})'.format(str(index_A),str(index_B),str(index_B),str(index_A))
        
        except:
            # 1st step case
            if self.old_pr == {}:
                distance_len_AB = distance_len_BA = 1
            else:
                max_pr = max(self.old_pr.values())
                highest_pr_node = -1
                for node in self.old_pr:
                    if self.old_pr[node]==max_pr:
                        highest_pr_node = node

                if highest_pr_node<0:
                    raise Exception('Cannot find the highest_pr node.')
                    

                distance_dict = nx.single_source_shortest_path_length(self.graph,highest_pr_node)

                del distance_dict[highest_pr_node]

                if distance_dict == {}:
                    distance_len_AB = distance_len_BA = 1

                else:
                    distance_len_AB = distance_len_BA = min(np.mean(list(distance_dict.values())),21)
                
        self.graph.edges[edge_AB]['distance']=distance_len_AB
        self.graph.edges[edge_BA]['distance']=distance_len_BA
        
        # set weight to the edge in network -- importance
        # importance = money_strength * init_value * distance
        time_last_A = self.graph.edges[edge_AB]['time_last']
        time_last_B = self.graph.edges[edge_AB]['time_last']
        money_strength_AB = (amountA_**1.1)*math.log(time_last_B)
        money_strength_BA = (amountB_**1.1)*math.log(time_last_A)
        
        importance_AB = money_strength_AB * init_value_AB * distance_len_AB
        importance_BA = money_strength_BA * init_value_BA * distance_len_BA
        
        self.graph.edges[edge_AB]['importance']=importance_AB
        self.graph.edges[edge_BA]['importance']=importance_BA
    
    def calculate_importance(self,edge):
        # calculate importance for old existing edges after time_last+1
        time_last = self.graph.edges[edge]['time_last']
        money_strength = (self.graph.edges[edge]['money']**1.1)*math.log(time_last)
        init_value = self.graph.edges[edge]['init_value']
        distance = self.graph.edges[edge]['distance']
        
        importance = money_strength * init_value * distance
        # set weight to the edge in network -- importance
        self.graph.edges[edge]['importance']=importance
    
    def pagerank(self):

        pr_dict = nx.pagerank(self.graph, alpha=0.9,weight='importance',max_iter=1000)
        return pr_dict
        
    def everyday_time_last_effect(self):

        pass
    
    def everyday_check_isAward(self,info_list):
        pass
    
    def generate_api_info(self):
        
        # build up add2pr
        # format: user_add:user_pr
        index2pr = self.pagerank()
        add2pr = {}
        for i in index2pr:
            add = self.index2add[i]
            add2pr[add] = index2pr[i]
        
        # build up importance dict
        # format: link_contract:{A-->B:importance,B-->A:importance}
        importance_dict = {}
        for edge in self.graph.edges():
            A,B = edge
            add_A,add_B = self.index2add[A],self.index2add[B]
            edge_info = self.graph.edges[edge]
            link_contract = edge_info['link_contract']
            importance = edge_info['importance']
            
            if link_contract not in importance_dict:
                importance_dict[link_contract] = {}

            _link = add_A + '--->' + add_B
            importance_dict[link_contract][_link] = importance
            
        return add2pr,importance_dict
        
                       
