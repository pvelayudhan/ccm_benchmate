from benchmate.apis.ebi_clients.base_tool import BaseTool


class ClustalOmega(BaseTool):
    """Client for Clustal Omega multiple sequence alignment."""

    def __init__(self, email):
        super().__init__(email, "clustalo")


class EMBOSS_Pepinfo(BaseTool):
    """Client for EMBOSS Pepinfo analysis."""

    def __init__(self, email):
        super().__init__(email, "emboss_pepinfo")


class EMBOSS_Backtranseq(BaseTool):
    """Client for EMBOSS Backtranseq."""

    def __init__(self, email):
        super().__init__(email, "emboss_backtranseq")


class InterProScan5(BaseTool):
    """Client for InterProScan5 protein function analysis."""

    def __init__(self, email):
        super().__init__(email, "iprscan5")


class Lalign(BaseTool):
    """Client for Lalign local sequence alignment."""

    def __init__(self, email):
        super().__init__(email, "lalign")


class Muscle(BaseTool):
    """Client for Muscle multiple sequence alignment."""

    def __init__(self, email):
        super().__init__(email, "muscle")


class NCBIBlast(BaseTool):
    """Client for NCBI BLAST sequence similarity search."""

    def __init__(self, email):
        super().__init__(email, "ncbiblast")


class TCoffee(BaseTool):
    """Client for T-Coffee multiple sequence alignment."""

    def __init__(self, email):
        super().__init__(email, "tcoffee")


class Wise(BaseTool):
    """Client for Wise sequence alignment."""

    def __init__(self, email):
        super().__init__(email, "wise")
