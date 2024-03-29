import networkx as nx
import math
import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
import logging
from copy import deepcopy
from decimal import Decimal, getcontext
getcontext().prec = 100


class directed_graph:

    def __init__(self, deadline_timestamp, coin_info, link_rate, nft_info, nft_cap):
        # directed_graph
        self.graph = nx.DiGraph()
        self.nodes = list(self.graph.nodes)
        self.edges = list(self.graph.edges)
        # Key: address, Value: index
        self.add2index = {}
        # Key: index, Value: address
        self.index2add = {}
        # PR values yesterday
        self.old_pr = {}
        # default PR value for new user
        self.default_pr = 0.5
        # all contracts for calculate PR
        self.edge_multi_contract = {}
        # new users today(no PR value yesterday)
        self.join_today = {}
        # deadline for data collection
        self.deadline_timestamp = deadline_timestamp
        # coin price and coefficient
        self.coin_info = coin_info
        # nft price and coefficient
        self.nft_info = nft_info
        # link usd rate
        self.link_rate = link_rate
        # logger
        self.logger = logging.getLogger('calculate')
        # default distance
        self.default_distance = None
        # nft value cap
        self.nft_cap = nft_cap

    def _add_node(self, user_address, contract_address, chain):
        # user is exist
        if user_address in self.add2index:
            index = self.add2index[user_address]
            # user has PR value
            if index in self.old_pr:
                pass
            else:
                # user already joined today
                if index in self.join_today:
                    try:
                        self.join_today[index]['later_come'][chain].append(contract_address)
                    except:
                        self.join_today[index]['later_come'][chain] = [contract_address]
                else:
                    # mark user as new user
                    self.join_today[index] = {'add': user_address}
                    self.join_today[index]['later_come'] = {chain: []}
                    self.join_today[index]['first_pr'] = None
        # user is completely new
        else:
            # add user to network
            if self.index2add == {}:
                index = 1
            else:
                index = max(self.index2add) + 1
            self.add2index[user_address] = index
            self.index2add[index] = user_address
            # mark user as new user
            self.join_today[index] = {'add': user_address}
            self.join_today[index]['later_come'] = {chain: []}
            self.join_today[index]['first_pr'] = None
        if index not in self.graph.nodes:
            self.graph.add_node(index)
        return index

    def _get_edge(self, user_a_address, user_b_address):
        if user_a_address in self.add2index:
            index_a = self.add2index[user_a_address]
        else:
            return None, None
        if user_b_address in self.add2index:
            index_b = self.add2index[user_b_address]
        else:
            return None, None
        return (index_a, index_b), (index_b, index_a)

    def _add_edge(self, index_a, index_b):
        edge_AB = (index_a, index_b)
        edge_BA = (index_b, index_a)
        if edge_AB not in self.edge_multi_contract:
            self.edge_multi_contract[edge_AB] = {}
        if edge_BA not in self.edge_multi_contract:
            self.edge_multi_contract[edge_BA] = {}
        return edge_AB, edge_BA

    def to_precision_decimal(self, value):
        if isinstance(value, Decimal):
            return value
        if 'e-' in str(value) or 'E-' in str(value):
            float_v, e_num = str(value).split('-')
            if '.' in float_v:
                number_v, f = float_v[:-1].split('.')
            else:
                number_v, f = float_v[:-1], ''
            e_num = int(e_num)
            if e_num - len(number_v) > 0:
                new_value = '0.' + '0' * (e_num - len(number_v)) + number_v + f
            else:
                new_value = number_v[:-e_num] + '.' + number_v[-e_num:] + f
            i_f = new_value.split('.')
        elif 'e+' in str(value) or 'E+' in str(value):
            float_v, e_num = str(value).split('+')
            if '.' in float_v:
                number_v, f = float_v[:-1].split('.')
            else:
                number_v, f = float_v[:-1], ''
            e_num = int(e_num)
            if e_num - len(f) > 0:
                new_value = number_v + f[:e_num] + '0' * (e_num - len(f))
            else:
                new_value = number_v + f[:e_num] + '.' + f[e_num:]
            i_f = new_value.split('.')
        else:
            i_f = str(value).split('.')
        if len(i_f) == 1:
            result = i_f[0]
        else:
            result = "{}.{}".format(i_f[0], i_f[1][:8])
        return Decimal(result)
    
    def to_precision_float(self, value, count=15):
        if 'e-' in str(value) or 'E-' in str(value):
            float_v, e_num = str(value).split('-')
            if '.' in float_v:
                number_v, f = float_v[:-1].split('.')
            else:
                number_v, f = float_v[:-1], ''
            e_num = int(e_num)
            if e_num - len(number_v) > 0:
                new_value = '0.' + '0' * (e_num - len(number_v)) + number_v + f
            else:
                new_value = number_v[:-e_num] + '.' + number_v[-e_num:] + f
            i_f = new_value.split('.')
        elif 'e+' in str(value) or 'E+' in str(value):
            float_v, e_num = str(value).split('+')
            if '.' in float_v:
                number_v, f = float_v[:-1].split('.')
            else:
                number_v, f = float_v[:-1], ''
            e_num = int(e_num)
            if e_num - len(f) > 0:
                new_value = number_v + f[:e_num] + '0' * (e_num - len(f))
            else:
                new_value = number_v + f[:e_num] + '.' + f[e_num:]
            i_f = new_value.split('.')
        else:
            i_f = str(value).split('.')
        if len(i_f) == 1:
            result = i_f[0]
        else:
            result = "{}.{}".format(i_f[0], i_f[1][:count])
        return float(result)
    
    def to_precision_float_by_list(self, _list, count=15):
        for index, i in enumerate(_list):
                _list[index] = self.to_precision_float(i, count=count)
        return _list

    def cal_importance(self, s, d, c, i):
        result = Decimal(str(s)) * Decimal(str(min(d, self.default_distance))) * Decimal(str(c)) * Decimal(str(i))
        return self.to_precision_decimal(str(result))

    def build_from_new_transaction(self, info):
        # filter by isAward_
        if not info['isAward_']:
            return
        userA_ = info['userA_']
        userB_ = info['userB_']
        lockDays_ = info['lockDays_']
        startTime_ = info['startTime_']
        link_contract = info['link_contract']
        chain = info['chain']
        # coin contract
        if 'symbol_' in info:
            # filter by symbol
            symbol_ = info['symbol_'].upper()
            if symbol_ not in self.coin_info:
                self.logger.error('{} is not supported, transaction ignored'.format(symbol_))
                return
            amountA_ = info['amountA_']
            amountB_ = info['amountB_']
            percentA_ = info['percentA_']
            total_amount = amountA_ + amountB_

            # usd threshold
            usd = self._cal_dollar(symbol_, total_amount)
            if not self._is_valid_link(percentA_, usd):
                return

            # add node to network
            index_A = self._add_node(userA_, link_contract, chain)
            index_B = self._add_node(userB_, link_contract, chain)

            # add edge to network
            edge_AB, edge_BA = self._add_edge(index_A, index_B)

            # calculate init_value
            init_value_AB, init_value_BA = self._cal_i(index_A, index_B, link_contract, chain)

            s = self._cal_s(usd, self._cal_contract_duration(lockDays_, startTime_))
            d = self._cal_d(index_A, index_B)
            c = self._cal_c(symbol_)
            i_ab = init_value_AB
            i_ba = init_value_BA

            # calculate importance
            importance_AB = self.cal_importance(s, d, c, i_ab)
            importance_BA = self.cal_importance(s, d, c, i_ba)

            contract_AB_info = {'symbol': symbol_, 'link_contract': link_contract, 'lock_days': lockDays_,
                                'start_time': startTime_, 'amount': total_amount, 'init_value': init_value_AB,
                                'distance': d, 'importance': importance_AB, 'percentA': percentA_}
            contract_BA_info = {'symbol': symbol_, 'link_contract': link_contract, 'lock_days': lockDays_,
                                'start_time': startTime_, 'amount': total_amount, 'init_value': init_value_BA,
                                'distance': d, 'importance': importance_BA, 'percentA': percentA_}
        # nft contract
        elif 'nft_' in info:
            # filter by nft
            nft_ = info['nft_']
            if nft_ not in self.nft_info:
                self.logger.error('NFT: {} is not supported, transaction ignored'.format(nft_))
                return
            idA_ = info['idA_']
            idB_ = info['idB_']
            single = info['single']
            if single is True:
                percentA_ = 100
            else:
                percentA_ = 50

            # usd threshold
            usd = self._cal_nft_dollar(nft_)
            if not self._is_valid_link(percentA_, usd):
                return

            # add node to network
            index_A = self._add_node(userA_, link_contract, chain)
            index_B = self._add_node(userB_, link_contract, chain)

            # add edge to network
            edge_AB, edge_BA = self._add_edge(index_A, index_B)

            # calculate init_value
            init_value_AB, init_value_BA = self._cal_i(index_A, index_B, link_contract, chain)

            s = self._cal_s(usd, self._cal_contract_duration(lockDays_, startTime_))
            d = self._cal_d(index_A, index_B)
            c = self._cal_c_nft(nft_)
            i_ab = init_value_AB
            i_ba = init_value_BA

            # calculate importance
            importance_AB = self.cal_importance(s, d, c, i_ab)
            importance_BA = self.cal_importance(s, d, c, i_ba)

            contract_AB_info = {'nft': nft_, 'link_contract': link_contract, 'lock_days': lockDays_,
                                'start_time': startTime_, 'id_a': idA_, 'id_b': idB_, 'init_value': init_value_AB,
                                'distance': d, 'importance': importance_AB, 'percentA': percentA_}
            contract_BA_info = {'nft': nft_, 'link_contract': link_contract, 'lock_days': lockDays_,
                                'start_time': startTime_, 'id_a': idA_, 'id_b': idB_, 'init_value': init_value_BA,
                                'distance': d, 'importance': importance_BA, 'percentA': percentA_}
        else:
            self.logger.error('Invalid Contract Info: {}'.format(info))
            return
        # add contract_AB_info and contract_AB_info into the edge_multi_contract dict
        if chain not in self.edge_multi_contract[edge_AB]:
            self.edge_multi_contract[edge_AB][chain] = {}
        if chain not in self.edge_multi_contract[edge_BA]:
            self.edge_multi_contract[edge_BA][chain] = {}
        self.edge_multi_contract[edge_AB][chain][link_contract] = contract_AB_info
        self.edge_multi_contract[edge_BA][chain][link_contract] = contract_BA_info

    def _is_valid_link(self, percent_a, usd):
        if 100 == percent_a and usd < self.link_rate:
            return False
        else:
            return True

    def _cal_d(self, index_a, index_b):
        # if a and b have active contracts already, use exist distance value
        edge_AB = (index_a, index_b)
        if edge_AB in self.edge_multi_contract and self.edge_multi_contract[edge_AB] != {}:
            for chain in self.edge_multi_contract[edge_AB].keys():
                for contract in self.edge_multi_contract[edge_AB][chain].keys():
                    distance = self.edge_multi_contract[edge_AB][chain][contract].get('distance', None)
                    return self.to_precision_decimal(distance)
        # calculate distance
        try:
            distance = nx.shortest_path_length(self.graph, index_a, index_b)
        except:
            distance = self.default_distance
        return self.to_precision_decimal(distance)

    def _cal_i(self, index_a, index_b, contract_address, chain):
        # if a and b have active contracts already, use exist init value
        edge_AB = (index_a, index_b)
        edge_BA = (index_b, index_a)
        if edge_AB in self.edge_multi_contract and edge_BA in self.edge_multi_contract \
                and self.edge_multi_contract[edge_AB] != {} and self.edge_multi_contract[edge_BA] != {}:
            init_value_AB = None
            for each_chain in self.edge_multi_contract[edge_AB].keys():
                for contract in self.edge_multi_contract[edge_AB][each_chain].keys():
                    init_value_AB = self.edge_multi_contract[edge_AB][each_chain][contract].get('init_value', None)
                    break
            init_value_BA = None
            for each_chain in self.edge_multi_contract[edge_BA].keys():
                for contract in self.edge_multi_contract[edge_BA][each_chain].keys():
                    init_value_BA = self.edge_multi_contract[edge_BA][each_chain][contract].get('init_value', None)
                    break
            if init_value_AB is not None and init_value_BA is not None:
                return self.to_precision_decimal(init_value_AB), self.to_precision_decimal(init_value_BA)
        # 1st turn, all_init_value = 0.5
        if self.old_pr == {}:
            init_value_A = 0.5
            init_value_B = 0.5
        # 2 new users
        elif index_a not in self.old_pr and index_b not in self.old_pr:
            # not first contract for user A today
            if contract_address in self.join_today[index_a]['later_come'][chain]:
                init_value_A = self.join_today[index_a]['first_pr']
                first_of_a = False
            # first contract
            else:
                init_value_A = self.default_pr
                first_of_a = True
            # not first contract for user B today
            if contract_address in self.join_today[index_b]['later_come'][chain]:
                init_value_B = self.join_today[index_b]['first_pr']
                first_of_b = False
            # first contract
            else:
                init_value_B = self.default_pr
                first_of_b = True
            # save first contract info
            if first_of_a:
                if first_of_b:
                    # other contract of A must use init value of B
                    self.join_today[index_a]['first_pr'] = init_value_B
                    # other contract of B must use init value of A
                    self.join_today[index_b]['first_pr'] = init_value_A
                else:
                    # other contract of A must use init value of B
                    self.join_today[index_a]['first_pr'] = init_value_B
            else:
                if first_of_b:
                    # other contract of B must use init value of A
                    self.join_today[index_b]['first_pr'] = init_value_A
                else:
                    pass
        # A in network, B is new
        elif index_a in self.old_pr and index_b not in self.old_pr:
            init_value_A = self.old_pr[index_a]
            init_value_A = max(init_value_A, self.default_pr * 3)
            # not first contract for user B today
            if contract_address in self.join_today[index_b]['later_come'][chain]:
                init_value_B = self.default_pr
            # first contract
            else:
                init_value_B = self.default_pr
                # other contract of B must use init value of A
                self.join_today[index_b]['first_pr'] = init_value_A
        # B in network, A is new
        elif index_a not in self.old_pr and index_b in self.old_pr:
            init_value_B = self.old_pr[index_b]
            init_value_B = max(init_value_B, self.default_pr * 3)
            # not first contract for user A today
            if contract_address in self.join_today[index_a]['later_come'][chain]:
                init_value_A = self.default_pr
            # first contract
            else:
                init_value_A = self.default_pr
                # other contract of A must use init value of B
                self.join_today[index_a]['first_pr'] = init_value_B
        # both A and B are in the network
        else:
            init_value_A = self.old_pr[index_a]
            init_value_B = self.old_pr[index_b]

        final_init_value_A = init_value_A / (init_value_A + init_value_B)
        final_init_value_B = init_value_B / (init_value_A + init_value_B)

        # 0.1<=init_value<=0.9
        final_init_value_A = max(final_init_value_A, 0.1)
        final_init_value_A = min(final_init_value_A, 0.9)
        final_init_value_B = max(final_init_value_B, 0.1)
        final_init_value_B = min(final_init_value_B, 0.9)

        init_value_AB = final_init_value_B
        init_value_BA = final_init_value_A
        return self.to_precision_decimal(init_value_AB), self.to_precision_decimal(init_value_BA)

    def _cal_contract_duration(self, lock_days, start_time):
        duration_days = (self.deadline_timestamp - start_time) / 86400
        if duration_days > int(duration_days):
            duration_days = int(duration_days) + 1
        return max(lock_days, duration_days) + 1

    def _cal_dollar(self, symbol, amount):
        return amount * self.coin_info[symbol]['price'] / 10 ** self.coin_info[symbol]['decimals']

    def _cal_nft_dollar(self, nft):
        nft_price = self.nft_info[nft]['price']
        return min(nft_price * 2, self.nft_cap)

    def _cal_s(self, dollar, duration):
        # return (dollar ** 1.1) * math.log(duration)
        return (Decimal(str(dollar)) ** Decimal(str(1.01))) * Decimal(str(math.log(duration)))

    def _cal_c(self, symbol):
        return self.coin_info[symbol]['coefficient']

    def _cal_c_nft(self, nft):
        return self.nft_info[nft]['coefficient']

    def _build_network(self):
        # use self.edge_multi_contract to build up network for pr calculating
        # temp graph for distance calculation
        temp_graph = nx.DiGraph()
        for edge in self.edge_multi_contract:
            valid_edge = False
            for each_chain in self.edge_multi_contract[edge]:
                for each_contract in self.edge_multi_contract[edge][each_chain]:
                    if 'symbol' in self.edge_multi_contract[edge][each_chain][each_contract]:
                        symbol = self.edge_multi_contract[edge][each_chain][each_contract]['symbol'].upper()
                        if symbol in self.coin_info:
                            valid_edge = True
                            break
                        else:
                            self.logger.info('{} is not supported, transaction ignored'.format(symbol))
                    elif 'nft' in self.edge_multi_contract[edge][each_chain][each_contract]:
                        nft = self.edge_multi_contract[edge][each_chain][each_contract]['nft']
                        if nft in self.nft_info:
                            valid_edge = True
                            break
                        else:
                            self.logger.info('NFT: {} is not supported, transaction ignored'.format(nft))
                if valid_edge is True:
                    break
            if valid_edge is True:
                temp_graph.add_edge(edge[0], edge[1])
        # set default distance
        self.default_distance = self._cal_default_distance(old_pr=self.old_pr, graph=temp_graph)
        temp_graph.clear()
        # build up network instance
        _graph = nx.DiGraph()
        for edge in self.edge_multi_contract:
            sum_importance = 0
            for each_chain in self.edge_multi_contract[edge]:
                for each_contract in self.edge_multi_contract[edge][each_chain]:
                    # cal again since coin price and duration changed
                    if 'symbol' in self.edge_multi_contract[edge][each_chain][each_contract]:
                        symbol = self.edge_multi_contract[edge][each_chain][each_contract]['symbol'].upper()
                        if symbol in self.coin_info:
                            total_amount = self.edge_multi_contract[edge][each_chain][each_contract]['amount']
                            lock_days = self.edge_multi_contract[edge][each_chain][each_contract]['lock_days']
                            start_time = self.edge_multi_contract[edge][each_chain][each_contract]['start_time']
                            usd = self._cal_dollar(symbol, total_amount)
                            s = self._cal_s(usd, self._cal_contract_duration(lock_days, start_time))
                            d = self.edge_multi_contract[edge][each_chain][each_contract]['distance']
                            c = self._cal_c(symbol)
                            i = self.edge_multi_contract[edge][each_chain][each_contract]['init_value']
                            importance = self.cal_importance(s, d, c, i)
                            # update importance
                            self.edge_multi_contract[edge][each_chain][each_contract]['importance'] = importance
                            sum_importance += importance
                        else:
                            self.logger.info('{} is not supported, transaction ignored'.format(symbol))
                    elif 'nft' in self.edge_multi_contract[edge][each_chain][each_contract]:
                        nft = self.edge_multi_contract[edge][each_chain][each_contract]['nft']
                        if nft in self.nft_info:
                            lock_days = self.edge_multi_contract[edge][each_chain][each_contract]['lock_days']
                            start_time = self.edge_multi_contract[edge][each_chain][each_contract]['start_time']
                            usd = self._cal_nft_dollar(nft)
                            s = self._cal_s(usd, self._cal_contract_duration(lock_days, start_time))
                            d = self.edge_multi_contract[edge][each_chain][each_contract]['distance']
                            c = self._cal_c_nft(nft)
                            i = self.edge_multi_contract[edge][each_chain][each_contract]['init_value']
                            importance = self.cal_importance(s, d, c, i)
                            # update importance
                            self.edge_multi_contract[edge][each_chain][each_contract]['importance'] = importance
                            sum_importance += importance
                        else:
                            self.logger.info('NFT: {} is not supported, transaction ignored'.format(nft))
            if sum_importance != 0:
                _graph.add_edge(edge[0], edge[1], importance=sum_importance)
        return _graph

    def _pagerank(self, alpha=1, max_iter=1000, error_tor=1e-09, weight='importance', symbol=None):
        # based on cal logic, no data(importance=0) will show up in pr cal,
        # thus no need to be prepared for row.sum=0 in sparse_matrix.sum(axis=1) while normalizing
        unchanged_edge_multi_contract = deepcopy(self.edge_multi_contract)
        # filter contracts
        if symbol is not None:
            individual_edge_multi_contract = {}
            contract_exist_flag = False
            symbol = symbol.upper()
            for edge in self.edge_multi_contract:
                individual_edge_multi_contract[edge] = {}
                for chain in self.edge_multi_contract[edge]:
                    individual_edge_multi_contract[edge][chain] = {}
                    for contract in self.edge_multi_contract[edge][chain]:
                        if 'symbol' in self.edge_multi_contract[edge][chain][contract] \
                                and symbol == self.edge_multi_contract[edge][chain][contract]['symbol'].upper():
                            individual_edge_multi_contract[edge][chain][contract] = \
                                self.edge_multi_contract[edge][chain][contract]
                            contract_exist_flag = True
            if not contract_exist_flag:
                return {}
            else:
                self.edge_multi_contract = individual_edge_multi_contract
        else:
            pass
        _e = 0
        # edge_weight = {edge:its_total_improtance}
        edges = []
        nodes_set = set()
        edge_weight = {}
        for edge in self.edge_multi_contract:
            total_weight = 0
            for chain in self.edge_multi_contract[edge]:
                for contract in self.edge_multi_contract[edge][chain]:
                    total_weight += self.edge_multi_contract[edge][chain][contract][weight]
            if total_weight > 0:
                edge_weight[edge] = self.to_precision_float(total_weight)
                edges.append(edge)
                nodes_set.add(edge[0])
                nodes_set.add(edge[1])

        # add virtual node
        # setup virtual node
        virtual_node = max(nodes_set) + 1
        # cal medium_weight
        # median_weight = np.median(list(edge_weight.values()))
        # cal node_strength
        node_strength = {}
        for i in edge_weight:
            _to_node = i[1]
            if _to_node not in node_strength:
                node_strength[_to_node] = edge_weight[i]
            else:
                node_strength[_to_node] += edge_weight[i]

        # add bi-direction edges between virtual node and all the other nodes
        for node in list(nodes_set):
            # node_strength as virtual edge importance
            edge_weight[(virtual_node, node)] = node_strength[node] / 10
            edge_weight[(node, virtual_node)] = node_strength[node] / 10
            edges.append((virtual_node, node))
            edges.append((node, virtual_node))

        nodes_set.add(virtual_node)
        nodes = list(nodes_set)
        N = len(nodes)

        #############################################
        # index: 1->N
        # node: actual numbers
        index2node = {}
        node2index = {}
        for i, j in enumerate(nodes):
            index2node[i + 1] = j
            node2index[j] = i + 1

        converted_edge_weight = {}
        for edge in edge_weight:
            left_node, right_node = edge
            converted_left_node, converted_right_node = node2index[left_node], node2index[right_node]
            converted_edge = (converted_left_node, converted_right_node)
            converted_edge_weight[converted_edge] = edge_weight[edge]

        edge_weight = converted_edge_weight
        #############################################

        # W = np.zeros([N, N])
        # for i in edge_weight:
        #     W[i[0] - 1][i[1] - 1] = edge_weight[i]

        W = lil_matrix((N, N))
        for i in edge_weight:
            W[i[0] - 1, i[1] - 1] = edge_weight[i]

            # sparse m
        weighted_S = W.tocsr()
        # normalize with _e
        weighted_S = weighted_S / (weighted_S.sum(axis=1) + _e)
        # sparse again
        weighted_S = csr_matrix(weighted_S)
        for index, d in enumerate(weighted_S.data):
            weighted_S.data[index] = self.to_precision_float(d, count=14)

        # dangling node
        dangling_nodes = []
        for i in range(N):
            if weighted_S[:][i].sum() == 0:
                dangling_nodes.append(i)

        init = np.ones(N) / N
        _init = np.ones(N) / N
        transfered_init = np.zeros(N) / N
        error = 1000

        count = 0
        e_list = []
        for _ in range(max_iter):
            danglesum = alpha * sum([transfered_init[i] for i in dangling_nodes])
            # transfered_init = np.dot(init,A)
            # transfered_init = alpha * init * weighted_S + np.ones(N) / N * danglesum + (1 - alpha) * np.ones(N) / N

            step1_value = alpha * init
            step1_value = self.to_precision_float_by_list(step1_value, count=14)
            step1_value = step1_value * weighted_S
            step1_value = self.to_precision_float_by_list(step1_value, count=14)

            step2_value = _init * danglesum
            step2_value = self.to_precision_float_by_list(step2_value, count=14)
            
            step3_value = (1 - alpha) * np.ones(N)
            step3_value = self.to_precision_float_by_list(step3_value, count=14)
            step3_value = step3_value / N
            step3_value = self.to_precision_float_by_list(step3_value, count=14)
            
            transfered_init = step1_value + step2_value + step3_value

            for index, i in enumerate(transfered_init):
                transfered_init[index] = self.to_precision_float(i, count=14)
            # transfered_init += np.ones(N)/N*danglesum
            error = transfered_init - init
            error = max(map(abs, error))
            e_list.append(error)
            init = transfered_init
            count += 1

            if error < error_tor:
                break

        pr = {}
        for index, i in enumerate(transfered_init):
            pr[index2node[index + 1]] = self.to_precision_float(i)

        # delete virtual pr
        virtual_node_pr = pr[virtual_node]
        del pr[virtual_node]

        # redistribute virtual node's pr
        # each node gets their part by pr_i/(1-virtual_pr)
        _sum_without_virtual_node = self.to_precision_float(1 - virtual_node_pr)
        for node in [i for i in nodes if i != virtual_node]:
            node_ratio = self.to_precision_float(pr[node] / _sum_without_virtual_node)
            node_virtual = node_ratio * virtual_node_pr
            node_virtual = self.to_precision_float(node_virtual)
            pr[node] += node_virtual
            pr[node] = self.to_precision_float(pr[node])

        # double normalize in case sum!=0 due to python computing problem
        _sum = 0
        for v in pr.values():
            _sum += v
            _sum = self.to_precision_float(_sum)
        for node in pr:
            pr[node] /= _sum
            pr[node] = self.to_precision_float(pr[node])

        # introducing "add" component
        # build up node_weight, using info from edge_multi_contract
        edge_merge_info = {}
        for edge in self.edge_multi_contract:
            _weight = 0
            for chain in self.edge_multi_contract[edge]:
                for contract in self.edge_multi_contract[edge][chain]:
                    _weight += float(self.edge_multi_contract[edge][chain][contract]['importance'])
            if _weight > 0:
                edge_merge_info[edge] = self.to_precision_float(_weight)

        node_weight = {}
        for edge in edge_merge_info:
            _node = edge[1]
            _weight = edge_merge_info[edge]
            if _node in node_weight:
                node_weight[_node] += _weight
                node_weight[_node] = self.to_precision_float(node_weight[_node])
            else:
                node_weight[_node] = _weight

        pr_new = {}
        base = 0.5
        _sum_weight = 0
        for v in node_weight.values():
            _sum_weight += v
            _sum_weight = self.to_precision_float(_sum_weight)

        for node in pr:
            pr_weight = base * node_weight[node] / _sum_weight
            pr_weight = self.to_precision_float(pr_weight)
            _pr = pr[node] + pr_weight
            pr_new[node] = self.to_precision_float(_pr)

        # normalize pr_new
        _sum_pr_new = 0
        for v in pr_new.values():
            _sum_pr_new += v
            _sum_pr_new = self.to_precision_float(_sum_pr_new)
        for i in pr_new:
            pr_new[i] /= _sum_pr_new
            pr_new[i] = self.to_precision_float(pr_new[i])

        # restore edge_multi_contract
        self.edge_multi_contract = unchanged_edge_multi_contract

        return pr_new

    def remove_transactions(self, remove_list):
        for transaction in remove_list:
            link = transaction['link_contract']
            user_a = transaction['userA_']
            user_b = transaction['userB_']
            chain = transaction['chain']
            edge_ab, edge_ba = self._get_edge(user_a, user_b)
            if edge_ab is not None:
                try:
                    del self.edge_multi_contract[edge_ab][chain][link]
                except:
                    self.logger.info('No Link: {}, {}, {}'.format(edge_ab, chain, link))
                try:
                    if self.edge_multi_contract[edge_ab][chain] == {}:
                        del self.edge_multi_contract[edge_ab][chain]
                except:
                    self.logger.info('No Chain: {}, {}'.format(edge_ab, chain))
                try:
                    if self.edge_multi_contract[edge_ab] == {}:
                        del self.edge_multi_contract[edge_ab]
                except:
                    self.logger.info('No Edge: {}'.format(edge_ab))
            if edge_ba is not None:
                try:
                    del self.edge_multi_contract[edge_ba][chain][link]
                except:
                    self.logger.info('No Link: {}, {}, {}'.format(edge_ba, chain, link))
                try:
                    if self.edge_multi_contract[edge_ba][chain] == {}:
                        del self.edge_multi_contract[edge_ba][chain]
                except:
                    self.logger.info('No Chain: {}, {}'.format(edge_ba, chain))
                try:
                    if self.edge_multi_contract[edge_ba] == {}:
                        del self.edge_multi_contract[edge_ba]
                except:
                    self.logger.info('No Edge: {}'.format(edge_ba))

    def generate_pr(self):
        # build up add2pr
        # format: user_add:user_pr
        index2pr = self._pagerank()
        add2pr = {}
        for i in index2pr:
            add = self.index2add[i]
            add2pr[add] = index2pr[i]
        return add2pr

    def generate_importance(self):
        # build up importance dict
        # format: {chain: {link_contract:{A-->B:importance,B-->A:importance}}}
        importance_dict = {}
        for edge in self.edge_multi_contract:
            A, B = edge
            add_A, add_B = self.index2add[A], self.index2add[B]
            edge_info = self.edge_multi_contract[edge]
            for chain in edge_info:
                if chain not in importance_dict:
                    importance_dict[chain] = {}
                for each_contract in edge_info[chain]:
                    link_contract = edge_info[chain][each_contract]['link_contract']
                    importance = edge_info[chain][each_contract]['importance']
                    if link_contract not in importance_dict[chain]:
                        importance_dict[chain][link_contract] = {}
                    _link = add_A + '--->' + add_B
                    importance_dict[chain][link_contract][_link] = str(importance)
        return importance_dict

    def load_contract_and_user(self, contract_and_user):
        # load last edge_multi_contract + add2index + index2add
        _dict, add2index, index2add = contract_and_user
        self.edge_multi_contract = _dict
        self.add2index = add2index
        self.index2add = index2add
        # build old_pr
        self.old_pr = self._pagerank()
        self.default_pr = 0.1 * np.median(list(self.old_pr.values()))
        # build and update graph
        self.graph = self._build_network()

    def get_contract_and_user(self):
        contract_and_user = (self.edge_multi_contract, self.add2index, self.index2add)
        return contract_and_user

    def generate_pr_info(self, symbol):
        # build up add2pr
        # format: user_add:user_pr
        index2pr = self._pagerank(symbol=symbol)
        add2pr = {}
        for i in index2pr:
            add = self.index2add[i]
            add2pr[add] = index2pr[i]
        return add2pr

    def _cal_default_distance(self, old_pr, graph):
        if old_pr == {}:
            distance = 1
        else:
            max_pr = max(old_pr.values())
            highest_pr_node = -1
            for node in old_pr:
                if old_pr[node] == max_pr:
                    highest_pr_node = node
            if highest_pr_node < 0:
                raise Exception('Cannot find the highest_pr node.')
            distance_dict = nx.single_source_shortest_path_length(graph, highest_pr_node)
            del distance_dict[highest_pr_node]
            if distance_dict == {}:
                distance = 1
            else:
                distance = min(3 * np.mean(list(distance_dict.values())), 21)
        return distance
