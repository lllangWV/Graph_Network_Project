import os
import json
import random
from glob import glob
from typing import List,Tuple

import torch
import numpy as np
from torch_geometric.data import Data, Dataset


def get_polyhedra_graph(file_name: str, device:str=None, y_val:str=None) -> Data:

    r"""
    this script opens a file of the GDB-9 database and processes it,
    returning the molecule structure in xyz format, a molecule identifier
    (tag), and a vector containing the entire list of molecular properties

    Args:

        file_name (str): filename containing the molecular information

    returns:

        molecule_id (int): integer identifying the molecule number
        in the database n_atoms (int): number of atoms in the molecule
        species (List[str]): the species of each atom (len = n_atoms)
        coordinates (np.array(float)[n_atoms,3]): atomic positions
        properties (np.array(float)[:]): molecular properties, see
        database docummentation charge (np.array(float)[n_atoms]):
        Mulliken charges of atoms

    """

    with open(file_name) as f:
        data = json.load(f)

    # node Features
    n_faces = len(data['x'])
    x = np.array(data['x'])
    edge_index = np.array(data['edge_index'])
    edge_attr = np.array(data['edge_attr'])
    pos = np.array(data['pos'])


    if y_val is None:
        y = data['y']
    else:
        y = data[y_val]



    # Nodes. Node feature matrix with shape [num_nodes, num_node_features]
    x = torch.tensor(x, dtype=torch.float)
    # Edges. Graph connectivity in COO format with shape [2, num_edges]
    edge_index = torch.tensor(edge_index, dtype=torch.long,device=device).contiguous()
    # Edge attributes.  Edge feature matrix with shape [num_edges, num_edge_features]
    edge_attr = torch.tensor(edge_attr, dtype=torch.float,device=device).contiguous()
    # Target to train against (may have arbitrary shape)
    y = torch.tensor(y, dtype=torch.float,device=device)

    pos = pos

    data = Data(x=x, edge_index=edge_index,edge_attr=edge_attr,pos = pos, y=y)
    data.to(device)
    return data

class PolyhedraDataset(Dataset):

    r"""Data set class to load molecular graph data"""

    def __init__(
        self,
        database_dir: str,
        y_val:str = 'y',
        n_max_entries: int = None,
        seed: int = 42,
        transform: object = None,
        pre_transform: object = None,
        pre_filter: object = None,
        device:str = None
    ) -> None:

        r"""

        Args:

           database_dir (str): the directory where the data files reside

           graphs: an object of class MolecularGraphs whose function is
                  to read each file in the data-base and return a
                  graph constructed according to the particular way
                  implemented in the class object (see MolecularGraphs
                  for a description of the class and derived classes)

           n_max_entries (int): optionally used to limit the number of clusters
                  to consider; default is all

           seed (int): initialises the random seed for choosing randomly
                  which data files to consider; the default ensures the
                  same sequence is used for the same number of files in
                  different runs

        """

        super().__init__(database_dir, transform, pre_transform, pre_filter)
        self.device=device
        self.y_val = y_val
        self.database_dir = database_dir
        
        filenames = database_dir + "/*.json"

        files = glob(filenames)
        
        self.n_polyhedra = len(files)

        if n_max_entries and n_max_entries < self.n_polyhedra:

            self.n_polyhedra = n_max_entries
            random.seed(seed)
            self.filenames = random.sample(files, n_max_entries)

        else:

            self.n_polyhedra = len(files)
            self.filenames = files

        

    def len(self) -> int:
        r"""return the number of entries in the database"""

        return self.n_polyhedra

    def get(self, idx: int) -> Data:

        r"""
        This function loads from file the corresponding data for entry
        idx in the database and returns the corresponding graph read
        from the file
        """

        if torch.is_tensor(idx):
            idx = idx.tolist()

        file_name = self.filenames[idx]

        polyhedra_graph = get_polyhedra_graph(file_name,device=self.device,y_val=self.y_val)

        return polyhedra_graph

    def get_file_name(self, idx: int) -> str:

        r"""Returns the cluster data file name"""

        return self.filenames[idx]

def main():
    parent_dir = os.path.dirname(__file__)
    train_dir = f"{parent_dir}{os.sep}train"
    test_dir = f"{parent_dir}{os.sep}test"


    # filenames = train_dir + "/*.json"
    # files = glob(filenames)
    # get_polyhedra_graph(file_name=files[0])

    dataset = PolyhedraDataset(database_dir=train_dir)

    print(dataset.get_file_name(idx = 0))

    print(dataset.get(idx = 0))



if __name__=='__main__':
    main()