import torch.nn as nn


class BidirectionalLSTM(nn.Module):

    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        super(BidirectionalLSTM, self).__init__()
        self.rnn = nn.LSTM(input_size,
                           hidden_size,
                           bidirectional=True,
                           batch_first=True)
        self.linear = nn.Linear(hidden_size * 2, output_size)

    def forward(self, x):
        """
        x : visual feature [batch_size x T=24 x input_size=512]
        output : contextual feature [batch_size x T x output_size]
        """
        self.rnn.flatten_parameters()
        recurrent, _ = self.rnn(
            x
        )  # batch_size x T x input_size -> batch_size x T x (2*hidden_size)
        output = self.linear(recurrent)  # batch_size x T x output_size
        return output
