import os
import copy
from typing import List
import numpy as np
import matplotlib.pyplot as plt

import torch
print(torch.__version__)
import torch.nn as nn
from torch.nn import BatchNorm1d
from torch.nn import functional as F
from torch_geometric.nn import CGConv, global_add_pool, global_mean_pool, global_max_pool, Sequential
from torch_geometric.loader import DataLoader
import torch_geometric.nn as pyg_nn
from torchmetrics.functional import mean_absolute_percentage_error

from matgraphdb.pyg_dataset import PolyhedraDataset
from trash.callbacks import EarlyStopping


class PolyhedronModel(nn.Module):
    """This is the main Polyhedron Model. 

    Parameters
    ----------
        n_node_features : int
        The number of node features
    n_edge_features : int
        The number of edge features, by default 2
    n_gc_layers : int, optional
        The number of graph convolution layers, by default 1
    global_pooling_method : str, optional
        The global pooling method to be used, by default 'add'
    """

    def __init__(self,
                n_node_features:int,
                n_edge_features:int, 
                n_gc_layers:int=1, 
                n_hidden_layers:List[int]=[5],
                global_pooling_method:str='add'):
        """This is the main Polyhedron Model. 

        Parameters
        ----------
         n_node_features : int
            The number of node features
        n_edge_features : int
            The number of edge features, by default 2
        n_gc_layers : int, optional
            The number of graph convolution layers, by default 1
        global_pooling_method : str, optional
            The global pooling method to be used, by default 'add'
        """
        super().__init__()

            
        layers=[]
        for i_gc_layer in range(n_gc_layers):
            if i_gc_layer == 0:
                vals = " x, edge_index, edge_attr -> x0 "
            else:
                vals = " x" + repr(i_gc_layer - 1) + " , edge_index, edge_attr -> x" + repr(i_gc_layer)

            layers.append((pyg_nn.CGConv(n_node_features, dim=n_edge_features,aggr = 'add'),vals))
        self.cg_conv_layers = Sequential(" x, edge_index, edge_attr " , layers)

        self.bn_node = pyg_nn.norm.BatchNorm(in_channels=n_node_features)
        self.bn_edge = pyg_nn.norm.BatchNorm(in_channels=n_edge_features)
        self.relu = nn.ReLU()
        self.sig = nn.Sigmoid()
        self.leaky_relu = torch.nn.LeakyReLU(negative_slope=0.01, inplace=False)

        self.point_net = pyg_nn.PointNetConv(add_self_loops =False)
        

        self.out_layer= nn.Linear( n_hidden_layers[-1],  1)
        

        if global_pooling_method == 'add':
            self.global_pooling_layer = global_add_pool
        elif global_pooling_method == 'mean':
            self.global_pooling_layer = global_mean_pool
        


    def forward(self, data_batch, targets=None):
        """The forward pass of of the network

        Parameters
        ----------
        x : pygeometic.Data
            The pygeometric data object
        targets : float, optional
            The target value to use to calculate the loss, by default None

        Returns
        -------
        _type_
            _description_
        """
        
        x, edge_index, edge_attr, pos = data_batch.x, data_batch.edge_index, data_batch.edge_attr, data_batch.pos
        batch = data_batch.batch

        # print(edge_index.shape)
        # print(x.shape)
        print(batch)

        # x_out = self.bn_node(x)
        # edge_out = self.bn_edge(edge_attr)

        x_out = x
        edge_out = edge_attr

        out = self.point_net(x, pos , edge_index)

        # Loss handling
        if targets is None:
            loss = None
            mape_loss = None
        else:
            loss_fn = torch.nn.MSELoss()
            mape_loss = mean_absolute_percentage_error(torch.squeeze(out, dim=1), targets)
            loss = loss_fn(torch.squeeze(out, dim=1), targets)

        return out,  loss, mape_loss

    # def generate_encoding(self, x):
    #     """This method generates the polyhedra encoding

    #     Parameters
    #     ----------
    #     x : pyg.Data object
    #         The pygeometric Data object

    #     Returns
    #     -------
    #     torch.Tensor
    #         The encoded polyhedra vector
    #     """

    #     out = self.cg_conv_layers(x.x, x.edge_index, x.edge_attr )
    #     out = self.leaky_relu(out)
    #     out = self.linear_1(out) # out -> (n_total_atoms_in_batch, 1)
    #     out = self.leaky_relu(out)
    #     out = self.global_pooling_layer(out, batch = x.batch) # out -> (n_graphs, n_hidden_layers[0])
    
    #     out = self.linear_2(out) # out -> (n_total_nodes_in_batch, n_hidden_layers[0])
    #     out = self.leaky_relu(out) 

    #     return out
    
