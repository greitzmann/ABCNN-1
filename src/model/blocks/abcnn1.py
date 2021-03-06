# coding=utf-8

import torch
import torch.nn as nn

from model.pooling.allap import AllAP

class ABCNN1Block(nn.Module):
    """ Implements a single ABCNN-1 Block as described in this paper: 

        http://www.aclweb.org/anthology/Q16-1019
    """
    
    def __init__(self, attn, conv, pool, dropout_rate=0.5):
        """ Initializes the ABCNN-1 Block. 

            Args:
                attn: ABCNN1Attention Module
                    The attention layer for the ABCNN-1 Block.
                conv: Convolution Module
                    The Convolutional layer for the ABCNN-1 Block.
                pool: WidthAP Module
                    The w-ap Average Pooling layer for the ABCNN-1 Block.
        """
        super().__init__()
        self.conv = conv
        self.attn = attn
        self.pool = pool
        self.ap = AllAP()
        self.dropout = nn.Dropout2d(p=dropout_rate)
    
    def forward(self, x1, x2):
        """ Computes the forward pass over the ABCNN-1 Block.

            Args:
                x1, x2: torch.Tensors of shape (batch_size, 1, max_length, input_size)
                    The inputs to the ABCNN-1 Block.

            Returns:
                w1, w2: torch.Tensors of shape (batch_size, 1, max_length, output_size)
                    The outputs of the w-ap Average Pooling layer. These are
                    passed to the next Block.
                a1, a2: torch.Tensors of shape (batch_size, output_size)
                    The outputs of the all-ap Average Pooling layer. These are
                    optionally passed to the output layer.
        """
        o1, o2 = self.attn(x1, x2) # shapes (batch_size, 2, max_length, input_size)
        c1, c2 = self.conv(o1), self.conv(o2) # shapes (batch_size, 1, max_length + width - 1, output_size)
        w1, w2 = self.pool(c1), self.pool(c2) # shapes (batch_size, 1, max_length, output_size)
        w1, w2 = self.dropout(w1), self.dropout(w2)
        a1, a2 = self.ap(c1), self.ap(c2) # shapes (batch_size, output_size)
        return w1, w2, a1, a2
