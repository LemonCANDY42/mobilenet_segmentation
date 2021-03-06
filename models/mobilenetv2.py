"""MobileNet v2 models for Keras.
MobileNetV2 is a general architecture and can be used for multiple use cases.
Depending on the use case, it can use different input layer size and
different width factors. This allows different width models to reduce
the number of multiply-adds and thereby
reduce inference cost on mobile devices.
MobileNetV2 is very similar to the original MobileNet,
except that it uses inverted residual blocks with
bottlenecking features. It has a drastically lower
parameter count than the original MobileNet.
MobileNets support any input size greater
than 32 x 32, with larger image sizes
offering better performance.
The number of parameters and number of multiply-adds
can be modified by using the `alpha` parameter,
which increases/decreases the number of filters in each layer.
By altering the image size and `alpha` parameter,
all 22 models from the paper can be built, with ImageNet weights provided.
The paper demonstrates the performance of MobileNets using `alpha` values of
1.0 (also called 100 % MobileNet), 0.35, 0.5, 0.75, 1.0, 1.3, and 1.4
For each of these `alpha` values, weights for 5 different input image sizes
are provided (224, 192, 160, 128, and 96).
The following table describes the performance of
MobileNet on various input sizes:
------------------------------------------------------------------------
MACs stands for Multiply Adds
 Classification Checkpoint| MACs (M)   | Parameters (M)| Top 1 Accuracy| Top 5 Accuracy
--------------------------|------------|---------------|---------|----|-------------
| [mobilenet_v2_1.4_224]  | 582 | 6.06 |          75.0 | 92.5 |
| [mobilenet_v2_1.3_224]  | 509 | 5.34 |          74.4 | 92.1 |
| [mobilenet_v2_1.0_224]  | 300 | 3.47 |          71.8 | 91.0 |
| [mobilenet_v2_1.0_192]  | 221 | 3.47 |          70.7 | 90.1 |
| [mobilenet_v2_1.0_160]  | 154 | 3.47 |          68.8 | 89.0 |
| [mobilenet_v2_1.0_128]  | 99  | 3.47 |          65.3 | 86.9 |
| [mobilenet_v2_1.0_96]   | 56  | 3.47 |          60.3 | 83.2 |
| [mobilenet_v2_0.75_224] | 209 | 2.61 |          69.8 | 89.6 |
| [mobilenet_v2_0.75_192] | 153 | 2.61 |          68.7 | 88.9 |
| [mobilenet_v2_0.75_160] | 107 | 2.61 |          66.4 | 87.3 |
| [mobilenet_v2_0.75_128] | 69  | 2.61 |          63.2 | 85.3 |
| [mobilenet_v2_0.75_96]  | 39  | 2.61 |          58.8 | 81.6 |
| [mobilenet_v2_0.5_224]  | 97  | 1.95 |          65.4 | 86.4 |
| [mobilenet_v2_0.5_192]  | 71  | 1.95 |          63.9 | 85.4 |
| [mobilenet_v2_0.5_160]  | 50  | 1.95 |          61.0 | 83.2 |
| [mobilenet_v2_0.5_128]  | 32  | 1.95 |          57.7 | 80.8 |
| [mobilenet_v2_0.5_96]   | 18  | 1.95 |          51.2 | 75.8 |
| [mobilenet_v2_0.35_224] | 59  | 1.66 |          60.3 | 82.9 |
| [mobilenet_v2_0.35_192] | 43  | 1.66 |          58.2 | 81.2 |
| [mobilenet_v2_0.35_160] | 30  | 1.66 |          55.7 | 79.1 |
| [mobilenet_v2_0.35_128] | 20  | 1.66 |          50.8 | 75.0 |
| [mobilenet_v2_0.35_96]  | 11  | 1.66 |          45.5 | 70.4 |
The weights for all 16 models are obtained and translated from the Tensorflow checkpoints
from TensorFlow checkpoints found at
https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/README.md
# Reference
This file contains building code for MobileNetV2, based on
[MobileNetV2: Inverted Residuals and Linear Bottlenecks](https://arxiv.org/abs/1801.04381)
Tests comparing this model to the existing Tensorflow model can be
found at [mobilenet_v2_keras](https://github.com/JonathanCMitchell/mobilenet_v2_keras)
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import warnings
import h5py
import numpy as np

from keras.models import Model
from keras.layers import Input
from keras.layers import Activation
from keras.layers import Dropout
from keras.layers import Reshape
from keras.layers import BatchNormalization
from keras.layers import Conv2D
from keras.layers import DepthwiseConv2D
from keras.layers import GlobalAveragePooling2D
from keras.layers import Add
from keras.layers import Flatten
from keras.layers import Dense
from keras.layers import LeakyReLU
from keras import initializers
from keras import regularizers
from keras import constraints
from keras.utils import conv_utils
from keras.utils.data_utils import get_file
from keras.engine import get_source_inputs
from keras import backend as K
import tensorflow as tf

# TODO Change path to v1.1
BASE_WEIGHT_PATH = 'https://github.com/JonathanCMitchell/mobilenet_v2_keras/releases/download/v1.1/'


def relu6(x):
    return K.relu(x, max_value=6)


def preprocess_input(x):
    """Preprocesses a numpy array encoding a batch of images.
    This function applies the "Inception" preprocessing which converts
    the RGB values from [0, 255] to [-1, 1]. Note that this preprocessing
    function is different from `imagenet_utils.preprocess_input()`.
    # Arguments
        x: a 4D numpy array consists of RGB values within [0, 255].
    # Returns
        Preprocessed array.
    """
    x /= 128.
    x -= 1.
    return x.astype(np.float32)


# This function is taken from the original tf repo.
# It ensures that all layers have a channel number that is divisible by 8
# It can be seen here:
# https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/mobilenet.py


def _make_divisible(v, divisor, min_value=None):
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    # Make sure that round down does not go down by more than 10%.
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


class MobilenetV2_base(object):
    def __init__(self):
        self.model = None
        print('\nBuilding MobileNet_V2...')

    def build_model(self, input_tensor, output_stride=8, return_model=False, alpha=1.0):

        if K.image_data_format() == 'channels_last':
            bn_axis = 3
        else:
            bn_axis = 1

        if input_tensor is None:
            input_tensor = Input(shape=[None, None, 3], name='input')

        input_tensor_source = get_source_inputs(input_tensor)[0]

        if alpha not in [0.35, 0.50, 0.75, 1.0, 1.3, 1.4]:
            raise ValueError('If imagenet weights are being loaded, '
                             'alpha can be one of'
                             '`0.25`, `0.50`, `0.75` or `1.0` only.')

        first_block_filters = _make_divisible(32 * alpha, 8)
        x = Conv2D(first_block_filters,
                   kernel_size=3,
                   strides=(2, 2), padding='same',
                   use_bias=False, name='mn_Conv1')(input_tensor)
        x = BatchNormalization(epsilon=1e-3, momentum=0.999, name='mn_bn_Conv1')(x)
        x = Activation(tf.nn.relu6, name='mn_Conv1_relu')(x)

        current_stride = 2
        stride_left = output_stride / current_stride

        self.conv0 = _inverted_res_block(x, filters=16, alpha=alpha, stride=1,
                                expansion=1, block_id=0)

        if stride_left > 1:
            strides = (2, 2)
            dilation = 1
            stride_left /= 2
        else:
            strides = (1, 1)
            dilation = 2

        self.conv1 = _inverted_res_block(self.conv0, filters=24, alpha=alpha, stride=strides, dilation=dilation,
                                expansion=6, block_id=1, use_shortcuts=True)
        self.conv2 = _inverted_res_block(self.conv1, filters=24, alpha=alpha, stride=1,
                                expansion=6, block_id=2)

        if stride_left > 1:
            strides = (2, 2)
            dilation = 1
            stride_left /= 2
        else:
            strides = (1, 1)
            dilation = 2

        self.conv3 = _inverted_res_block(self.conv2, filters=32, alpha=alpha, stride=strides, dilation=dilation,expansion=6, block_id=3, use_shortcuts=True)
        self.conv4 = _inverted_res_block(self.conv3, filters=32, alpha=alpha, stride=1,expansion=6, block_id=4, use_shortcuts=True)
        self.conv5 = _inverted_res_block(self.conv4, filters=32, alpha=alpha, stride=1,expansion=6, block_id=5, use_shortcuts=True)

        if stride_left > 1:
            strides = (2, 2)
            dilation = 1
            stride_left /= 2
        else:
            strides = (1, 1)
            dilation = 2

        self.conv6 = _inverted_res_block(self.conv5, filters=64, alpha=alpha, stride=strides, dilation=dilation,
                                expansion=6, block_id=6, use_shortcuts=True)
        self.conv7 = _inverted_res_block(self.conv6, filters=64, alpha=alpha, stride=1,
                                expansion=6, block_id=7, use_shortcuts=True)
        self.conv8 = _inverted_res_block(self.conv7, filters=64, alpha=alpha, stride=1,
                                expansion=6, block_id=8, use_shortcuts=True)
        self.conv9 = _inverted_res_block(self.conv8, filters=64, alpha=alpha, stride=1,
                                expansion=6, block_id=9, use_shortcuts=True)

        self.conv10 = _inverted_res_block(self.conv9, filters=96, alpha=alpha, stride=1,
                                expansion=6, block_id=10, use_shortcuts=True)
        self.conv11 = _inverted_res_block(self.conv10, filters=96, alpha=alpha, stride=1,
                                expansion=6, block_id=11, use_shortcuts=True)
        self.conv12 = _inverted_res_block(self.conv11, filters=96, alpha=alpha, stride=1,
                                expansion=6, block_id=12, use_shortcuts=True)

        if stride_left > 1:
            strides = (2, 2)
            dilation = 1
            stride_left /= 2
        else:
            strides = (1, 1)
            dilation = 2

        self.conv13 = _inverted_res_block(self.conv12, filters=160, alpha=alpha, stride=strides, dilation=dilation,
                                expansion=6, block_id=13, use_shortcuts=True)
        self.conv14 = _inverted_res_block(self.conv13, filters=160, alpha=alpha, stride=1,
                                expansion=6, block_id=14, use_shortcuts=True)
        self.conv15 = _inverted_res_block(self.conv14, filters=160, alpha=alpha, stride=1,
                                expansion=6, block_id=15, use_shortcuts=True)

        self.conv16 = _inverted_res_block(self.conv15, filters=320, alpha=alpha, stride=1,
                                expansion=6, block_id=16, use_shortcuts=True)

        # no alpha applied to last conv as stated in the paper:
        # if the width multiplier is greater than 1 we
        # increase the number of output channels
        if alpha > 1.0:
            last_block_filters = _make_divisible(1280 * alpha, 8)
        else:
            last_block_filters = 1280

        x = Conv2D(last_block_filters,
                   kernel_size=1,
                   use_bias=False,
                   name='mn_Conv_1')(self.conv16)
        x = BatchNormalization(epsilon=1e-3, momentum=0.999, name='mn_Conv_1_bn')(x)
        x = Activation(tf.nn.relu6, name='mn_out_relu')(x)

        rows = 224

        # Create model.
        self.model = Model(input_tensor_source, x,
                      name='mobilenetv2_%0.2f_%s' % (alpha, rows))

        # load weights
        if K.image_data_format() == 'channels_first':
            raise ValueError('Weights for "channels_first" format '
                             'are not available.')

        model_name = 'mobilenet_v2_weights_tf_dim_ordering_tf_kernels_' + \
            str(alpha) + '_' + str(rows) + '_no_top' + '.h5'
        weigh_path = BASE_WEIGHT_PATH + model_name
        weights_path = get_file(model_name, weigh_path,
                                cache_subdir='models')
        print(f"Loading weights from {weights_path}")
        self.model.load_weights(weights_path)




def _inverted_res_block(inputs, expansion, stride, alpha, filters, block_id, dilation=1, use_shortcuts=False):
    in_channels = inputs._keras_shape[-1]
    pointwise_conv_filters = int(filters * alpha)
    pointwise_filters = _make_divisible(pointwise_conv_filters, 8)
    x = inputs
    prefix = 'mn_block_{}_'.format(block_id)

    if block_id:
        # Expand
        x = Conv2D(expansion * in_channels, kernel_size=1, padding='same',
                   use_bias=False, activation=None,
                   name=prefix + 'expand')(x)
        x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                               name=prefix + 'expand_BN')(x)
        x = Activation(tf.nn.relu6, name=prefix + 'expand_relu')(x)
    else:
        prefix = 'mn_expanded_conv_'

    # Depthwise
    x = DepthwiseConv2D(kernel_size=3, strides=stride, dilation_rate=dilation, activation=None,
                        use_bias=False, padding='same',
                        name=prefix + 'depthwise')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'depthwise_BN')(x)

    x = Activation(tf.nn.relu6, name=prefix + 'depthwise_relu')(x)

    # Project
    x = Conv2D(pointwise_filters,
               kernel_size=1, padding='same', use_bias=False, activation=None,
               name=prefix + 'project')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'project_BN')(x)

    if in_channels == pointwise_filters and stride == 1 and dilation == 1:
        return Add(name=prefix + 'add')([inputs, x])
#     elif use_shortcuts:
#         return shortcut(input=inputs, residual=x, block_id=block_id)

    return x

def __inverted_res_block(inputs, expansion, stride, alpha, filters, block_id, dilation=1, use_shortcuts=False):
    in_channels = inputs._keras_shape[-1]
    pointwise_conv_filters = int(filters * alpha)
    pointwise_filters = _make_divisible(pointwise_conv_filters, 8)
    x = inputs
    prefix = 'IRB_block_{}_'.format(block_id)

    if block_id:
        # Expand
        x = Conv2D(expansion * in_channels, kernel_size=1, padding='same',
                   use_bias=False, activation=None,
                   name=prefix + 'expand')(x)
        x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                               name=prefix + 'expand_BN')(x)
        x = Activation(tf.nn.relu6, name=prefix + 'expand_relu')(x)
    else:
        prefix = 'mn_expanded_conv_'

    # Depthwise
    x = DepthwiseConv2D(kernel_size=3, strides=stride, dilation_rate=dilation, activation=None,
                        use_bias=False, padding='same',
                        name=prefix + 'depthwise')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'depthwise_BN')(x)

    x = Activation(tf.nn.relu6, name=prefix + 'depthwise_relu')(x)

    # Project
    x = Conv2D(pointwise_filters,
               kernel_size=1, padding='same', use_bias=False, activation=None,
               name=prefix + 'project')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'project_BN')(x)

    if in_channels == pointwise_filters and stride == 1 and dilation == 1:
        return Add(name=prefix + 'add')([inputs, x])
#     elif use_shortcuts:
#         return shortcut(input=inputs, residual=x, block_id=block_id)

    return x




def shortcut(input, residual, block_id):
    input_shape = K.int_shape(input)
    residual_shape = K.int_shape(residual)
    stride_row = int(round(input_shape[1] / residual_shape[1]))
    stride_col = int(round(input_shape[2] / residual_shape[2]))
    channels_equal = (input_shape[3] == residual_shape[3])

    shortcut_connection = input
    if stride_col > 1 or stride_row > 1 or not channels_equal:
        shortcut_connection = Conv2D(filters=residual_shape[3],
                                     kernel_size=1, strides=(stride_row, stride_col),
                                     padding='valid', kernel_initializer='he_normal',
                                     name='shortcut_conv_' + str(block_id))(input)

    return Add(name='shortcut' + str(block_id))([shortcut_connection, residual])
