import os.path
import time

from dataclasses import dataclass
from typing import Optional

import numpy as np
from bs4 import BeautifulSoup as bs

from ccm_benchmate.literature.utils import *

class NoPapersError(Exception):
    pass

def paper_from_response(openalex_response):
    if "pmid" in openalex_response["ids"].keys():
        paper_id=openalex_response["ids"]["pmid"].split("/").pop()
        id_type="pubmed"
    else:
        raise ValueError("Could not find a valid paper ID in the response.")

    paper=Paper(paper_id=paper_id, id_type=id_type, search_info=False, download=False, process=False)
    paper.info.openalex_info = filter_openalex_response(openalex_response)
    if "best_oa_location" in openalex_response.keys() and openalex_response["best_oa_location"] is not None:
        link = openalex_response["best_oa_location"]["pdf_url"]
        if link is not None and link.endswith(".pdf"):
            download_link = openalex_response["best_oa_location"]["pdf_url"]
        else:
            warnings.warn("Did not find a direct pdf download link")
            download_link = None
    else:
        warnings.warn("There is no place to download the paper, this paper might not be open access")
        download_link = None
    paper.info.download_link = download_link
    return paper


def paper_from_link(link):
    openalex_id=link.split("/").pop()
    info=search_openalex(paper_id=openalex_id, id_type="openalex")
    paper=paper_from_response(info)
    return paper

