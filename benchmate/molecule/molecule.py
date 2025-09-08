from dataclasses import dataclass
from typing import Optional

from rdkit import Chem
import numpy as np
from usearch_molecules.dataset import FingerprintedDataset, shape_ecfp4, shape_fcfp4, shape_maccs

from ccm_benchmate.structure.structure import Structure

@dataclass
class MoleculeInfo:
    name: str
    smiles: str
    mol: Chem.rdchem.Mol = None
    fingerprint_dim: int = 2048
    fingerprint_radius: int = 2
    bound_structure: Optional[Structure] = None
    ecfp4: Optional[np.ndarray] = None
    fcfp4: Optional[np.ndarray] = None
    maccs: Optional[np.ndarray] = None
    properties: Optional[dict] = None


class Molecule:
    """
    Molecule class to represent chemical structures using SMILES or InChI. this will include methods for different property
    calculations and structure comparisons using usearch molecules.
    """
    def __init__(self, name, smiles, bound_structure=None, fingerprint_dim=2048, radius=2):
        """
        Initialize a Molecule object with a SMILES string.
        :param smiles: A SMILES or InChI representation of the molecule.
        :param bound_structure: A bound strcutre this is a pdb it will become a strcture object upon loading
        """
        self.info=MoleculeInfo(name=name, smiles=smiles)
        self.info.mol = Chem.MolFromSmiles(smiles)
        if bound_structure is not None:
            self.info.bound_structure = Structure(pdb=bound_structure)
        self.info.fingerprint_dim = fingerprint_dim
        self.info.fingerprint_radius=radius
        self.info.ecfp4 = self._fingerprint(type="ecfp4")
        self.info.fcfp4 = self._fingerprint(type="fcfp4")
        self.info.maccs = self._fingerprint(type="maccs")
        self.info.properties = self._properties()


    def _fingerprint(self, type="ecfp4"):
        if type == "ecfp4":
            fpgen = Chem.FingerprintGenerator.GetMorganGenerator(radius=self.fingerprint_radius,
                                                                   fpSize=self.fingerprint_dim,
                                                                   atomInvariantsGenerator=Chem.rdFingerprintGenerator.GetMorganAtomInvGen())
            fp = fpgen.GetFingerprint(self.mol)
        elif type == "fcfp4":
            fpgen=Chem.FingerprintGenerator.GetMorganGenerator(radius=self.fingerprint_radius,
                fpSize=self.fingerprint_dim,
                atomInvariantsGenerator=Chem.FingerprintGenerator.GetMorganFeatureAtomInvGen())
            fp = fpgen.GetFingerprint(self.mol)
        elif type == "maccs":
            fp=Chem.MACCSkeys.GenMACCSKeys(self.mol)
        else:
            raise NotImplementedError("Only ecfp4, fcfp4 and maccs fingerprints are implemented")

        return fp


    def search(self, library, n=10, metric="tanimoto", using="ecfp4"):
        """
        Search for similar molecules in a given library using a specified fingerprinting method.
        :param library: The dataset to search within.
        :param n: Number of similar molecules to return.
        :param metric: Similarity metric to use (default is "tanimoto").
        :param using: Fingerprint type to use (default is "ecfp4").
        :return: A list of similar molecules from the library.
        """
        if metric != "tanimoto":
            raise NotImplementedError("metric must be tanimoto")

        if using not in ["ecfp4", "fcfp4", "maccs"]:
            raise NotImplementedError("method must be ecfp4 or fcfp4 or maccs")
        elif using == "ecfp4":
            shape = shape_ecfp4
        elif using == "fcfp4":
            shape = shape_fcfp4
        elif using == "maccs":
            shape = shape_maccs

        data = FingerprintedDataset(library, shape=shape)
        results = data.search(smiles=self.smiles, n=n)
        return results


    def _properties(self, missingVal=None):
        """
        calculate all the descriptors that rdkit can mange and return a dictionary of them
        :return: a dictionary of properties
        """
        res = {}
        for nm, fn in Chem.Descriptors._descList:
            # some of the descriptor fucntions can throw errors if they fail, catch those here:
            try:
                val = fn(self.info.mol)
            except:
                # print the error message:
                import traceback
                traceback.print_exc()
                # and set the descriptor value to whatever missingVal is
                val = missingVal
            res[nm] = val
        return res

    def __repr__(self):
        return f"Molecule(name={self.info.name}, smiles={self.info.smiles})"

    def __str__(self):
        return f"Molecule(name={self.info.name}, smiles={self.info.smiles})"

    def __eq__(self, other):
        if self.info.smiles == other.info.smiles:
            return True
        else:
            return False

    def __ne__(self, other):
        if not isinstance(other, Molecule):
            return True
        elif self == other:
            return False
        else:
            return True








