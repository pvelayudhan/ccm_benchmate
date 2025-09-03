import tarfile

from PIL import Image
import pytesseract
import layoutparser as lp

import pymupdf
import torch
import json

from sentence_transformers import SentenceTransformer
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, AutoTokenizer
from qwen_vl_utils import process_vision_info
from chonkie import SemanticChunker, Model2VecEmbeddings
from colpali_engine.models import ColPali, ColPaliProcessor

from ccm_benchmate.literature.configs import *
from ccm_benchmate.utils.general_utils import *

# set up semantic chunker so I don't have to do it every time
params=paper_processing_config["chunking"]

embeddings = Model2VecEmbeddings(params["model"])

chunker = SemanticChunker(
            embedding_model=embeddings,
            threshold=params["threshold"],  # Similarity threshold (0-1) or (1-100) or "auto"
            chunk_size=params["chunk_size"],  # Maximum tokens per chunk
            min_sentences=params["min_sentences"],  # Initial sentences per chunk,
            return_type=params["return_type"]  # return a list of strings
)

embedding_model=SentenceTransformer("Qwen/Qwen3-Embedding-0.6B",
                                    cache_folder=os.path.abspath(os.path.join(os.path.dirname(__file__),"models/")))


def interpret_image(image, prompt, processor, model, max_tokens, device):
    """
    This function takes an image and a prompt, and generates a text description of the image using a vision-language model.
    the default model is Qwen2_5_VL.
    :param image: PIL image, no need to save to disk
    :param prompt: image prompt, see configs for default
    :param processor: processor class from huggingface
    :param model: model class from huggingface
    :param max_tokens: number of tokens to generate, more tokens = more text but does not mean more information
    :param device: gpu or cpu, if cpu keep it short
    :return: string
    """
    prompt[1]["content"][0]["image"] = image
    text = processor.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
    # this is here for compatibility I will not be processing videos
    image_inputs, video_inputs = process_vision_info(prompt)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(device)
    generated_ids = model.generate(**inputs, max_new_tokens=max_tokens)
    generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids,
    out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return output_text

def process_pdf(pdf, lp_model=paper_processing_config["lp_model"], interpret_figures=True, interpret_tables=True,
                vl_model=paper_processing_config["vl_model"], zoomx=2, device="cuda", max_tokens=400, figure_prompt=figure_messages,
                table_prompt=table_message):
    """
    This function takes a pdf file and processes it using layout parser and pytesseract to extract text, figures and tables.
    figures and tables are PIL instances, text is a string. the text is then chunked into smaller pieces using the chunking strategy
    the default is semantic chunking. This is preprocessing for the a RAG application
    :param pdf:
    :param lp_model:
    :param interpret_figures: whether to interpret figures or not using vision language model
    :param interpret_tables: whether to interpret tables or not using vision language model
    :param vl_model:
    :param zoomx: zoom factor for the pdf, higher means better quality but slower processing important for OCR
    :param device: better be GPU
    :param max_tokens:
    :param figure_prompt: see configs for default it makes a difference
    :param table_prompt:
    :return:
    """
    lp_model=lp.Detectron2LayoutModel(lp_model["config"], lp_model["model"],
                             label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                             extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8],
                             )

    doc = pymupdf.open(pdf)
    zoom_x = zoomx  # horizontal zoom
    zoom_y = zoomx  # vertical zoom
    mat = pymupdf.Matrix(zoom_x, zoom_y)
    texts = []
    figures = []
    tables=[]
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        pix = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        layout = lp_model.detect(pix)
        figure_blocks = lp.Layout([b for b in layout if b.type == 'Figure'])
        table_blocks = lp.Layout([b for b in layout if b.type == 'Table'])
        if len(figure_blocks) > 0:
            for block in figure_blocks:
                coords = block.block
                coords = (coords.x_1, coords.y_1, coords.x_2, coords.y_2,)
                figure_img = pix.crop(coords)
                figures.append(figure_img)

        if len(table_blocks) > 0:
            for block in table_blocks:
                coords = block.block
                coords = (coords.x_1, coords.y_1, coords.x_2, coords.y_2,)
                table_img = pix.crop(coords)
                tables.append(table_img)

        page_text = pytesseract.image_to_string(pix)
        texts.append(page_text)
    texts=[text.replace("\n", " ").replace("  ", " ") for text in texts]
    article_text = " ".join(texts)

    if interpret_figures or interpret_tables:
        model_vl = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            vl_model, torch_dtype="auto", device_map="auto"
        )
        processor = AutoProcessor.from_pretrained(vl_model)

    figure_interpretation = []
    if interpret_figures:
        for figure in figures:
            figure_interpretation.append(interpret_image(figure, figure_prompt, processor, model_vl, max_tokens, device,))

    table_interpretation = []
    if interpret_tables:
        for table in tables:
            table_interpretation.append(interpret_image(table, table_prompt, processor, model_vl, max_tokens, device,))

    return article_text, figures, tables, figure_interpretation, table_interpretation

