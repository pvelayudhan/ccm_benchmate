
from ccm_benchmate.apis.ensembl import Ensembl
from ccm_benchmate.apis.ncbi import Ncbi
from ccm_benchmate.apis.reactome import Reactome
from ccm_benchmate.apis.uniprot import UniProt
from ccm_benchmate.apis.stringdb import StringDb
from ccm_benchmate.apis.rnacentral import RnaCentral
from ccm_benchmate.apis.others import BioGrid, IntAct

#from ccm_benchmate.sequence.sequence import Sequence, SequenceList, SequenceDict
#from ccm_benchmate.structure.structure import Structure, Complex
from ccm_benchmate.genome.genome import Genome
from ccm_benchmate.literature.literature import Paper, LitSearch



#from ccm_benchmate.knowledge_base.knowledge_base import KnowledgeBase

class Apis:
    """
    This is just an aggreation of the classes in the apis section, this will be part of the project class
    """
    def __init__(self, email, biogrid_api_key):
        self.ensembl = Ensembl()
        self.ncbi = Ncbi(email=email)
        self.reactome = Reactome()
        self.uniprot = UniProt()
        self.stringdb = StringDb()
        self.biogrid = BioGrid(access_key=biogrid_api_key)
        self.rnacentral = RnaCentral()
        self.intact = IntAct()
        self.apiset = ["ensembl", "ncbi", "reactome", "uniprot", "stringdb", "biogrid", "rnacentral", "intact"]

    def api_call(self, target: str, method: str, *args, **kwargs):
        """
        Call a specific method from a specific aggregated class.
        Example: obj.api_call("classA", "method1", arg1, arg2, kw=value)
        """
        # Ensure the target exists
        if target not in self.apiset:
            raise AttributeError(f"No such api {target} in {self.apiset}")

        subobj = getattr(self, target)

        # Ensure the method exists
        if not hasattr(subobj, method):
            raise AttributeError(f"{target} has no method {method}")

        func = getattr(subobj, method)
        if not callable(func):
            raise TypeError(f"{method} on {target} is not callable")

        # Call it
        return func(*args, **kwargs)


class Project:
    """
    this is the metaclass for the whole thing, it will collect all the modules and will be main point for interacting with the knowledgebase
    """
    def __init__(self, description):
        """
        Main metaclass for consrcutor, if we are going to use any kind of agentic stuff the description is very important.
        The generatl description of the project can be used to determine
        1. if a paper is relevant based on the abstract
        2. if a gene or a feature of a protein or a domain is relevant based on the description

        etc.

        This will be passed as part of the prompt for the project manger agent.

        :param description: A detailed desscription of the project, this will be used in all aspect of the agentic workflows
        it is not necessary to use agents but if you would like to automate a bunch of stuff than it might be helpful.
        """
        self.description = description
        #this is very impcomplete, I will
        #self.kb = KnowledgeBase()
        self.apis = Apis()
        self.genome = None
        self.structures=[]
        self.sequences=[]
        self.papers=[]


    def _kb_create(self, engine):
        pass

    def _kb_connect(self, engine):
        pass

    #TODO this will do a lit search using the lit search class and then return papers will need to find a way to get them in the knowledge base
    def literature_search(self, query, database="pubmed", results="id", max_results=1000):
        litsearch = LitSearch()
        ids=litsearch.search(query, database=database, results=results, max_results=max_results)
        return ids

    def collect_papers(self, ids_types, **kwargs):
        """
        :param ids_types: these are the id and type of the paper to collect
        :param kwargs: see ccm_benchmate.literature.paper.Paper for kwargs
        :return:self, these will have the processed papers in memory
        """
        paper_list=[]
        for id, type in ids_types:
            paper=Paper(id, **kwargs)
            paper_list.append(paper)
        self.papers=self.papers+paper_list
        return self

    def add_papers(self):
        pass

    def add_genome(self, genome_fasta, gtf, name, description, #db_conn=self.kb.engine,
                   transcrcriptome_fasta=None, proteome_fasta=None, create=True,):
        self.genome=Genome(genome_fasta, gtf, name, description, #db_conn,
                           transcrcriptome_fasta, proteome_fasta, create=create,)
        return self

    def upload_papers(self):
        pass


    #TODO
    def sequences(self):
        pass

    #TODO
    def structures(self):
        pass








    