# -*- coding: utf-8 -*-
"""
Created on 2020/8/5
@project: SPAIC
@filename: Connection
@author: Hong Chaofei
@contact: hongchf@gmail.com

@description:
定义神经集群间的连接，包括记录神经元集群、连接的突触前、突触后神经元编号、连接形式（全连接、稀疏连接、卷积）、权值、延迟 以及连接产生函数、重连接函数等。
"""
from ..Network.Topology import Connection, SynapseModel
from ..Neuron.Neuron import NeuronGroup
from ..Network.Assembly import Assembly
import numpy as np
import scipy.sparse as sp
import torch


class Basic_synapse(SynapseModel):
        """
        Basic synapse
        Compute Isyn
        """
        def __init__(self, conn, **kwargs):
            super(Basic_synapse, self).__init__()

            if conn.link_type == 'conv':
                if conn.maxpool_on:
                    self._syn_operations.append([conn.post_var_name+'[post]', 'conv_max_pool2d', conn.pre_var_name+'[input]', 'weight[link]', 'maxpool_kernel_size[pre]',
                                'stride[pre]', 'padding[pre]', 'dilation[pre]', 'groups[pre]'])
                else:
                    self._syn_operations.append([conn.post_var_name+'[post]', 'conv_2d', conn.pre_var_name+'[input][updated]', 'weight[link]', 'stride[pre]', 'padding[pre]', 'dilation[pre]',
                                'groups[pre]'])
            else:
                if conn.is_sparse:
                    self._syn_operations.append([conn.post_var_name+'[post]', 'sparse_mat_mult_weight', 'weight[link]', conn.pre_var_name+'[input]'])
                elif conn.max_delay > 0:
                    self._syn_operations.append([conn.post_var_name+'[post]', 'mult_sum_weight', conn.pre_var_name+'[input]', 'weight[link]'])
                else:
                    self._syn_operations.append([conn.post_var_name+'[post]', 'mat_mult_weight', conn.pre_var_name+'[input][updated]', 'weight[link]'])

SynapseModel.register('basic_synapse', Basic_synapse)


class DirectPass_synapse(SynapseModel):
    """
    DirectPass synapse
    target_name = input_name
    """

    def __init__(self, conn, **kwargs):
        super(DirectPass_synapse, self).__init__()
        self._syn_operations.append([conn.post_var_name + '[post]', 'equal', conn.pre_var_name + '[input]'])


SynapseModel.register('directpass_synapse', DirectPass_synapse)


class Electrical_synapse(SynapseModel):
    """
    Electrical synapse
    Iele = weight *（V(l-1) - V(l)）
    """
    def __init__(self, conn, **kwargs):
        super(Electrical_synapse, self).__init__()
        # V_post = conn.get_post_name(conn.post_assembly, 'V')
        # V_pre = conn.get_pre_name(conn.pre_assembly, 'V')
        # Vtemp_post = conn.get_link_name(conn.pre_assembly, conn.post_assembly, 'Vtemp')
        # I_post = conn.get_post_name(conn.post_assembly, 'I_ele')
        # weight = conn.get_link_name(conn.pre_assembly, conn.post_assembly, 'weight')
        # Vtemp_pre = conn.get_link_name(conn.post_assembly, conn.pre_assembly, 'Vtemp')
        # I_pre = conn.get_pre_name(conn.pre_assembly, 'I_ele')
        #
        # self._syn_variables[Vtemp_post] = 0.0
        # self._syn_variables[I_post] = 0.0
        # self._syn_variables[Vtemp_pre] = 0.0
        # self._syn_variables[I_pre] = 0.0
        # self._syn_operations.append([Vtemp_post, 'minus', V_pre, V_post])
        # self._syn_operations.append([I_post, 'var_mult', weight, Vtemp_post + '[updated]'])
        # self._syn_operations.append([Vtemp_pre, 'minus', V_post, V_pre])
        # self._syn_operations.append([I_pre, 'var_mult', weight, Vtemp_pre + '[updated]'])

        # self._syn_variables['Vprepost'] = np.zeros([1, conn.pre_num, conn.post_num])
        assert isinstance(conn.pre_assembly, NeuronGroup) and isinstance(conn.post_assembly, NeuronGroup), f"Electrical synapses exist in connections in which the presynaptic and postsynaptic objects are neurongroups"

        self._syn_variables['Isyn[post]'] = np.zeros([1, conn.post_num])
        self._syn_variables['Isyn[pre]'] = np.zeros([1, conn.pre_num])
        self._syn_constant_variables['unsequence_dim'] = 0
        self._syn_constant_variables['permute_dim'] = [1, 2, 0]
        self._syn_constant_variables['Vpre_permute_dim'] = [2, 1, 0]
        self._syn_constant_variables['post_sum_dim'] = 2
        self._syn_constant_variables['pre_sum_dim'] = 1

        # unsequence_dim_name =
        self._syn_operations.append(['Vpre', 'unsqueeze', 'V[pre]', 'unsequence_dim'])
        self._syn_operations.append(['Vpre_temp', 'permute', 'Vpre', 'Vpre_permute_dim'])
        self._syn_operations.append(['Vpost_temp', 'unsqueeze', 'V[post]', 'unsequence_dim'])
        # [pre_num, batch_size, post_num] [pre_num, batch_size, 1] [1, batch_size, post_num]
        self._syn_operations.append(['Vprepost', 'minus', 'Vpre_temp', 'Vpost_temp'])
        # [batch_size, post_num, pre_num]
        self._syn_operations.append(['Vprepost_temp', 'permute', 'Vprepost', 'permute_dim'])
        self._syn_operations.append(['I_post_temp', 'var_mult', 'Vprepost_temp', 'weight[link]'])
        # [batch_size, post_num]
        self._syn_operations.append(['Isyn[post]', 'reduce_sum', 'I_post_temp', 'post_sum_dim'])

        # [pre_num, batch_size, post_num]  [1, batch_size, post_num] [pre_num, batch_size, 1]
        self._syn_operations.append(['Vpostpre', 'minus', 'Vpost_temp', 'Vpre_temp'])
        # [batch_size, post_num, pre_num]
        self._syn_operations.append(['Vpostpre_temp', 'permute', 'Vpostpre', 'permute_dim'])
        self._syn_operations.append(['I_pre_temp', 'var_mult', 'Vpostpre_temp', 'weight[link]'])
        # [batch_size, pre_num]
        self._syn_operations.append(['Isyn[pre]', 'reduce_sum', 'I_pre_temp', 'pre_sum_dim'])