def image_embeddings(images, model_dir=paper_processing_config["image_embedding_model"],
                     device="cuda:0"):

    model = ColPali.from_pretrained(
        model_dir,
        torch_dtype=torch.bfloat16,
        device_map=device,  # or "mps" if on Apple Silicon
    ).eval()
    processor = ColPaliProcessor.from_pretrained(model_dir)
    batch_images = processor.process_images(images).to(model.device)
    with torch.no_grad():
        image_embeddings = model(**batch_images)

    ems = []
    for i in range(image_embeddings.shape[0]):
        ems.append(image_embeddings[i, :, :])
    return ems


# same model for article text and captions
# TODO need to move the chunker out of the function so I don't load it every time
def text_embeddings(text, chunker=chunker, splitting_strategy="semantic", embedding_model=embedding_model):
    """
    genereate text embeddings using a chunking strategy and an embedding model. The model is a huggingface senntence transformer
    and the chunker is a chonkie semantic chunker
    :param text: text to embed
    :param chunker: chonkie semantic chunker
    :param splitting_strategy: whether to use semantic chunking or not
    :param embedding_model: sentence transformer model
    :return: chunks and embeddings if not chunked then the whole text and its embedding
    """
    if splitting_strategy == "semantic":
        chunks = chunker.chunk(text)
    elif splitting_strategy == "none":
        chunks=[text]
    else:
        raise NotImplementedError("Semantic splitting and none are the only implemented methods.")
    embeddings = embedding_model.encode(chunks)
    return chunks, embeddings

# At this point this is almost legacy because pmc ids are not a reliable source of retrieval. When we can find them
# they come in tar.gz format so here we are.
def extract_pdfs_from_tar(file, destination):
    """Lists the contents of a .tar.gz file.
    Args:
        file_path: The path to the .tar.gz file.
    """
    if not os.path.exists(destination):
        raise FileNotFoundError("{} does not exist.".format(destination))

    try:
        if file.endswith(".tar.gz"):
            read_str="r:gz"
        elif file.endswith(".tar.bz2"):
            read_str="r:bz2"
        elif file.endswith(".zip"):
            read_str="r:zip"
        else:
            read_str="r"

        paths=[]
        with tarfile.open(file, read_str) as tar:
            for member in tar.getmembers():
                if member.name.endswith("pdf"):
                    tar.extract(member, destination)
                    paths.append(os.path.abspath(os.path.join(destination, file, member.name)))

        return paths

    except FileNotFoundError:
        print(f"Error: File not found: {file}")
        return None

    except tarfile.ReadError:
        print(f"Error: Could not open or read {file}. It might be corrupted or not a valid tar.gz file.")
        return None

#This is not for the end user, this is for the developers
def filter_openalex_response(response, fields=None):
    if fields is None:
        fields=["id", "ids", "doi", "title", "topics", "keywords", "concepts",
                "mesh", "best_oa_location", "referenced_works", "related_works",
                "cited_by_api_url", "datasets"]
    new_response = {}
    for field in fields:
        if field in response.keys():
            new_response[field] = response[field]
    return new_response

