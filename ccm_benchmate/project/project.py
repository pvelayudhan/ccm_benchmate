from dataclasses import dataclass
import datetime

from pysam.bcftools import query
from sqlalchemy import select, insert

from ccm_benchmate.apis.ensembl import Ensembl
from ccm_benchmate.apis.ncbi import Ncbi
from ccm_benchmate.apis.reactome import Reactome
from ccm_benchmate.apis.uniprot import UniProt
from ccm_benchmate.apis.stringdb import StringDb
from ccm_benchmate.apis.rnacentral import RnaCentral
from ccm_benchmate.apis.others import BioGrid, IntAct
from ccm_benchmate.genome.genome import Genome
from ccm_benchmate.knowledge_base.tables import Structure, Sequence
from ccm_benchmate.literature.literature import Paper, LitSearch
from ccm_benchmate.knowledge_base.knowledge_base import KnowledgeBase

#TODO
#from ccm_benchmate.sequence.sequence import Sequence, SequenceList, SequenceDict
#from ccm_benchmate.structure.structure import Structure, Complex

from ccm_benchmate.project.utils import *

@dataclass
class ApiCall:
    """
    class to store the results of an api call, it's more than just the results but also the api name and the kwargs used.
    this is necessary for the project manager agent to know what to do with the results.
    """
    api_name: str
    results: dict
    kwargs: dict
    query_time: datetime.datetime


class Apis:
    """
    This is just an aggreation of the classes in the apis section, this will be part of the project class
    """
    def __init__(self, email, biogrid_api_key):
        self.apis={
            "ensembl": Ensembl(),
            "ncbi": Ncbi(email=email),
            "reactome": Reactome(),
            "uniprot": UniProt(),
            "stringdb": StringDb(),
            "biogrid": BioGrid(access_key=biogrid_api_key),
            "rnacentral": RnaCentral(),
            "intact": IntAct(),
        }

    def call(self, api_name, **kwargs):
        results=self.apis[api_name](**kwargs)
        return ApiCall(api_name, results, kwargs, datetime.datetime.now())

class Literature:
    """ same as apis just collecting all the methods in the literature module so that we can use them in the project class"""
    def __init__(self):
        self.litsearch=LitSearch()
        self.paper=Paper()

class Project:
    """
    this is the metaclass for the whole thing, it will collect all the modules and will be main point for interacting with the knowledgebase
    """
    def __init__(self, name, description, engine):
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
        self.name = name
        self.project_id=None
        self.description = description
        self.kb = KnowledgeBase(engine=engine)
        self.apis = Apis()
        self.literature = Literature()
        self.genome = None
        self.structures=[]
        self.sequences=[]
        self.papers=[]

    def _project_create(self):
        project_table=self.kb.db_tables["project"]
        query=select(project_table.c.project_id).filter(project_table.c.name==self.name)
        results=self.kb.session().execute(query).fetchall()

        if len(results)==0:
            ins=insert(project_table).values(name=self.name, description=self.description).returning(project_table.c.project_id)
            self.project_id=self.kb.session().execute(ins).scalar()
        elif len(results)==1:
            self.project_id=results[0][0]
        else:
            raise ProjectNameError("There are more than one projects with the same name")

    def _kb_create(self):
        self.kb._create_kb()

    #TODO
    def to_kb(self, data):
        if isinstance(data, Genome):
            pass
        elif isinstance(data, Structure):
            pass
        elif isinstance(data, Sequence):
            pass
        elif isinstance(data, Paper):
            pass
        elif isinstance(data, ApiCall):
            pass
        #TODO
        #elif isinstance(data, Variant):
        #    pass
        #elif isinstance(data, Molecule):
        #    pass
        else:
            raise TypeError("data must be one of the following: Genome, Structure, Sequence, Paper, ApiCall, LitSearch")

    def add_genome(self, genome_fasta, gtf, name, description, #db_conn=self.kb.engine,
                   transcrcriptome_fasta=None, proteome_fasta=None, create=True,):
        self.genome=Genome(genome_fasta, gtf, name, description, #db_conn,
                           transcrcriptome_fasta, proteome_fasta, create=create,)
        return self


    