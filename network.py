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

        self.old_pr = {}

        self.edge_multi_contract = {}

        self.join_today = {}

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
        
        total_money = amountA_ + amountB_

        if self.old_pr == {}:
            default_pr = 0.5
        else:
            default_pr = 0.1 * np.median(list(self.old_pr.values()))

        if not isAward_:
            return None
        # new add --> new index+1
        if userA_ not in self.add2index:

            if self.index2add == {}:
                index_A = 1
            else:
                index_A = max(self.index2add) + 1
            # update add2index and index2add
            self.add2index[userA_] = index_A
            self.index2add[index_A] = userA_

            self.join_today[index_A] = {'add': userA_}
            self.join_today[index_A]['later_come'] = []
            self.join_today[index_A]['first_pr'] = None

            # if index_B not in self.old_pr:
            first_pr = default_pr
            if userB_ in self.add2index:
                if self.add2index[userB_] in self.old_pr:
                    first_pr = self.old_pr[self.add2index[userB_]]
            self.join_today[index_A]['first_pr'] = first_pr

        else:
            index_A = self.add2index[userA_]

            if index_A in self.join_today:
                self.join_today[index_A]['later_come'].append(link_contract)

        if userB_ not in self.add2index:
            index_B = max(self.index2add) + 1
            # update add2index and index2add
            self.add2index[userB_] = index_B
            self.index2add[index_B] = userB_

            self.join_today[index_B] = {'add': userB_}
            self.join_today[index_B]['later_come'] = []
            self.join_today[index_B]['first_pr'] = None

            # if index_B not in self.old_pr:
            first_pr = default_pr
            if userA_ in self.add2index:
                if self.add2index[userA_] in self.old_pr:
                    first_pr = self.old_pr[self.add2index[userA_]]

            self.join_today[index_B]['first_pr'] = first_pr
        else:
            index_B = self.add2index[userB_]

            if index_B in self.join_today:
                self.join_today[index_B]['later_come'].append(link_contract)

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

        contract_AB_info = {}
        contract_BA_info = {}

        # set weight to the edge in network -- status
        contract_AB_info['status'] = status_
        contract_BA_info['status'] = status_

        # set weight to the edge in network -- link_contract
        contract_AB_info['link_contract'] = link_contract
        contract_BA_info['link_contract'] = link_contract

        # set weight to the edge in network -- time_last
        # contract_AB_info['time_last']=1
        # contract_BA_info['time_last']=1
        contract_AB_info['time_last'] = lockDays_
        contract_BA_info['time_last'] = lockDays_

        # set weight to the edge in network -- money
        contract_AB_info['money'] = total_money
        contract_BA_info['money'] = total_money

        # set weight to the edge in network -- init_value
        # 1st turn, all_init_value = 0.5
        # pa = pb = 0.5
        if self.old_pr == {}:
            init_value_A = 0.5
            init_value_B = 0.5


        # 2 new users
        # pa = pb = _mean_old_pr
        elif index_A not in self.old_pr and index_B not in self.old_pr:
            # _mean_old_pr = np.mean(list(self.old_pr.values()))

            if link_contract in self.join_today[index_A]['later_come']:
                init_value_A = self.join_today[index_A]['first_pr']
            else:
                init_value_A = default_pr
            init_value_B = default_pr

        # A in network, B is new
        # pa = old_pr[A]
        # pb = _mean_old_pr
        elif index_A in self.old_pr and index_B not in self.old_pr:
            # _mean_old_pr = np.mean(list(self.old_pr.values()))
            init_value_A = self.old_pr[index_A]

            init_value_A = max(init_value_A, default_pr)

            if link_contract in self.join_today[index_B]['later_come']:
                init_value_B = self.join_today[index_B]['first_pr']
            else:
                init_value_B = default_pr

        # B in network, A is new
        # pa = _mean_old_pr
        # pb = old_pr[B]
        elif index_A in self.old_pr and index_B not in self.old_pr:
            # _mean_old_pr = np.mean(list(self.old_pr.values()))

            init_value_A = default_pr
            init_value_B = self.old_pr[index_B]

            init_value_B = max(init_value_B, default_pr)

        # both A and B are in the network
        # pa = old_pr[A]
        # pb = old_pr[B]
        else:
            init_value_A = self.old_pr[index_A]
            init_value_B = self.old_pr[index_B]

        final_init_value_A = init_value_A / (init_value_A + init_value_B)
        final_init_value_B = init_value_B / (init_value_A + init_value_B)

        # 0.1<=init_value<=0.9
        final_init_value_A = max(final_init_value_A, 0.1)
        final_init_value_A = min(final_init_value_A, 0.9)
        final_init_value_B = max(final_init_value_B, 0.1)
        final_init_value_B = min(final_init_value_B, 0.9)

        init_value_AB = final_init_value_B
        init_value_BA = final_init_value_A

        contract_AB_info['init_value'] = init_value_AB
        contract_BA_info['init_value'] = init_value_BA

        # set weight to the edge in network -- distance
        try:

            # directed_graph
            distance_len_AB = nx.shortest_path_length(self.graph, index_A, index_B)
            distance_len_BA = nx.shortest_path_length(self.graph, index_B, index_A)
            # double check
            assert distance_len_AB == distance_len_BA, 'path_len({}-->{}) != path_len({}-->{})'.format(str(index_A),
                                                                                                       str(index_B),
                                                                                                       str(index_B),
                                                                                                       str(index_A))

        except:

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

                distance_dict = nx.single_source_shortest_path_length(self.graph, highest_pr_node)

                del distance_dict[highest_pr_node]

                if distance_dict == {}:
                    distance_len_AB = distance_len_BA = 1

                else:
                    distance_len_AB = distance_len_BA = min(np.mean(list(distance_dict.values())), 21)

        contract_AB_info['distance'] = distance_len_AB
        contract_BA_info['distance'] = distance_len_BA

        # set weight to the edge in network -- importance
        # importance = money_strength * init_value * distance
        time_last_A = contract_AB_info['time_last']
        time_last_B = contract_BA_info['time_last']
        # +2 防止lockday=0
        money_strength_AB = (total_money ** 1.1) * math.log(time_last_B + 2)
        money_strength_BA = (total_money ** 1.1) * math.log(time_last_A + 2)

        importance_AB = money_strength_AB * init_value_AB * distance_len_AB
        importance_BA = money_strength_BA * init_value_BA * distance_len_BA

        contract_AB_info['money_strength'] = money_strength_AB
        contract_BA_info['money_strength'] = money_strength_BA

        contract_AB_info['importance'] = importance_AB
        contract_BA_info['importance'] = importance_BA

        # build up contract_AB_info and contract_AB_info successfully
        # add contract_AB_info and contract_AB_info into the edge_multi_contract dict

        contractAB_key = contract_AB_info['link_contract']
        contractBA_key = contract_BA_info['link_contract']
        self.edge_multi_contract[edge_AB][contractAB_key] = contract_AB_info
        self.edge_multi_contract[edge_BA][contractBA_key] = contract_BA_info

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
        self.graph = self.build_network()
        pr_dict = nx.pagerank(self.graph, alpha=0.9, weight='importance', max_iter=1000)
        return pr_dict

    def everyday_time_last_effect(self):

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

    def everyday_check_isAward(self, remove_set):
        remove_info_record = []
        # loop through self.edge_multi_contract to remove link_contract_add with isAward_==False everyday
        for edge in self.edge_multi_contract:
            for each_contract in self.edge_multi_contract[edge]:
                if self.edge_multi_contract[edge][each_contract]['link_contract'] in remove_set:
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
        # load last edge_multi_contract + add2index + index2add
        with open(add, 'rb') as f:
            info = pickle.load(f)

        _dict, add2index, index2add = info
        self.edge_multi_contract = _dict
        self.add2index = add2index
        self.index2add = index2add

        # build old_pr
        self.old_pr = self.pagerank()

    def save_info(self, add):
        # save today edge_multi_contract + add2index + index2add
        # if not os.path.exists(add):
        #    print(add + " doesn't exist.")
        info = (self.edge_multi_contract, self.add2index, self.index2add)
        with open(add, 'wb') as f:
            pickle.dump(info, f, protocol=pickle.HIGHEST_PROTOCOL)