# the whole citeby references etc need to be removed and then re-written as a separate function
# I give up on semantic scholar, it is unlikely I will get an api key, and openalex is good enough
def search_openalex(id_type, paper_id, fields=None):
    base_url = "https://api.openalex.org/works/{}"
    if id_type == "doi":
        paper_id = f"https://doi.org/:{paper_id}"
    elif paper_id == "MAG":
        paper_id = f"mag:{paper_id}"
    elif id_type == "pubmed":
        paper_id = f"pmid:{paper_id}"
    elif id_type == "pmcid":
        paper_id = f"pmcid:{paper_id}"
    elif id_type == "openalex":
        paper_id=paper_id

    url = base_url.format(paper_id)
    response = requests.get(url)
    try:
        response = json.loads(response.content.decode().strip())
        new_response = filter_openalex_response(response, fields)
    except:
        raise ValueError("Could not retrieve information for paper id {} of type {}".format(paper_id, id_type))

    return new_response

# its here, not sure if I will use it, still waiting for an api key, feel like not gonna happen
def search_semantic_scholar(paper_id, id_type, api_key=None, fields=None):
    base_url="https://api.semanticscholar.org/graph/v1/paper/{}?fields={}"
    if id_type == "doi":
        paper_id=f"DOI:{paper_id}"
    elif id_type == "arxiv":
        paper_id=f"ARXIV:{paper_id}"
    elif paper_id == "mag":
        paper_id=f"MAG:{paper_id}"
    elif id_type == "pubmed":
        paper_id=f"PMID:{paper_id}"
    elif id_type == "pmcid":
        paper_id=f"PMCID:{paper_id}"
    elif id_type == "ACL":
        paper_id=f"ACL:{paper_id}"

    available_fields=["paperId", "corpusID", "externalIds", "url", "title", "abstract", "venue",
                      "publicationVenue", "year", "referenceCount", "citationCount", "influentialCitationCount",
                      "isOpenAccess", "openAccessPdf", "fieldsOfStudy", "s2FieldsOfStudy",
                      "publicationTypes", "publicationDate", "journal", "citationStyles", "authors",
                      "citations", "references", "embedding", "tldr"]
    acceptable_fields=[]
    for field in fields:
        if field in available_fields:
            acceptable_fields.append(field)
        else:
            warnings.warn("field '{}' not available".format(field))

    if api_key is not None:
        headers = {
            'X-API-Key': api_key,
            'Accept': 'application/json'
        }
    url=base_url.format(paper_id, ",".join(acceptable_fields))
    response = requests.get(url)
    response.raise_for_status()
    response=json.loads(response.content.decode().strip())
    return response

def symmetric_score(sim):
    """
    get symetric score for a similarity matrix of a given text and project description
    :param sim: pairwise similarlty matrix of semantic chunks
    :return: float, symmetric score of mean max similarities
    """
    # Mean of max similarities from rows (text1 to other)
    mean_max_row = torch.max(sim, dim=1).values.mean().item()
    # Mean of max similarities from columns (other to text1)
    mean_max_col = torch.max(sim, dim=0).values.mean().item()
    # Symmetric score
    return (mean_max_row + mean_max_col) / 2

#TODO this might need to move to project instance because this can be used for other things like uniport description or other
# free text that is in the other api calls.
def text_score(project_description, paper_abstracts, chunker=chunker, embedding_model=embedding_model):
    """
    calculate a relevance score between a project description and a paper abstract, this is done by comparing
    each semantic chunk of the project description to each semantic chunk of each abstract. for an m desccirption chunks
    and n abstracts chunks we get an m x n matrix of cosine similarities. the final score is calculated taking some measure (max)
    for each row and then comparing the resulting vector of lenght n to all the other comparisions.
    :param project_description: string
    :param paper_abstract: list of strings
    :param chunker: SemanticChunker instance
    :param embedding_model: a model to generate embeddings
    :return: list of floats one for each abstract in the same order as the input list
    """
    project_description_chunks, project_description_embeddings = text_embeddings(project_description, chunker=chunker,
                                                                                 splitting_strategy="semantic")
    paper_scores = []
    for paper_abstract in paper_abstracts:
        abstract_chunks, abstract_embeddings = text_embeddings(paper_abstract, chunker=chunker,
                                                              splitting_strategy="semantic")
        sim=embedding_model.similarity(project_description_embeddings, abstract_embeddings)
        score=symmetric_score(sim)
        paper_scores.append(score)

    return paper_scores