class LitSearch:
    def __init__(self, pubmed_api_key=None, email=None, sort_by="relevance"):
        """
        create the ncessary framework for searching
        :param pubmed_api_key:
        """
        self.pubmed_key = pubmed_api_key
        self.email=email
        if sort_by not in ["relevance", "pub+date"]:
            raise ValueError("sort_by must be relevance or pub+date")
        self.sorting=sort_by
        self.params={
            "retmode": "xml",
            "email": self.email,
            "api_key": self.pubmed_key,
            "sort": self.sorting,
        }


        #TODO advanced search, while technically supported because query is just a string it would be nice if it was explicit
    def search(self, query, database="pubmed", results="id", max_results=1000):
        """
        search pubmed and arxiv for a query, this is just keyword search no other params are implemented at the moment
        :param query: this is a string that is passed to the search, as long as it is a valid query it will work and other fields can be specified
        :param database: pubmed or arxiv
        :param results: what to return, default is paper id PMID and arxiv id
        :param max_results:
        :return: paper ids specific to the database
        """
        #TODO implement pubmed api key for non-free papers, implement email
        if database == "pubmed":
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={}&retmax={}".format(query, max_results)
            search_response = requests.get(search_url, params=self.params)
            search_response.raise_for_status()

            soup = bs(search_response.text, "xml")
            ids = [item.text for item in soup.find_all("Id")]

            if results == "doi":
                dois = []
                for paperid in ids:
                    response = requests.get(
                        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={}".format(paperid))
                    response.raise_for_status()
                    soup = bs(response.text, "xml")
                    dois.append([item.text for item in soup.find_all("ArticleId") if item.attrs["IdType"] == "doi"])
                to_ret=dois
            else:
                to_ret=ids

        elif database == "arxiv":
            search_url="http://export.arxiv.org/api/search_query?{}&max_results={}".format(query, str(max_results))
            search_response = requests.get(search_url)
            search_response.raise_for_status()
            soup = bs(search_response.text, "xml")
            ids=[item.text.split("/").pop() for item in soup.find_all("id")][1:] #first one is the search id
            to_ret= ids
        return to_ret


@dataclass
class PaperInfo:
    id: str
    id_type: str
    title: Optional[str] = None
    authors: Optional[list] = None
    abstract: Optional[str] = None
    abstract_embeddings: Optional[np.ndarray]  = None
    text: Optional[str] = None
    text_chunks: Optional[list] = None
    chunk_embeddings: Optional[np.ndarray] = None
    figures: Optional[list] = None
    figure_embeddings: Optional[np.ndarray] = None
    tables: Optional[list] = None
    table_embeddings: Optional[np.ndarray] = None
    figure_interpretation: Optional[str] = None
    table_interpretation: Optional[str] = None
    figure_interpretation_embeddings: Optional[np.ndarray] = None
    table_interpretation_embeddings: Optional[np.ndarray] = None
    download_link: str = None
    pathname: str = None
    openalex_info: Optional[dict] = None
    references: Optional[list] = None
    related_works: Optional[list] = None
    cited_by: Optional[list] = None




class Paper:
    def __init__(self, paper_id, id_type="pubmed", search_info=True, download=True,
                 destination=".", process=True, **process_kwargs):
        """
        This class is used to download and process a paper from a given id, it can also be used to process a paper from a file
        :param paper_id:
        :param id_type: pubmed or arxiv
        :param filepath: if you already have the pdf file you can pass it here, mutually exclusive with paper_id
        :param citations: if you want to get the citations for the paper, need paper id, cannot do it with pdf
        :param references: if you want to get the references for the paper, need paper id, cannot do it with pdf
        :param related_works: if you want to get the related works for the paper, need paper id, cannot do it with pdf
        """
        self.info=PaperInfo(paper_id, id_type)
        self.info.abstract, self.info.title, self.info.authors= self.get_abstract()

        if search_info:
            self.info.openalex_info, self.info.download_link = self.search_info()

        if download and self.info.download_link is not None:
            try:
                self.download(destination)
                self.info.downloaded=True
                self.info.pathname=destination
            except:
                self.info.downloaded=False
                warnings.warn("Could not download paper")

        if process and self.info.downloaded:
            self.process(self.info.pathname, **process_kwargs)

    #I cannot imagine a paper where there are not authors I'm not writing a check for that.
    def get_abstract(self):
        if self.info.id_type =="pubmed":
            response=requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={}".format(self.info.id))
            response.raise_for_status()
            soup=bs(response.text, "xml")
            abstract_text=soup.find("AbstractText")
            if abstract_text is not None:
                abstract_text=abstract_text.text
            else:
                abstract_text=None
            title=soup.find("ArticleTitle").text
            author_tags=soup.find_all("Author")
            authors=[]
            for author in author_tags:
                affiliation_info=author.find("AffiliationInfo")
                if len(affiliation_info.find_all("Affiliation"))>0:
                    authors.append({"name":(author.find("ForeName").text + ", " + author.find("LastName").text),
                                "affiliation":(author.find("AffiliationInfo").find("Affiliation").text)})
                else:
                    authors.append({"name": (author.find("ForeName").text + ", " + author.find("LastName").text),
                                    "affiliation": None})

        elif self.info.id_type == "arxiv":
            response = requests.get("http://export.arxiv.org/api/query?search_query=id:{}".format(self.info.id))
            response.raise_for_status()
            soup=bs(response.text, "xml")
            abstract_text = soup.find("summary").text
            #not ideal if arxiv changes things, this will break
            title=soup.find_all("title")
            if len(title)==2:
                title=title[1].text
            else:
                title=None
            author_tags = soup.find_all("author")
            authors = []
            for author in author_tags:
                authors.append({"name": author.find("name").text,
                                "affiliation": None})

        else:
            raise NotImplementedError("source must be pubmed or arxiv other sources are not implemented")

        return abstract_text, title, authors

    def search_info(self):
        openalex_info = search_openalex(id_type=self.info.id_type, paper_id=self.info.id)
        if openalex_info is None:
            warnings.warn("Could not find a paper with id {}".format(self.info.id))

        else:
            if "best_oa_location" in openalex_info.keys() and openalex_info[
                "best_oa_location"] is not None:
                link = openalex_info["best_oa_location"]["pdf_url"]
                if link is not None and link.endswith(".pdf"):
                    download_link = openalex_info["best_oa_location"]["pdf_url"]
                else:
                    warnings.warn("Did not find a direct pdf download link")
                    download_link = None
            else:
                warnings.warn("There is no place to download the paper, this paper might not be open access")
                download_link = None

        self.info.openalex_info=openalex_info
        self.info.download_link=openalex_info
        return None

    def download(self, destination):
        download = requests.get(self.info.download_link, stream=True)
        download.raise_for_status()
        with open("{}/{}.pdf".format(destination, self.info.id), "wb") as f:
            f.write(download.content)
        file_paths=os.path.abspath(os.path.join("{}/{}.pdf".format(destination, self.info.id)))
        self.info.pathname=file_paths
        return None

    #TODO I need to pass arguments properly the **kwargs is not going to work
    def process(self, file_path, embed_images=True, embed_text=True,
                embed_interpretations=True, **kwargs):
        """
        see utils.py for details
        :return:
        """
        article_text, figures, tables, figure_interpretation, table_interpretation = process_pdf(file_path)
        self.info.text=article_text
        self.info.figures=figures
        self.info.tables=tables
        self.info.figure_interpretation=figure_interpretation
        self.info.table_interpretation=table_interpretation

        if embed_images:
            if len(self.info.figures) > 0:
                figure_embeddings=[]
                for fig in self.info.figures:
                    figure_embeddings.append(image_embeddings(fig))

            if len(self.info.tables) > 0:
                table_embeddings=[]
                for table in self.info.tables:
                    table_embeddings.append(image_embeddings(table))

        if embed_text:
            self.info.abstract_embeddings=text_embeddings(self.info.abstract, splitting_strategy="none")[1]
            if self.info.text is not None:
                self.info.text_chunks, self.info.chunk_embeddings=text_embeddings(self.info.text,
                                                                        splitting_strategy="semantic",
                                                                        **kwargs)
        if embed_interpretations:
            if self.info.figure_interpretation is not None:
                self.info.figure_interpretation_embeddings=text_embeddings(self.info.figure_interpretation,
                                                                      splitting_strategy="none",
                                                                      **kwargs)[1]

            if self.info.table_interpretation is not None:
                self.info.table_interpretation_embeddings=text_embeddings(self.info.table_interpretation,
                                                                      splitting_strategy="none",
                                                                     **kwargs)[1]

        return None

    def get_references(self):
        if "referenced_works" not in self.info.openalex_info.keys():
            raise ValueError("The response does not contain references.")
        references=self.info.openalex_info["referenced_works"]
        papers=[]
        for reference in references:
            try:
                p=paper_from_link(reference)
                papers.append(p)
                time.sleep(0.1)
            except:
                print("Could not find a paper with id {}".format(reference.split("/").pop()))

        self.info.references=papers
        return None

    def get_related_works(self):
        if "related_works" not in self.info.openalex_info.keys():
            raise ValueError("The response does not contain related works.")
        references = self.info.openalex_info["related_works"]
        papers = []
        for reference in references:
            try:
                p = paper_from_link(reference)
                papers.append(p)
                time.sleep(0.1)
            except:
                print("Could not find a paper with id {}".format(reference.split("/").pop()))
        self.info.related_works=papers
        return None

    def get_cited_by(self, cursor="*"):
        if "cited_by_api_url" not in self.info.openalex_info.keys():
            raise ValueError("The response does not contain cited by information.")
        url = self.info.openalex_info["cited_by_api_url"] + "&cursor="
        content = requests.get(url + cursor).content.decode().strip()
        content = json.loads(content)
        next_cursor = content["meta"]["next_cursor"]
        papers = []
        for item in content["results"] and len(content["results"])>0:
            try:
                p = paper_from_response(item)
                papers.append(p)
                time.sleep(0.1)
            except:
                print("Could not find a paper with id {}".format())
            finally:
                cursor=next_cursor
        while next_cursor != cursor and next_cursor is not None:
            self.get_cited_by(next_cursor)
        self.info.cited_by=papers
        return None

    def __str__(self):
        return self.info.title

    def __repr__(self):
        return "Paper(id={}, id_type={}, title={})".format(self.info.id, self.info.id_type, self.info.title)






