import os
import subprocess
from dataclasses import dataclass
from io import StringIO
from typing import List, Dict, Optional

import requests
import torch
import pandas as pd

from biotite.structure import sasa, distance, to_sequence, get_chains
from biotite.structure.io.pdb import PDBFile
from biotite.structure.alphabet import to_3di

from benchmate.structure.utils import *

@dataclass
class StructureInfo:
    name: str
    pdb: str
    chains: List[str] = None
    seq_3di: Optional[str] = None

#TODO extract names of things that map to each chain, extract name of the sequence or id or some other metadata.
class Structure:
    def __init__(self, name, pdb, id, source="PDB", destination=".", calculate_embeddings=False,):
        """
        constructor for Structure class
        :param pdb:
        :param sequence:
        :param predict:
        :param model:
        """
        self.pdb = os.path.abspath(pdb)
        if pdb is not None:
            self.structure = PDBFile.read(self.pdb).get_structure()[0]

        if pdb is None and id is not None:
            pdb=os.path.abspath(download(id, source, destination))

        self.info = StructureInfo(name=name, pdb=pdb)
        self.info.sasa = self.calculate_sasa()
        if calculate_embeddings:
            self.info.embeddings=self.calculate_embeddings()
        else:
            self.info.embeddings = None
        self.info.seq_3di = self.get_3di()
        self.info.chains = get_chains(self.structure)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"


    def align(self, other, destination):
        if self.pdb is None or other.pdb is None:
            raise ValueError("Cannot align structures without a PDB")

        command = ["mustang", "-i", os.path.abspath(self.pdb), os.path.abspath(other.pdb), "-o",
                   os.path.abspath(destination), "-r", "ON"]
        process = subprocess.run(command)
        if process.returncode != 0:
            raise ValueError("There was an error aligning structures. See error below \n {}".format(process.stderr))

        aligned_pdb = os.path.abspath(destination + "results.pdb")
        rotation_file = os.path.abspath(destination + "results.rms_rot")
        html_report = os.path.abspath(destination + "results.html")
        return aligned_pdb, rotation_file, html_report

    def find_pockets(self, **kwargs):
        """
        :param kwargs: these are additional key value pairs to be fed into fpocket, read its documentation for details
        :return:
        """
        command_params = []
        for key, value in kwargs.items():
            command_params.append(f"--{key} {value}")

        command_params = " ".join(command_params)
        command = "fpocket -f {pdb} -x -d {command_params}".format(pdb=self.pdb, command_params=command_params)
        run = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode != 0:
            raise RuntimeError(run.stderr.decode())
        else:
            results = run.stdout.decode()
            pocket_properties = pd.read_csv(StringIO(results), sep=" ")
            pocket_list = [file for file in os.listdir(self.pdb.replace(".pdb", "_out")) if file.endswith(".pdb")]
            pocket_coords = [get_pocket_dimensions(item) for item in pocket_list]
            return pocket_list, pocket_properties, pocket_coords

    #TODO
    def tm_score(self, other):
        pass

    def write(self, fpath):
        PDBFile.write(self.pdb, fpath)

    def contacts(self, chain_id1, chain_id2, cutoff=5.0, level="atom", measure="any"):
        """
        Get contacts between two chains in the structure.
        :param chain_id1:
        :param chain_id2:
        :param cutoff:
        :return:
        """
        chain1 = self._get_chain(chain_id1)
        chain2 = self._get_chain(chain_id2)
        contacts=[]
        for i in range(len(chain1)):
            for j in range(len(chain2)):
                if measure == "any":
                    dist = distance(chain1[i], chain2[j])
                elif measure=="CA":
                    if "CA" in chain1[i].atom_name and "CA" in chain2[j].atom_name:
                        dist = distance(chain1[i], chain2[j])
                    else:
                        continue
                if dist < cutoff:
                    if level == "atom":
                        contacts.append({chain_id1: i, chain_id2: j,
                                     "distance": dist})
                    elif level == "residue":
                        contacts.append({chain_id1: chain1[i].res_id, chain_id2: chain2[j].res_id,
                                     "distance": dist})

        return contacts

    def __repr__(self):
        return "Structure(name={}, pdb={}, chains={})".format(self.info.name, self.info.pdb, ",".join(self.chains))

    def __str__(self):
        return self.pdb



