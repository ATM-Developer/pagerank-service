import networkx as nx
import math
import numpy as np
import pickle


class directed_graph:

    def __init__(self):
        # directed_graph
        self.graph = nx.DiGraph()
        self.nodes = list(self.graph.nodes)
        self.edges = list(self.graph.edges)

        self.add2index = {}
        self.index2add = {}

        # 以天为单位更新old_pr?
        self.old_pr = {}

        # 收集同一edge的多个contract信息
        # 需要记录每个contract的子edge的weight，便于之后汇总
        # 每个先更新这个dict，最后再构建network
        self.edge_multi_contract = {}

    def build_from_new_transction(self, info):
        # parse the unrecorded_info_list
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
        isAward_ = info['isAward_']

        # isAward==False,则此合约失效
        if not isAward_:
            return None
        # new add --> new index+1
        if userA_ not in self.add2index:
            # network的第一个点
            if self.index2add == {}:
                index_A = 1
            else:
                index_A = max(self.index2add) + 1
            # update add2index and index2add
            self.add2index[userA_] = index_A
            self.index2add[index_A] = userA_

        else:
            index_A = self.add2index[userA_]

        if userB_ not in self.add2index:
            index_B = max(self.index2add) + 1
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
        edge_AB = (index_A, index_B)
        edge_BA = (index_B, index_A)

        if edge_AB not in self.edge_multi_contract:
            self.edge_multi_contract[edge_AB] = {}

        if edge_BA not in self.edge_multi_contract:
            self.edge_multi_contract[edge_BA] = {}
            '''
            未完待续
            先全部把dict建立完成，最后计算pr的时候不管是用nx还是igraph，就是个内置函数。
            用dict存储所有edge的信息，weight，天数等等
            
            format:
            self.edge_multi_contract = {
                                        edge_AB:{contract_1:{}
                                                 contract_2:{}
                                                 contract_3:{}
                                        }
                                        edge_BA:{.....}
                                        
                                        }
            
            之后再汇集成单个edge，建立network，求pagerank
            
            
            '''

        contract_AB_info = {}
        contract_BA_info = {}

        # 辅助信息setup：status，link_contract

        # set weight to the edge in network -- status
        contract_AB_info['status'] = status_
        contract_BA_info['status'] = status_

        # set weight to the edge in network -- link_contract
        contract_AB_info['link_contract'] = link_contract
        contract_BA_info['link_contract'] = link_contract

        # set weight to the edge in network -- time_last
        contract_AB_info['time_last'] = 1
        contract_BA_info['time_last'] = 1

        # set weight to the edge in network -- money
        contract_AB_info['money'] = amountB_
        contract_BA_info['money'] = amountA_

        # set weight to the edge in network -- init_value
        # 1st turn, all_init_value = 0.5
        # pa = pb = 0.5
        if self.old_pr == {}:
            init_value_A = 0.5
            init_value_B = 0.5

        # 引入”新点“：
        # 如何判断node是new还是old呢，如果一个node之前有过合约，加入过网络后来取消合约了，它没有edge了，就不该算他在network内部了吧
        # 为了方便标记，node一旦加入network就不会被取消index，即便它退出了，所以应该认为node没有edge了，就算是新的了。
        # 既：在old_pr中没有node，就算是新的

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

        contract_AB_info['init_value'] = init_value_AB
        contract_BA_info['init_value'] = init_value_BA

        # set weight to the edge in network -- distance
        try:
            # 存在path
            # directed_graph求distance需要2个方向都求
            distance_len_AB = nx.shortest_path_length(self.graph, index_A, index_B)
            distance_len_BA = nx.shortest_path_length(self.graph, index_B, index_A)
            # double check,因为此网络所有edge均为双向，所以应该相等
            assert distance_len_AB == distance_len_BA, 'path_len({}-->{}) != path_len({}-->{})'.format(str(index_A),
                                                                                                       str(index_B),
                                                                                                       str(index_B),
                                                                                                       str(index_A))

        except:
            # 不存在path
            # 用目前PR值最高的点到网络内其他点的平均距离的3倍，但最大值不超过21,作为replace

            # 1st step case
            if self.old_pr == {}:
                distance_len_AB = distance_len_BA = 1
            else:
                max_pr = max(self.old_pr.values())
                highest_pr_node = -1
                for node in self.old_pr:
                    if self.old_pr[node] == max_pr:
                        highest_pr_node = node

                if highest_pr_node < 0:
                    raise Exception('Cannot find the highest_pr node.')

                # pr最高点到其他点的mean最短距离
                # 因为此网络结构为双向，所以不需要重复计算 inner_len 和 outter_len
                distance_dict = nx.single_source_shortest_path_length(self.graph, highest_pr_node)
                # nx.single_source_shortest_path_length会重复计算自己到自己的距离，所以删除
                del distance_dict[highest_pr_node]
                # 该网络无edge
                if distance_dict == {}:
                    distance_len_AB = distance_len_BA = 1
                # 该网络正常,distance不超过21
                else:
                    distance_len_AB = distance_len_BA = min(np.mean(list(distance_dict.values())), 21)

        contract_AB_info['distance'] = distance_len_AB
        contract_BA_info['distance'] = distance_len_BA

        # set weight to the edge in network -- importance
        # importance = money_strength * init_value * distance
        time_last_A = contract_AB_info['time_last']
        time_last_B = contract_BA_info['time_last']
        money_strength_AB = (amountB_ ** 1.1) * math.log(time_last_B + 1)
        money_strength_BA = (amountA_ ** 1.1) * math.log(time_last_A + 1)

        importance_AB = money_strength_AB * init_value_AB * distance_len_AB
        importance_BA = money_strength_BA * init_value_BA * distance_len_BA

        contract_AB_info['money_strength'] = money_strength_AB
        contract_BA_info['money_strength'] = money_strength_BA

        contract_AB_info['importance'] = importance_AB
        contract_BA_info['importance'] = importance_BA

        # build up contract_AB_info and contract_AB_info successfully
        # add contract_AB_info and contract_AB_info into the edge_multi_contract dict
        # contractBA_key为用于识别2个user的多个contract的key_identification
        # link_contract 地址应该是unique的
        contractAB_key = contract_AB_info['link_contract']
        contractBA_key = contract_BA_info['link_contract']
        self.edge_multi_contract[edge_AB][contractAB_key] = contract_AB_info
        self.edge_multi_contract[edge_BA][contractBA_key] = contract_BA_info

        # 是否需要加入新变量：录入的天数，既第几天被录入，之后便于安全的复现whole network？

    def calculate_importance(self, edge, link_contract):
        # calculate importance for old existing edges as time_last+1
        contract_info = self.edge_multi_contract[edge][link_contract]
        time_last = contract_info['time_last']
        money_strength = contract_info['money'] ** 1.1 * math.log(time_last)
        init_value = contract_info['init_value']
        distance = contract_info['distance']

        importance = money_strength * init_value * distance
        # set weight to the edge in network -- importance
        self.edge_multi_contract[edge][link_contract]['importance'] = importance

    def build_network(self):
        # use self.edge_multi_contract to build up network for pr calculating
        # build up network instance
        _graph = nx.DiGraph()

        for edge in self.edge_multi_contract:

            sum_importance = 0
            for each_contract in self.edge_multi_contract[edge]:
                sum_importance += self.edge_multi_contract[edge][each_contract]['importance']

            _graph.add_edge(edge[0], edge[1], importance=sum_importance)

        return _graph

    def pagerank(self):
        # 统一计算pr
        # 更新频次：每日，而不是每次action
        self.graph = self.build_network()
        pr_dict = nx.pagerank(self.graph, alpha=0.9, weight='importance', max_iter=1000)
        return pr_dict

    def everyday_time_last_effect(self):
        # 每天统一查看状态
        # 每天对于状态不变的所有已存在contract or edge，则time_last自动+1
        # 每天10点此script都会运行，所以如果没有合约取消，则time_last自动+1
        # time_last+1

        # 此函数在everyday_check_isAward()之后进行，所以无需判别isAward，直接所有time_last+1，然后重新计算importance即可
        # loop through self.edge_multi_contract to increase time_last+1 to all existing contract
        for edge in self.edge_multi_contract:
            for each_contract in self.edge_multi_contract[edge]:
                old_last_time = self.edge_multi_contract[edge][each_contract]['time_last']
                old_money_strength = self.edge_multi_contract[edge][each_contract]['money_strength']
                # update time_last + 1
                self.edge_multi_contract[edge][each_contract]['time_last'] += 1
                # update money_strength
                new_money_strength = old_money_strength * math.log(old_last_time + 2) / math.log(old_last_time + 1)
                self.edge_multi_contract[edge][each_contract]['money_strength'] = new_money_strength

                # update importance
                _contract_info = self.edge_multi_contract[edge][each_contract]
                new_importance = new_money_strength * _contract_info['distance'] * _contract_info['init_value']
                self.edge_multi_contract[edge][each_contract]['importance'] = new_importance

    def everyday_check_isAward(self, info_list):
        # check the recorded_info_list
        # remove_list contains link_contract_add to be removed from self.edge_multi_contract[edge][each_contract]
        remove_list = []
        for i in info_list:
            if i['isAward_'] == False:
                remove_list.append(i['link_contract'])

        remove_info_record = []
        # loop through self.edge_multi_contract to remove link_contract_add with isAward_==False everyday
        for edge in self.edge_multi_contract:
            for each_contract in self.edge_multi_contract[edge]:
                if self.edge_multi_contract[edge][each_contract]['link_contract'] in remove_list:
                    # need to record the edge to use it later to remove from dict
                    # cannot del it now or the changing of dict will influence the loop process
                    _need_to_remove = {}
                    _need_to_remove['edge'] = edge
                    _need_to_remove['link_contract'] = each_contract
                    remove_info_record.append(_need_to_remove)
                    # del self.edge_multi_contract[edge][each_contract]

        # remove
        for i in remove_info_record:
            _edge = i['edge']
            _link_contract = i['link_contract']
            del self.edge_multi_contract[_edge][_link_contract]

    def whole_pipeline_logic(self):
        '''
        load_last_day_edge_multi_contract()
        everyday_check_isAward()
        everyday_time_last_effect()
        for i in info_list():
            build_from_new_transction()
            
        generate_api_info()
        save_today_edge_multi_contract()
        '''
        pass

    def generate_api_info(self):
        # 生成下一阶段api数据

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
        for edge in self.edge_multi_contract:
            A, B = edge
            add_A, add_B = self.index2add[A], self.index2add[B]
            edge_info = self.edge_multi_contract[edge]
            for each_contract in edge_info:
                link_contract = edge_info[each_contract]['link_contract']
                importance = edge_info[each_contract]['importance']

                if link_contract not in importance_dict:
                    importance_dict[link_contract] = {}

                _link = add_A + '--->' + add_B
                importance_dict[link_contract][_link] = importance

        return add2pr, importance_dict

    def load_info(self, add):
        # load last edge_multi_contract
        with open(add, 'rb') as f:
            _dict = pickle.load(f)
        self.edge_multi_contract = _dict

    def save_info(self, add):
        # save today edge_multi_contract
        # if not os.path.exists(add):
        #    print(add + " doesn't exist.")
        with open(add, 'wb') as f:
            pickle.dump(self.edge_multi_contract, f, protocol=pickle.HIGHEST_PROTOCOL)