SynapseModel.register('electrical_synapse', Electrical_synapse)


class FullConnection(Connection):

    '''
    each neuron in the first layer is connected to each neuron in the second layer.

    Args:
        pre_assembly(Assembly): The assembly which needs to be connected
        post_assembly(Assembly): The assembly which needs to connect the pre_assembly
        link_type(str): full
    '''

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'), policies=[],
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):

        super(FullConnection, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                             link_type=link_type, max_delay=max_delay,
                                             sparse_with_mask=sparse_with_mask,
                                             pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        weight = kwargs.get('weight', None)
        self.w_std = kwargs.get('w_std', 0.05)
        self.w_mean = kwargs.get('w_mean', 0.005)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', True)
        self.is_sparse = kwargs.get('is_sparse', False)
        self._variables = dict()

        if weight is None:
            # Connection weight
            self.weight = self.w_std*np.random.randn(*self.shape) + self.w_mean
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight

        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass

Connection.register('full', FullConnection)
Connection.register('full_connection',FullConnection)


class one_to_one_sparse(Connection):
    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(one_to_one_sparse, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                                link_type=link_type, max_delay=max_delay,
                                                sparse_with_mask=sparse_with_mask,
                                                pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        try:
            assert self.pre_num == self.post_num
        except AssertionError:
            raise ValueError(
                'One to One connection must be defined in two groups with the same size, but the pre_num %s is not equal to the post_num %s.' % (
                self.pre_num, self.post_num))
        weight = kwargs.get('weight', None)
        self.w_mean = kwargs.get('w_mean', 0.05)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', False)
        self.is_sparse = kwargs.get('is_sparse', True)
        self._variables = dict()

        if weight is None:
            # Connection weight
            self.weight = self.w_mean * np.eye(*self.shape)
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight
        self._variables['weight[link]'] = self.weight
        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass

Connection.register('one_to_one_sparse', one_to_one_sparse)


class one_to_one_mask(Connection):
    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=True, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(one_to_one_mask, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                              link_type=link_type, max_delay=max_delay,
                                              sparse_with_mask=sparse_with_mask,
                                              pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        try:
            assert self.pre_num == self.post_num
        except AssertionError:
            raise ValueError(
                'One to One connection must be defined in two groups with the same size, but the pre_num %s is not equal to the post_num %s.' % (
                self.pre_num, self.post_num))
        weight = kwargs.get('weight', None)
        self.w_mean = kwargs.get('w_mean', 0.05)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', True)
        self.is_sparse = kwargs.get('is_sparse', False)
        self._variables = dict()

        if weight is None:
            # Connection weight
            self.weight = self.w_mean * np.eye(*self.shape)
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass
Connection.register('one_to_one', one_to_one_mask)

class conv_connect(Connection):

    '''
    do the convolution connection.

    Args:
        pre_assembly(Assembly): the assembly which needs to be connected
        post_assembly(Assembly): the assembly which needs to connect the pre_assembly
        link_type(str): Conv
    Methods:
        unit_connect: define the basic connection information and add them to the connection_information.
        condition_check: check whether the pre_group.type is equal to the post_group.type, only if they are equal, return flag=Ture.

    '''

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(conv_connect, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                           link_type=link_type, max_delay=max_delay,
                                           sparse_with_mask=sparse_with_mask,
                                           pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        self.out_channels = kwargs.get('out_channels', 4)
        self.in_channels = kwargs.get('in_channels', 1)
        self.kernel_size = kwargs.get('kernel_size', (3, 3))
        self.maxpool_on = kwargs.get('maxpool_on', True)
        self.maxpool_kernel_size = kwargs.get('maxpool_kernel_size', (2, 2))
        self.w_std = kwargs.get('w_std', 0.05)
        self.w_mean = kwargs.get('w_mean', 0.05)

        weight = kwargs.get('weight', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', True)
        self.is_sparse = kwargs.get('is_sparse', False)
        self.mask = kwargs.get('mask', None)
        self.stride = kwargs.get('stride', 1)
        self.padding = kwargs.get('padding', 0)
        self.dilation = kwargs.get('dilation', 1)
        self.groups = kwargs.get('groups', 1)

        self._variables = dict()
        self._variables['stride[pre]'] = self.stride
        self._variables['padding[pre]'] = self.padding
        self._variables['dilation[pre]'] = self.dilation
        self._variables['groups[pre]'] = self.groups
        self._variables['maxpool_kernel_size[pre]'] = self.maxpool_kernel_size

        '''
        set the basic parameters, for example: link_length, connection weight, connection shape, the name for backend variables, the backend variable,the backend basic operation.

        Args:
            pre_group(Groups): the neuron group which need to be connected in the pre_assembly.
            post_group(Groups): the neuron group which need to be connected with the pre_group neuron.

        '''
        self.shape = (self.out_channels, self.in_channels, self.kernel_size[0], self.kernel_size[1])
        if weight is None:
            # Connection weight
            self.weight = self.w_std * np.random.randn(*self.shape) + self.w_mean
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight

        Hin = self.pre_assembly.shape[-2]
        Win = self.pre_assembly.shape[-1]

        if self.maxpool_on:  # 池化

            Hin = int(Hin / self.maxpool_kernel_size[0])
            Win = int(Win / self.maxpool_kernel_size[1])

        Ho = int((Hin + 2 * self.padding - self.kernel_size[
            0]) / self.stride + 1)  # Ho = (Hin + 2 * padding[0] - kernel_size[0]) / stride[0] + 1
        Wo = int((Win + 2 * self.padding - self.kernel_size[
            1]) / self.stride + 1)  # Wo = (Win + 2 * padding[0] - kernel_size[1]) / stride[0] + 1

        post_num = int(Ho * Wo * self.out_channels)

        if self.post_assembly.num == None:
            self.post_assembly.num = post_num
            self.post_assembly.shape = (self.out_channels, Ho, Wo)

        if self.post_assembly.num != None:
            if self.post_assembly.num != post_num:
                raise ValueError(
                    "The post_group num is not equal to the output num, cannot achieve the conv connection, "
                    "the output num is %d * %d * %d " % (self.out_channels, Ho, Wo))
            else:
                self.post_assembly.shape = (self.out_channels, Ho, Wo)


    def condition_check(self, pre_group, post_group):
        '''
        check whether the pre_group.type is equal to the post_group.type, only if they are equal, return flag=Ture.

        Args:
            pre_group(Groups): the neuron group which need to be connected in the pre_assembly.
            post_group(Groups): the neuron group which need to connect the pre_group in the post_assembly.

        Returns: flag

        '''

        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
Connection.register('conv', conv_connect)
Connection.register('conv_connection', conv_connect)


class sparse_connect_sparse(Connection):

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(sparse_connect_sparse, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                                    link_type=link_type, max_delay=max_delay,
                                                    sparse_with_mask=sparse_with_mask,
                                                    pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        weight = kwargs.get('weight', None)
        self.w_std = kwargs.get('w_std', 0.05)
        self.density = kwargs.get('density', 0.1)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', False)
        self.is_sparse = kwargs.get('is_sparse', True)
        self._variables = dict()

        if weight is None:
            # Connection weight
            sparse_matrix = self.w_std * sp.rand(*self.shape, density=self.density, format='csr')
            self.weight = sparse_matrix.toarray()
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight

        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass
Connection.register('sparse_sparse', sparse_connect_sparse)
Connection.register('sparse_connection_sparse', sparse_connect_sparse)


class sparse_connect_mask(Connection):

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=True, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(sparse_connect_mask, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                                  link_type=link_type, max_delay=max_delay,
                                                  sparse_with_mask=sparse_with_mask,
                                                  pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        weight = kwargs.get('weight', None)
        self.w_std = kwargs.get('w_std', 0.05)
        self.w_mean = kwargs.get('w_mean', 0.005)
        self.density = kwargs.get('density', 0.1)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', True)
        self.is_sparse = kwargs.get('is_sparse', False)
        self._variables = dict()

        if weight is None:
            # Connection weight
            sparse_matrix = self.w_std * sp.rand(*self.shape, density=self.density, format='csr')
            self.weight = sparse_matrix.toarray()
            self.weight[self.weight.nonzero()] = self.weight[self.weight.nonzero()] + self.w_mean
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight

        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass
Connection.register('sparse', sparse_connect_mask)
Connection.register('sparse_connection', sparse_connect_mask)


class random_connect_sparse(Connection):

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(random_connect_sparse, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                                    link_type=link_type, max_delay=max_delay,
                                                    sparse_with_mask=sparse_with_mask,
                                                    pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        weight = kwargs.get('weight', None)
        self.probability = kwargs.get('probability', 0.1)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', False)
        self.is_sparse = kwargs.get('is_sparse', True)
        self._variables = dict()

        if weight is None:
            # Link_parameters
            prob_weight = np.random.rand(*self.shape)
            diag_index = np.arange(min([self.pre_num, self.post_num]))
            prob_weight[diag_index, diag_index] = 1
            index = (prob_weight < self.probability)
            # Connection weight
            self.weight = np.zeros(self.shape)
            self.weight[index] = prob_weight[index]
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight
        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass
Connection.register('random_connection_sparse', random_connect_sparse)



class random_connect_mask(Connection):

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv', '...'),
                 max_delay=0, sparse_with_mask=True, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(random_connect_mask, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                                  link_type=link_type, max_delay=max_delay,
                                                  sparse_with_mask=sparse_with_mask,
                                                  pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        weight = kwargs.get('weight', None)
        self.probability = kwargs.get('probability', 0.1)
        self.w_max = kwargs.get('w_max', None)
        self.w_min = kwargs.get('w_min', None)
        self.param_init = kwargs.get('param_init', None)
        self.is_parameter = kwargs.get('is_parameter', True)
        self.is_sparse = kwargs.get('is_sparse', False)
        self._variables = dict()

        if weight is None:
            # Link_parameters
            prob_weight = np.random.rand(*self.shape)
            diag_index = np.arange(min([self.pre_num, self.post_num]))
            prob_weight[diag_index, diag_index] = 1
            index = (prob_weight < self.probability)
            # Connection weight
            self.weight = np.zeros(self.shape)
            self.weight[index] = prob_weight[index]
        else:
            assert (weight.shape == self.shape), f"The size of the given weight {weight.shape} does not correspond to the size of synaptic matrix {self.shape} "
            self.weight = weight

        self._variables['weight[link]'] = self.weight
        pass

    def condition_check(self, pre_group, post_group):
        flag = False
        pre_type = pre_group.type
        post_type = post_group.type
        if pre_type == post_type:
            flag = True
        return flag
        pass
Connection.register('random', random_connect_mask)
Connection.register('random_connection', random_connect_mask)


class NullConnection(Connection):

    '''
    each neuron in the first layer is connected to each neuron in the second layer.

    Args:
        pre_assembly(Assembly): The assembly which needs to be connected
        post_assembly(Assembly): The assembly which needs to connect the pre_assembly
        link_type(str): full

    Methods:
        unit_connect: define the basic connection information and add them to the connection_information.
        condition_check: check whether the pre_group.type is equal to the post_group.type, only if they are equal, return flag=Ture.

    '''

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv','...'), policies=[],
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):

        super(NullConnection, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name,
                                             link_type=link_type, policies=policies, max_delay=max_delay,
                                             sparse_with_mask=sparse_with_mask,
                                             pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        self._variables = dict()

    # def unit_connect(self, pre_group, post_group):
    #     # The number of neurons in neuron group
    #     pre_num = pre_group.num
    #     post_num = post_group.num
    #     link_num = pre_num * post_num
    #     try:
    #         assert pre_num == post_num
    #     except AssertionError:
    #         raise ValueError('DirectPass must be defined in two groups with the same size, but the pre_num %s is not equal to the post_num %s.' % (pre_num, post_num))
    #
    #     # The name for backend variables
    #     input_name = self.get_input_name(pre_group, post_group)
    #     target_name = self.get_post_name(post_group, self.post_var_name)
    #
    #     # The backend basic operation
    #     var_code = None
    #     if self.max_delay > 0:
    #         op_code = [target_name, 'equal', input_name]
    #     else:
    #         op_code = [target_name, 'equal', input_name]

        pass

Connection.register('null', NullConnection)

class DistDepd_connect(Connection):

    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse', 'conv','...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):

        super(DistDepd_connect, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name, link_type=link_type,
                                             max_delay=max_delay, sparse_with_mask=sparse_with_mask,
                                             pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
        self.distance_weight_function = kwargs.get('distance_weight_function', None)
        self.zero_self = kwargs.get('zero_self', False)
        if self.distance_weight_function is None:
            self.distance_weight_function = self.default_dist_weight_function
        self.dist_function = kwargs.get('dist_function', 'euclidean')
        if self.dist_function == 'euclidean':
            self.dist_function = self.euclidean_dist_function
        elif self.dist_function == 'circular':
            self.dist_function = self.circular_dist_function

        self.dist_a = kwargs.get('dist_a', 0.2)
        self.dist_b = kwargs.get('dist_b', 0.4)
        self.w_amp = kwargs.get('w_amp', -0.1)
        self.pos_range = kwargs.get('pos_range', 1.0)

    def unit_connect(self, pre_group, post_group):
        # The number of neurons in neuron group
        pre_num = pre_group.num
        post_num = post_group.num
        assert len(pre_group.position) > 0
        assert len(post_group.position) > 0
        link_num = pre_num * post_num
        shape = (post_num, pre_num)
        weight = np.zeros(shape)
        post_pos = np.expand_dims(post_group.position,  axis=1)
        pre_pos = np.expand_dims(pre_group.position, axis=0)
        weight = self.distance_weight_function(self.dist_function(pre_pos, post_pos))
        # from matplotlib import pyplot as plt
        # plt.imshow(weight)
        # plt.show()

        # The name for backend variables
        input_name = self.get_input_name(pre_group, post_group)
        weight_name = self.get_weight_name(pre_group, post_group)
        target_name = self.get_target_name(post_group)

        # The backend variable
        var_code = (weight_name, shape, weight, True, False) # (var_name, shape, value, is_parameter, is_sparse, init)
        op_code = [target_name, 'mat_mult', input_name, weight_name]
        connection_information = (pre_group, post_group, link_num, var_code, op_code)
        self.unit_connections.append(connection_information)

    def circular_dist_function(self, pre_pos, post_pos):
        if not isinstance(pre_pos, torch.Tensor):
            pre_pos = torch.tensor(pre_pos)
        if not  isinstance(post_pos, torch.Tensor):
            post_pos = torch.tensor(post_pos)

        z = torch.maximum(pre_pos, post_pos)
        k = torch.minimum(pre_pos, post_pos)
        dist = torch.minimum(z - k, self.pos_range + k - z)
        dist = torch.norm(dist, p=2, dim=-1)
        return dist

    def euclidean_dist_function(self, pre_pos, post_pos):
        if isinstance(pre_pos, torch.Tensor) and isinstance(post_pos, torch.Tensor):
            diff = pre_pos - post_pos
        else:
            diff = torch.tensor(pre_pos-post_pos)
        dist = torch.norm(diff, p=2, dim=-1)
        return dist

    def default_dist_weight_function(self, dist):
        weights = self.w_amp * (torch.exp(-dist / self.dist_a)/self.dist_a - 0.5*torch.exp(-dist / self.dist_b)/self.dist_b)
        if self.zero_self:
            weights = weights * (dist!=0).float()
        # import matplotlib.pyplot as plt
        # plt.imshow(weights, aspect='auto')
        # plt.show()
        return weights
Connection.register('dist_depd', DistDepd_connect)


class reconnect(Connection):
    def __init__(self, pre_assembly, post_assembly, name=None, link_type=('full', 'sparse_connect', 'conv', '...'),
                 max_delay=0, sparse_with_mask=False, pre_var_name='O', post_var_name='Isyn', **kwargs):
        super(reconnect, self).__init__(pre_assembly=pre_assembly, post_assembly=post_assembly, name=name, link_type=link_type,
                                             max_delay=max_delay, sparse_with_mask=sparse_with_mask, pre_var_name=pre_var_name, post_var_name=post_var_name, **kwargs)
    def unit_connect(self, pre_group, post_group):
        pass

    def condition_check(self, pre_group, post_group):
        pass