def weight_init(m):
    """
    Initializes the weights of a module using Xavier initialization.
    """
    if isinstance(m, nn.Conv2d) or isinstance(m, nn.Linear):
        nn.init.xavier_uniform_(m.weight.data)

project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
# hyperparameters
save_model = True

# Training params
n_epochs = 500
learning_rate = 1e-2
batch_size = 2
early_stopping_patience = 20
device = 'cuda' if torch.cuda.is_available() else 'cpu'
# print(torch.cuda.mem_get_info())

# polyhedron model parameters
n_gc_layers = 2
n_hidden_layers=[8,4]
global_pooling_method = 'add'

# dataset parameters
dataset = 'plutonic_polyhedra'
feature_set_index = 3
y_val = ['energy_per_verts','dihedral_energy'][0]

###################################################################
# Start of the the training run
###################################################################

train_dir = f"{project_dir}{os.sep}datasets{os.sep}{dataset}{os.sep}feature_set_{feature_set_index}{os.sep}train"
# test_dir = f"{project_dir}{os.sep}datasets{os.sep}{dataset}{os.sep}feature_set_{feature_set_index}{os.sep}test"
# val_dir = f"{project_dir}{os.sep}datasets{os.sep}{dataset}{os.sep}feature_set_{feature_set_index}{os.sep}val"

train_dataset = PolyhedraDataset(database_dir=train_dir, device=device, y_val=y_val)
n_node_features = train_dataset[0].x.shape[1]
n_edge_features = train_dataset[0].edge_attr.shape[1]

node_max = torch.zeros(n_node_features, device = device)
node_min = torch.zeros(n_node_features, device = device)
edge_max = torch.zeros(n_edge_features, device = device)
edge_min = torch.zeros(n_edge_features, device = device)
for data in train_dataset:

    # Finding node max and min
    current_node_max = data.x.max(axis=0)[0]
    node_max = torch.vstack( [node_max,current_node_max] )
    node_max = node_max.max(axis=0)[0]

    current_node_min = data.x.min(axis=0)[0]
    node_min = torch.vstack( [node_min,current_node_min] )
    node_min = node_min.min(axis=0)[0]

    # Finding edge max and min
    current_edge_max = data.edge_attr.max(axis=0)[0]
    edge_max = torch.vstack( [edge_max,current_edge_max] )
    edge_max = edge_max.max(axis=0)[0]

    current_edge_min = data.edge_attr.min(axis=0)[0]
    edge_min = torch.vstack( [edge_min,current_edge_min] )
    edge_min = edge_min.min(axis=0)[0]

del train_dataset

def min_max_scaler(data):
    data.x = ( data.x - node_min ) / (node_min - node_max)
    data.edge_attr = ( data.edge_attr - edge_min ) / (edge_min - edge_max)

    data.edge_attr=data.edge_attr.nan_to_num()
    data.x=data.x.nan_to_num()
    return data

train_dataset = PolyhedraDataset(database_dir=train_dir,device=device, y_val=y_val, transform = min_max_scaler)

n_train = len(train_dataset)
train_loader = DataLoader(train_dataset, batch_size=batch_size, num_workers=0)


model = PolyhedronModel(n_node_features=n_node_features, 
                                n_edge_features=n_edge_features, 
                                n_gc_layers=n_gc_layers,
                                n_hidden_layers=n_hidden_layers,
                                global_pooling_method=global_pooling_method)

model.apply(weight_init)
m = model.to(device)


# sample =  next(iter(train_loader))
sample = train_dataset[0]
# print(m(sample))


def visualize_mesh(pos, face):
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    ax.axes.xaxis.set_ticklabels([])
    ax.axes.yaxis.set_ticklabels([])
    ax.axes.zaxis.set_ticklabels([])
    ax.plot_trisurf(pos[:, 0], pos[:, 1], pos[:, 2], triangles=data.face.t(), antialiased=False)
    plt.show()


def visualize_points(pos, edge_index=None, index=None):
    fig = plt.figure(figsize=(4, 4))
    if edge_index is not None:
        for (src, dst) in edge_index.t().tolist():
             src = pos[src].tolist()
             dst = pos[dst].tolist()
             plt.plot([src[0], dst[0]], [src[1], dst[1]], linewidth=1, color='black')
    if index is None:
        plt.scatter(pos[:, 0], pos[:, 1], s=50, zorder=1000)
    else:
       mask = torch.zeros(pos.size(0), dtype=torch.bool)
       mask[index] = True
       plt.scatter(pos[~mask, 0], pos[~mask, 1], s=50, color='lightgray', zorder=1000)
       plt.scatter(pos[mask, 0], pos[mask, 1], s=50, zorder=1000)
    plt.axis('off')
    plt.show()

