
from Bio.PDB import *
from esm.models.esm3 import ESM3
from esm.sdk.api import ESMProtein, SamplingConfig

parser = PDBParser(PERMISSIVE=1)

def get_esm3_embeddings(file, normalize=True, device="cuda"):
    ESM3InferenceClient = ESM3.from_pretrained("esm3-open").to(device)

    protein = ESMProtein.from_pdb(file)
    protein_tensor = ESM3InferenceClient.encode(protein)

    if normalize:
        output = ESM3InferenceClient.forward_and_sample(
            protein_tensor, SamplingConfig(return_mean_embedding=True)
        )
        embeddings = output.mean_embedding
    else:
        output = ESM3InferenceClient.forward_and_sample(
            protein_tensor, SamplingConfig(return_per_residue_embeddings=True)
        )
        embeddings = output.per_residue_embedding
    return embeddings



def get_pocket_dimensions(pocket_path):
    """
    Args:
        pocket_path (str): Path to the PDB file of the binding pocket.

    Returns:
        tuple:
            center (list of float): The [x, y, z] center coordinates.
            bbox_size (float): The maximum length in any dimension.
    """
    parser = PDBParser(PERMISSIVE=1)
    structure = parser.get_structure("pocket", pocket_path)

    coord = []

    # Extract all atom coordinates from the pocket structure
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    coord.append(atom.coord)

    # Convert list of coordinates to NumPy array
    coord_numpy = np.array(coord)

    # Find max and min along each axis
    x_max, y_max, z_max = np.max(coord_numpy, axis=0)
    x_min, y_min, z_min = np.min(coord_numpy, axis=0)

    # Compute the size of the bounding box (max extent)
    bbox_size = max(x_max - x_min, y_max - y_min, z_max - z_min)

    # Compute the geometric center of the pocket
    center = [
        (x_max + x_min) / 2,
        (y_max + y_min) / 2,
        (z_max + z_min) / 2
    ]
    return center, bbox_size

# need to figure out where to put this
def bounding_box(self, amino_acids=None, use_alpha_carbon=False):
        """
        generate a bounding box around a given list of amino acid ids. This can be used to generate more molecules or
        calculate properties of a pocket
        :param use: target or bound structure, this needs to be a Structure instance
        :param amino_acids: which amino acids to use
        :param use_alpha_carbon: whether to use the alpha carbon or the side chains to get the bounding box
        :return: 6 coordinates of the bounding box
        """

        if self.bound_structure is None:
            raise ValueError("bound_sturcutre must be set for bounding box calculation")

        coord = []

        for model in self.bound_structure:
            for chain in model:
                for residue in chain:
                    if amino_acids is None or residue.resname in amino_acids:
                        for atom in residue:
                            if use_alpha_carbon:
                                if atom.name == "CA":
                                    coord.append(atom.coord)
                            else:
                                coord.append(atom.coord)

        coord_numpy = np.array(coord)

        x_max, y_max, z_max = np.max(coord_numpy, axis=0)
        x_min, y_min, z_min = np.min(coord_numpy, axis=0)

        return {"xmax": x_max, "ymax": y_max, "zmax": z_max, "xmin": x_min, "ymin": y_min, "zmin": z_min}

