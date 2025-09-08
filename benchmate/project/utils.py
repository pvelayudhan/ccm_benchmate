from typing import List
import io

from sqlalchemy import select, insert
from PIL import Image

from benchmate.apis.utils import ApiCall, Apis
from benchmate.genome.genome import Genome
from benchmate.literature.literature import Paper, LitSearch, PaperInfo
from benchmate.molecule.molecule import Molecule

#TODO add and get
from benchmate.sequence.sequence import Sequence, SequenceList, SequenceDict
from benchmate.structure.structure import Structure, Complex


class ProjectNameError(Exception):
    pass

def add_papers(project, papers: List[Paper]):
    """This will add a list of paper class instances and if not a paper class instance or does not have a paperinfo dataclass will raise an error"""
    papers_table=project.kb.db_tables["papers"]
    authors_table=project.kb.db_tables["authors"]
    figures_table=project.kb.db_tables["figures"]
    tables_table=project.kb.db_tables["tables"]
    body_text_table=project.kb.db_tables["body_text"]
    chunked_text_table=project.kb.db_tables["body_text_chunked"]


    for item in papers:
        if isinstance(item, Paper):
            if isinstance(item.info, PaperInfo):
                stms=insert(papers_table.c.source_id, papers.c.source, papers.c.title,
                            papers.c.project_id,
                            papers.c.abstract, papers.c.abstract_embeddings,
                            papers.c.pdf_url, papers.c.pdf_path,
                            papers.c.openalex_response).values(item.info.id, item.info.id_type,
                                                               item.info.title,
                                                               project.project_id,
                                                               item.info.abstract,
                                                               item.info.abstract_embeddings,
                                                               item.info.download_link,
                                                               item.info.pathname,
                                                               item.info.openalex_info).returning(papers_table.c.paper_id)
                paper_id=project.kb.session().execute(stms).scalar()

                for author in item.info.authors:
                    author_stms=insert(authors_table.c.paper_id,
                                      authors_table.c.name,
                                      author.c.affiliation).values(paper_id,
                                                                   author["name"],
                                                                   author["affiliation"])
                    project.kb.session().execute(author_stms)

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
                        project.kb.session().execute(figure_stms)

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
                        project.kb.session().execute(table_smts)

                if item.info.text is not None:
                    text_stms=insert(body_text_table.c.paper_id, body_text_table.c.text,).values(paper_id, item.info.text)
                    project.kb.session().execute(text_stms)

                if item.info.text_chunks is not None:
                    for i in range(len(item.info.text_chunks)):
                        chunk_stms=insert(chunked_text_table.c.paper_id, chunked_text_table.c.chunk,
                                          chunked_text_table.c.chunk_embeddings).values(paper_id,
                                                                                       item.info.text_chunks[i],
                                                                                       item.info.chunk_embeddings[i])
                        project.kb.session().execute(chunk_stms)

                if item.info.references is not None:
                    references_table=project.kb.db_tables["references"]
                    for paper in item.info.references:
                        id=project.add_papers(paper)
                        stms=insert(references_table.c.paper_id, references_table.c.id,).values(paper_id, id)
                        project.kb.session().execute(stms)

                if item.info.related_works is not None:
                    related_works_table=project.kb.db_tables["related_works"]
                    for paper in item.info.related_works:
                        id=project.add_papers(paper)
                        stms = insert(related_works_table.c.paper_id, related_works_table.c.id, ).values(paper_id, id)
                        project.kb.session().execute(stms)

                if item.info.cited_by is not None:
                    cited_by_table=project.kb.db_tables["cited_by"]
                    for paper in item.info.cited_by:
                        id=project.add_papers(paper)
                        stms = insert(cited_by_table.c.paper_id, cited_by_table.c.id, ).values(paper_id, id)
                        project.kb.session().execute(stms)

                project.kb.session().commit()

            else:
                raise ValueError("Paper instance must have a PaperInfo instance")
        else:
            raise TypeError("All items in the papers list must be of type Paper")

    return None

#def add_structures(project, structures):
#    pass