# visualize_mesh(sample.pos, sample.face)

visualize_points(sample.pos, edge_index=sample.edge_index, index=None)
# optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
# es = EarlyStopping(patience = early_stopping_patience)
# # scheduler =  torch.optim.StepLR(optimizer, 
# #                                 step_size = 4, # Period of learning rate decay
# #                                 gamma = 0.5)

# scheduler =  torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 
#                                             factor=0.1,
#                                             patience=10,
#                                             threshold=1e-4,
#                                             min_lr=0,
#                                             )

# # sample = next(iter(test_loader))
# # # print(sample)
# # # print(sample.batch)
# # # print(sample.x[torch.where(sample.batch == 0)])
# # model(sample , targets = sample.y)



# n_epoch_0 = 0
# model.train()
# for epoch in range(n_epochs):
#     n_epoch = n_epoch_0 + epoch
#     batch_train_loss = 0.0
#     batch_train_mape = 0.0
#     for i,sample in enumerate(train_loader):
#         optimizer.zero_grad()
#         out, train_loss, mape_loss = model(sample , targets = sample.y)
#         train_loss.backward()
#         optimizer.step()
#         batch_train_loss += train_loss.item()
#         batch_train_mape += mape_loss.item()

#     sample = next(iter(train_loader))
#     # print(model.generate_encoding(sample))
#     # print(getattr(model,'linear_1').weight.grad)
#     batch_train_loss = batch_train_loss / (i+1)
#     batch_train_mape = batch_train_mape / (i+1)

#     batch_val_loss = 0.0
#     batch_val_mape = 0.0
#     for i,sample in enumerate(val_loader):
#         torch.set_grad_enabled(False)
#         out, val_loss, mape_val_loss = model(sample , targets = sample.y)
#         torch.set_grad_enabled(True)
#         batch_val_loss += val_loss.item()
#         batch_val_mape += mape_val_loss.item()
#     batch_val_loss = batch_val_loss / (i+1)
#     batch_val_mape = batch_val_mape / (i+1)
#     scheduler.step(batch_val_loss)


#     batch_test_loss = 0.0
#     batch_test_mape = 0.0
#     for i,sample in enumerate(test_loader):
#         torch.set_grad_enabled(False)
#         out, test_loss, mape_test_loss = model(sample , targets = sample.y)
#         torch.set_grad_enabled(True)
#         batch_test_loss += test_loss.item()
#         batch_test_mape += mape_test_loss.item()
#     batch_test_loss = batch_test_loss / (i+1)
#     batch_test_mape = batch_test_mape / (i+1)

#     current_lr = scheduler.optimizer.param_groups[0]['lr']
#     # val_loss *= (factor)  # to put it on the same scale as the training running loss)
#     if n_epoch % 1 == 0:
#         print(repr(n_epoch) + ",  " + repr(batch_train_loss) + ",  " + repr(batch_val_loss) + ",  " + repr(batch_test_loss) + ",  " + repr(100*batch_test_mape) + '%')
    
#     if es(model=model, val_loss=batch_val_loss,mape_val_loss=batch_val_mape):
#         print("Early stopping")
#         print('_______________________')
#         print(f'Stopping : {epoch - es.counter}')
#         print(f'mae_val : {es.best_loss**0.5}')
#         print(f'mape_val : {es.best_mape_loss}')
#         break
#     elif current_lr < 1e-6:
#         print("Under min learning rate")
#         print('_______________________')
#         print(f'Stopping : {epoch - es.counter}')
#         print(f'mae_val : {es.best_loss**0.5}')
#         print(f'mape_val : {es.best_mape_loss}')
#         break

# if save_model:
#     checkpoint = {
#             "epoch":n_epoch,
#             "model_state": model.state_dict(),
#             "optim_state": optimizer.state_dict(),
#             "scheduler_state": scheduler.state_dict(),
#             "train_loss": batch_train_loss,
#             "val_loss": batch_val_loss,
#             "test_loss": batch_test_loss,
#             }
#     torch.save(checkpoint, f"{project_dir}{os.sep}models{os.sep}model_checkpoint.pth")

