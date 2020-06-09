# Copyright 2020 Xilinx Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for doing IO on XGraph objects


"""

import os
import json
import h5py
import logging
import numpy as np

from .json_io import XGraphJSONEncoder
from ..xgraph_factory import XGraphFactory
from ..layer import xlayer

logger = logging.getLogger('pyxir')


class XGraphIO(object):

    """

    TODO Handle 'Partition' layers
    """

    xgraph_factory = XGraphFactory()

    @classmethod
    def save(cls, xgraph, filename):
        # type: (XGraph, str) -> None
        """
        Save this xgraph to disk. The network graph information is written to
        json and the network paraemeters are written to an h5 file
        Arguments
        ---------
        filename: str
            the name of the files storing the graph inormation and network
            parameters the graph information is stored in `filename`.json
            the network paraemeters are stored in `filename`.h5
        """
        h5f = h5py.File(filename + '.h5', 'w')

        # Save graph info
        d = {
            'nodes': [],
            'name': xgraph.get_name()
        }

        for X in xgraph.get_layers():

            if X.type[0] == 'Partition':
                raise NotImplementedError("Saving of 'Partition' layers"
                                          " is not supported at the moment")

            # logger.debug("Name: {}, type: {}".format(X.name, X.type))
            if X.type and \
                    ('Convolution' in X.type or 'Dense' in X.type):
                h5f.create_dataset(X.name + '_weights', data=X.data.weights)
                h5f.create_dataset(X.name + '_biases', data=X.data.biases)
                # X = X._replace(data='Retrieve data from h5py file')
            elif X.type and 'BatchNorm' in X.type:
                h5f.create_dataset(X.name + '_mu', data=X.data.mu)
                h5f.create_dataset(X.name + '_variance',
                                   data=X.data.sigma_square)
                h5f.create_dataset(X.name + '_gamma', data=X.data.gamma)
                h5f.create_dataset(X.name + '_beta', data=X.data.beta)
                # X = X._replace(data='Retrieve data from h5py file')
            elif X.type and 'Scale' in X.type:
                h5f.create_dataset(X.name + '_gamma', data=X.data.gamma)
                h5f.create_dataset(X.name + '_beta', data=X.data.beta)
                # X = X._replace(data='Retrieve data from h5py file')
            elif X.type and 'Eltwise' in X.type:
                if X.data != []:
                    logger.debug(X.name)
                    logger.debug(type(X.data))
                    h5f.create_dataset(X.name + '_beta', data=X.data[0])
                    # X = X._replace(data='Retrieve data from h5py file')
            elif X.type and 'BiasAdd' in X.type:
                if X.data != []:
                    logger.debug(X.name)
                    logger.debug(type(X.data))
                    h5f.create_dataset(X.name + '_beta', data=X.data[0])
                    # X = X._replace(data='Retrieve data from h5py file')
            elif X.type and 'Constant' in X.type:
                if X.data != []:
                    logger.debug(X.name)
                    logger.debug(type(X.data))
                    h5f.create_dataset(X.name + '_constant', data=X.data[0])
                    # X = X._replace(data='Retrieve data from h5py file')

            node_json = {
                'name': X.name,
                # 'shape': layer.get('shape'),
                # 'fillcolor': layer.get('fillcolor'),
                'LayerParameter': X.to_dict(data=False)
            }
            d['nodes'].append(node_json)

        with open(filename + '.json', 'w') as f:
            json.dump(d, f, cls=XGraphJSONEncoder, indent=4, sort_keys=True)

        h5f.close()

    @classmethod
    def load(cls, net_file, params_file):
        # type: (str, str) -> None
        """
        Load the graph network information and weighst from the json network
        file respectively h5 parameters file
        Arguments
        ---------
        net_file: str
            the path to the file containing the network graph information
        params_file: str
            the path to the file containing the network weights
        TODO
        """

        if not net_file.endswith('.json'):
            raise ValueError("Invalid network file type: {}, should be json"
                             .format(net_file.split('.')[-1]))
        if not params_file.endswith('.h5'):
            raise ValueError("Invalid parameters file type: {}, should be h5"
                             .format(params_file.split('.')[-1]))
        if not os.path.exists(net_file):
            raise ValueError("Provided network file does not exist: {}"
                             .format(net_file))
        if not os.path.exists(params_file):
            raise ValueError("Provided parameters file does not exist: {}"
                             .format(params_file))

        with open(net_file) as nf:
            net = json.load(nf)
        h5f = h5py.File(params_file, 'r')

        xlayers = []
        for node in net['nodes']:
            # pydot_attrs = copy.copy(pydot_tools.LAYER_STYLE_DEFAULT)
            # pydot_attrs['shape'] = node['shape']
            # pydot_attrs['fillcolor'] = node['fillcolor']

            X = xlayer.XLayer(**node['LayerParameter'])
            if X.type and \
                    ('Convolution' in X.type or 'Dense' in X.type):
                weights_key, biases_key = X.name + '_weights',\
                    X.name + '_biases'
                if weights_key not in h5f:
                    raise ValueError("Couldn't find required weights"
                                     " parameters in parameters file: {}"
                                     .format(params_file))
                if biases_key not in h5f:
                    raise ValueError("Couldn't find required biases parameters"
                                     " in parameters file: {}"
                                     .format(params_file))

                dset_weights = h5f[weights_key]
                weights = np.empty(dset_weights.shape, dtype=np.float32)
                dset_weights.read_direct(weights)

                dset_biases = h5f[biases_key]
                biases = np.empty(dset_biases.shape, dtype=np.float32)
                dset_biases.read_direct(biases)

                X.data = xlayer.ConvData(weights, biases)
            if X.type and ('BatchNorm' in X.type):
                mu_key, variance_key = X.name + '_mu', X.name + '_variance'
                gamma_key, beta_key = X.name + '_gamma', X.name + '_beta'
                if mu_key not in h5f:
                    raise ValueError("Couldn't find required batchnorm mean"
                                     " parameters in parameters file: {}"
                                     .format(params_file))
                if variance_key not in h5f:
                    raise ValueError("Couldn't find required batchnorm"
                                     " variance parameters in parameters file:"
                                     " {}".format(params_file))
                if gamma_key not in h5f:
                    raise ValueError("Couldn't find required batchnorm gamma"
                                     " parameters in parameters file: {}"
                                     .format(params_file))
                if beta_key not in h5f:
                    raise ValueError("Couldn't find required batchnorm beta"
                                     " parameters in parameters file: {}"
                                     .format(params_file))

                dset_mu = h5f[mu_key]
                mu = np.empty(dset_mu.shape, dtype=np.float32)
                dset_mu.read_direct(mu)

                dset_variance = h5f[variance_key]
                variance = np.empty(dset_variance.shape, dtype=np.float32)
                dset_variance.read_direct(variance)

                dset_gamma = h5f[gamma_key]
                gamma = np.empty(dset_gamma.shape, dtype=np.float32)
                dset_gamma.read_direct(gamma)

                dset_beta = h5f[beta_key]
                beta = np.empty(dset_beta.shape, dtype=np.float32)
                dset_beta.read_direct(beta)

                X.data = xlayer.BatchData(mu, variance, gamma, beta)
            if X.type and ('Scale' in X.type):
                gamma_key, beta_key = X.name + '_gamma', X.name + '_beta'
                if gamma_key not in h5f:
                    raise ValueError("Couldn't find required scale gamma"
                                     " parameters in parameters file: {}"
                                     .format(params_file))
                if beta_key not in h5f:
                    raise ValueError("Couldn't find required scale beta"
                                     " parameters in parameters file: {}"
                                     .format(params_file))

                dset_gamma = h5f[gamma_key]
                gamma = np.empty(dset_gamma.shape, dtype=np.float32)
                dset_gamma.read_direct(gamma)

                dset_beta = h5f[beta_key]
                beta = np.empty(dset_beta.shape, dtype=np.float32)
                dset_beta.read_direct(beta)

                X.data = xlayer.ScaleData(gamma, beta)
            if X.type and ('Eltwise' in X.type):
                beta_key = X.name + '_beta'
                if beta_key in h5f:
                    dset_beta = h5f[beta_key]
                    beta = np.empty(dset_beta.shape, dtype=np.float32)
                    dset_beta.read_direct(beta)

                    X = X.data = [beta]
            if X.type and ('BiasAdd' in X.type):
                beta_key = X.name + '_beta'
                if beta_key in h5f:
                    dset_beta = h5f[beta_key]
                    beta = np.empty(dset_beta.shape, dtype=np.float32)
                    dset_beta.read_direct(beta)

                    X.data = [beta]
            if X.type and ('Constant' in X.type):
                constant_key = X.name + '_constant'
                if constant_key in h5f:
                    dset_constant = h5f[constant_key]
                    constant = np.empty(dset_constant.shape, dtype=np.float32)
                    dset_constant.read_direct(constant)

                    X.data = [constant]

            xlayers.append(X)

        h5f.close()

        # TODO Graph is not necessarily completely the identical to the saved
        #   one e.g. colors
        xgraph = XGraphIO.xgraph_factory.build_from_xlayer(net=xlayers)

        return xgraph