def add_genome(project, genome_fasta, gtf, name, description, transcriptome_fasta=None, proteome_fasta=None):
    """
    add a genome to the knowledgebase, the params are the same as in the genome class constructor
    :param genome_fasta: genome fast
    :param gtf:
    :param name: name of the genome, if there is already one then you will get an error
    :param description: description of the genome
    :param transcriptome_fasta: trascripts fasta
    :param proteome_fasta: proteome fasta
    :return: checks if there is such a genome if so creates the genome instance otherwise just returns the genome instance with relevant slots filled
    """
    genome_table=project.kb.db_tables["genome"]
    query=select(genome_table.c.id, genome_table.c.project_id, genome_table.c.genome_name).filter(genome_table.c.project_id==project.project_id)
    results = project.kb.session().execute(query).fetchall()
    if len(results)==0:
        create=True
    elif len(results)==1:
        create=False
    else:
        raise ValueError("There are more than one genomes with the same name")

    project.genome=Genome(genome_fasta=genome_fasta, gtf=gtf, name=name, description=description, db_conn=project.kb.engine,
                       transcriptome_fasta=transcriptome_fasta, proteome_fasta=proteome_fasta, create=create)
    return project

def add_api_calls(project, api_calls: List[ApiCall]):
    api_table=project.kb.db_tables["api_call"]
    for item in api_calls:
        if not isinstance(item, ApiCall):
            raise ValueError("All items in the api_calls list must be of type ApiCall")
        else:
            api_stms=insert(api_table.c.project_id, api_table.c.api_name, api_table.c.params,
                            api_table.c.results, api_table.c.query_time).values(project.project_id,
                                                                                item.api_name,
                                                                                item.kwargs,
                                                                                item.results,
                                                                                item.query_time)
            project.kb.session().execute(api_stms)
            project.kb.session().commit()

    return None

#TODO after structure import has been implemented I will need to get the strcture id and them add them to the import statement
def add_molecules(project, molecules):
    molecule_table=project.kb.db_tables["molecule"]
    for item in molecules:
        if not isinstance(item, Molecule):
            raise ValueError("All items in the molecules list must be of type Molecule")
        else:
            mol_stms=insert(molecule_table.c.project_id,
                            molecule_table.c.name,
                            molecule_table.c.smiles,
                            molecule_table.c.ecfp4,
                            molecule_table.c.fcfp4,
                            molecule_table.c.maccs,
                            molecule_table.c.properties,).values(project.project_id,
                                                            item.info.name,
                                                            item.info.smiles,
                                                            item.info.ecfp4,
                                                            item.info.fcfp4,
                                                            item.info.maccs,
                                                            item.info.properties,)
            project.kb.session().execute(mol_stms)
            project.kb.session().commit()

    return None

def add_structures(project, structures):
    structure_table=project.kb.db_tables["structure"]
    for item in structures:
        if not isinstance(item, Structure):
            raise ValueError("All items in the structures list must be of type Structure")
        str_stms=insert(structure_table.c.project_id, structure_table.c.name, )

def add_sequence(project, sequences):
    sequence_table=project.kb.db_tables["sequence"]
    for item in sequences:
        if not isinstance(item, Sequence):
            raise ValueError("All items in the sequences list must be of type Sequence")

        seq_stms=insert(sequence_table.c.project_id, sequence_table.c.name, sequence_table.c.sequence, sequence_table.c.type,
                    sequence_table.c.features, sequence_table.c.msa_path, sequence_table.c.blast_path, sequence_table.c.embeddings).values(
            project.project_id,
            item.name,
            item.sequence,
            item.type,
            item.features,
            item.msa_path,
            item.blast_path,
            item.embeddings
        )
        project.kb.session().execute(seq_stms)
        project.kb.session().commit()

def get_paper(description, papers):
    pass

def get_genome(name):
    pass

def get_structure(name):
    pass

def get_molecule(name):
    pass

def get_api_call(name):
    pass

# this will do a keyword search on the papers in the knowledegebase
# it needs to know if we are searching titles, abstracts, full text or captions
def keyword_search():
    pass

# given a figure (or caption) find similar figures in the knowledgebase
def figure_search():
    pass




