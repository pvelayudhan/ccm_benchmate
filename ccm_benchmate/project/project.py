from typing import List
import io

from sqlalchemy import select, insert
from PIL import Image


from ccm_benchmate.apis.utils import ApiCall, Apis
from ccm_benchmate.genome.genome import Genome
from ccm_benchmate.literature.literature import Paper, LitSearch, PaperInfo
from ccm_benchmate.molecule.molecule import Molecule
from ccm_benchmate.knowledge_base.knowledge_base import KnowledgeBase

from ccm_benchmate.sequence.sequence import Sequence, SequenceList, SequenceDict
from ccm_benchmate.structure.structure import Structure, Complex

from ccm_benchmate.project.utils import *


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

    def add_papers(self, papers: List[Paper]):
        """This will add a list of paper class instances and if not a paper class instance or does not have a paperinfo dataclass will raise an error"""
        papers_table=self.kb.db_tables["papers"]
        figures_table=self.kb.db_tables["figures"]
        tables_table=self.kb.db_tables["tables"]
        body_text_table=self.kb.db_tables["body_text"]
        chunked_text_table=self.kb.db_tables["body_text_chunked"]

        for item in papers:
            if isinstance(item, Paper):
                if isinstance(item.info, PaperInfo):
                    stms=insert(papers_table.c.source_id, papers.c.source, papers.c.title,
                                papers.c.project_id,
                                papers.c.abstract, papers.c.abstract_embeddings,
                                papers.c.pdf_url, papers.c.pdf_path,
                                papers.c.openalex_response).values(item.info.id, item.info.id_type,
                                                                   item.info.title,
                                                                   self.project_id,
                                                                   item.info.abstract,
                                                                   item.info.abstract_embeddings,
                                                                   item.info.download_link,
                                                                   item.info.pathname,
                                                                   item.info.opeanlex_info).returning(papers_table.c.paper_id)
                    paper_id=self.kb.session().execute(stms).scalar()
                    if item.info.figures is not None:
                        for i in range(len(item.info.figures)):
                            img = Image.open(item.info.figures[i])
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format="JPEG")
                            img_bytes = img_byte_arr.getvalue()
                            figure_stms=insert(figures_table.c.paper_id, figures_table.c.image_blob,
                                               figures_table.c.ai_caption,
                                               figures_table.c.figure_embeddings,
                                               figures_table.c.figure_interpretation_embeddings).values(paper_id,
                                                                                         img_bytes,
                                                                                         item.info.figure_interpretation[i],
                                                                                         item.info.figure_embeddings[i],
                                                                                         item.info.figure_interpretation_embeddings[i]
                                                                                         )
                            self.kb.session().execute(figure_stms)
                    if item.info.tables is not None:
                        for i in range(len(item.info.tables)):
                            img = Image.open(item.info.tables[i])
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format="JPEG")
                            img_bytes = img_byte_arr.getvalue()
                            table_smts = insert(tables_table.c.paper_id, tables_table.c.image_blob,
                                                 tables_table.c.ai_caption,
                                                 tables_table.c.table_embeddings,
                                                 tables_table.c.table_interpretation_embeddings).values(paper_id,
                                                                                           img_bytes,
                                                                                           item.info.table_interpretation[i],
                                                                                           item.info.table_embeddings[i],
                                                                                           item.info.table_interpretation_embeddings[i]
                                                                                           )
                            self.kb.session().execute(table_smts)

                    if item.info.text is not None:
                        text_stms=insert(body_text_table.c.paper_id, body_text_table.c.text,).values(paper_id, item.info.text)
                        self.kb.session().execute(text_stms)

                    if item.info.text_chunks is not None:
                        for i in range(len(item.info.text_chunks)):
                            chunk_stms=insert(chunked_text_table.c.paper_id, chunked_text_table.c.chunk,
                                              chunked_text_table.c.chunk_embeddings).values(paper_id,
                                                                                           item.info.text_chunks[i],
                                                                                           item.info.chunk_embeddings[i])
                            self.kb.session().execute(chunk_stms)
                    self.kb.session().commit()

                else:
                    raise ValueError("Paper instance must have a PaperInfo instance")
            else:
                raise TypeError("All items in the papers list must be of type Paper")

    #def add_sequences(self, sequences):
    #    pass

    #def add_structures(self, structures):
    #    pass

    def add_genome(self, genome_fasta, gtf, name, description, transcriptome_fasta=None, proteome_fasta=None):
        genome_table=self.kb.db_tables["genome"]
        query=select(genome_table.c.id, genome_table.c.project_id, genome_table.c.genome_name).filter(genome_table.c.project_id==self.project_id)
        results = self.kb.session().execute(query).fetchall()
        if len(results)==0:
            create=True
        elif len(results)==1:
            create=False
        else:
            raise ValueError("There are more than one genomes with the same name")

        self.genome=Genome(genome_fasta=genome_fasta, gtf=gtf, name=name, description=description, db_conn=self.kb.engine,
                           transcriptome_fasta=transcriptome_fasta, proteome_fasta=proteome_fasta, create=create)

    def add_api_calls(self, api_calls: List[ApiCall]):
        api_table=self.kb.db_tables["api_call"]
        for item in api_calls:
            if not isinstance(item, ApiCall):
                raise ValueError("All items in the api_calls list must be of type ApiCall")
            else:
                api_stms=insert(api_table.c.project_id, api_table.c.api_name, api_table.c.params,
                                api_table.c.results, api_table.c.query_time).values(self.project_id,
                                                                                    item.api_name,
                                                                                    item.kwargs,
                                                                                    item.results,
                                                                                    item.query_time)
                self.kb.session().execute(api_stms)
                self.kb.session().commit()

    def add_molecules(self, molecules):
        pass

    #def add_variants(self, variants):
    #    pass

    # for now we only can search papers and api calls because the import mechanism for sequence structures molecules
    # and variations is not yet implemented
    def search(self):
        pass

    def __str__(self):
        return f"Project(name={self.name}, project_id={self.project_id}, description={self.description})"

    def __repr__(self):
        return f"Project(name={self.name}, project_id={self.project_id}"


    