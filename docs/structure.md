---
layout: default
title: Structure Module
nav_order: 8
---

# Structure Module

A module for working with protein structures, providing functionality for structure analysis, prediction, alignment and embedding generation. 
Just like the sequence module this is a very lightweight module that only is meant to represent a protein structure and have a few
very basic calculations. Again similar to the sequence module, adding additional functionality that depends on some of the later 
nerual network modules will not be possible and will be ported the container runner class. As long as the output of whatever
program is running in the container is a PDB file, it will be possible to load it into this class.

Under the hood the main structure is represented using the [biotite](https://www.biotite-python.org/latest/index.html) package, which itself has 
a lot of other functionalities that can be immediately used.

One additional limitation of representing structures is that there can be multiple chains in a single PDB file. These chains are
not necessarily proteins. The structure can come from NMR, X-ray, EM, or other sources rendering a lot of the information in the header
very difficult to interpret and parse; this is assuming that the header is not weirdly formatted in the first place. 

So we are keeping this module basic and only supporting loading/downloading structures, aligning two structures and 
calculating contact points between chains. If you have other ideas that can be generalized to any structure, please let us know.

### Basic Usage

```python
from benchmate.structure.structure import Structure

# Create from PDB file
structure = Structure(pdb="/path/to/structure.pdb")
# or
structure = Structure(pdb_id="1A2B", source="pdb", destination="/path/to/download/")

```

### Structure Analysis (very limited)

```python
# calculate SASA (solvent accesible surface area)
structure.calculate_sasa()

# find pockets in structure using fpocket
stucture.find_pockets()

# aling 2 structures
structure.align(other_structure)

# find contacts between chains only applies to pdb files with 2 chains (does not have to be proteins)
contacts=structure.find_contacts(chain_id1="A", chain_id2="B")
```

