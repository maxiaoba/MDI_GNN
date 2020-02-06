import numpy as np
import torch
import matplotlib.pyplot as plt
import argparse
from utils import objectview

parser = argparse.ArgumentParser()
parser.add_argument('--uci_data', type=str, default='cancer')
parser.add_argument('--file', type=str, default='1')
args = parser.parse_args()

load_path = './Data/uci/'+args.uci_data+'/'+args.file+'/'

import joblib
result = joblib.load(load_path+'result.pkl')
result = objectview(result)
train_args = result.args
for key in train_args.__dict__.keys():
    print(key,': ',train_args.__dict__[key])

from plot_utils import plot_result
plot_result(result, load_path)

from uci import get_dataset
dataset = get_dataset(args.uci_data)

from gnn_model import GNNStack
model = GNNStack(dataset[0].num_node_features, train_args.node_dim,
                        train_args.edge_dim, train_args.edge_mode,
                        train_args.model_types, train_args.dropout)
model.load_state_dict(torch.load(load_path+'model.pt'))
model.eval()

from prediction_model import MLPNet
predict_model = MLPNet([train_args.node_dim, train_args.node_dim], 1, dropout=train_args.dropout)
predict_model.load_state_dict(torch.load(load_path+'predict_model.pt'))
predict_model.eval()

mask_defined = False
for data in dataset:
    if (not mask_defined) or (train_args.fix_train_mask == 0):
        from utils import get_train_mask
        train_mask = \
            get_train_mask(train_args.valid,(train_args.load_train_mask==1),load_path+'../',data)
    mask_defined = True
    
    known_mask = train_mask.clone().detach()
    known_mask[train_mask] = (torch.FloatTensor(torch.sum(train_mask).item()).uniform_() < train_args.known)
    # known mask is a mask that masks train mask

    # now concat all masks by it self
    double_train_mask = torch.cat((train_mask, train_mask),dim=0)
    double_known_mask = torch.cat((known_mask, known_mask),dim=0)
    
    x = data.x.clone().detach()
    edge_attr = data.edge_attr.clone().detach()
    edge_index = data.edge_index.clone().detach()
    from utils import mask_edge
    train_edge_index, train_edge_attr = mask_edge(edge_index,edge_attr,double_train_mask,(train_args.remove_unknown_edge == 1))
    known_edge_index, known_edge_attr = mask_edge(edge_index,edge_attr,double_known_mask,(train_args.remove_unknown_edge == 1))

    # xs, preds = model(x, train_edge_attr, train_edge_index, edge_index, return_x=True)
    xs = model(x, train_edge_attr, train_edge_index)
    predict_edge_index = edge_index[:,:int(edge_index.shape[1]/2)]
    preds = predict_model([xs[predict_edge_index[0],:],xs[predict_edge_index[1],:]])

    Os = {}
    for indx in range(128):
        i=edge_index[0,indx].detach().numpy()
        j=edge_index[1,indx].detach().numpy()
        true=train_edge_attr[indx].detach().numpy()
        pred=preds[indx].detach().numpy()
        xi=xs[i].detach().numpy()
        xj=xs[j].detach().numpy()
        if str(i) not in Os.keys():
            Os[str(i)] = {'true':[],'pred':[],'x_j':[]}
        Os[str(i)]['true'].append(true)
        Os[str(i)]['pred'].append(pred)
        Os[str(i)]['x_i'] = xi
        Os[str(i)]['x_j'] += list(xj)

import matplotlib.pyplot as plt
plt.figure()
plt.subplot(1,3,1)
for i in Os.keys():
    plt.plot(Os[str(i)]['pred'],label='o'+str(i)+'pred')
plt.legend()
plt.subplot(1,3,2)
for i in Os.keys():
    plt.plot(Os[str(i)]['x_i'],label='o'+str(i)+'xi')
    # print(Os[str(i)]['x_i'])
plt.legend()
plt.subplot(1,3,3)
for i in Os.keys():
    plt.plot(Os[str(i)]['x_j'],label='o'+str(i)+'xj')
    # print(Os[str(i)]['x_j'])
plt.legend()
plt.savefig(load_path+'check_embedding.png')

