from dataclasses import dataclass
from datetime import datetime

from ccm_benchmate.apis.ensembl import Ensembl
from ccm_benchmate.apis.ncbi import Ncbi
from ccm_benchmate.apis.reactome import Reactome
from ccm_benchmate.apis.uniprot import UniProt
from ccm_benchmate.apis.stringdb import StringDb
from ccm_benchmate.apis.rnacentral import RnaCentral
from ccm_benchmate.apis.others import BioGrid, IntAct

@dataclass
class ApiCall:
    """
    class to store the results of an api call, it's more than just the results but also the api name and the kwargs used.
    this is necessary for the project manager agent to know what to do with the results.
    """
    api_name: str = None
    results: dict = None
    args: tuple = None
    kwargs: dict = None
    query_time: datetime.datetime = None


class Apis:
    """
    This is just an aggreation of the classes in the apis section, this will be part of the project class
    """

    def __init__(self, email, biogrid_api_key):
        self.apis = {
            "ensembl": Ensembl(),
            "ncbi": Ncbi(email=email),
            "reactome": Reactome(),
            "uniprot": UniProt(),
            "stringdb": StringDb(),
            "biogrid": BioGrid(access_key=biogrid_api_key),
            "rnacentral": RnaCentral(),
            "intact": IntAct(),
        }

    def _dispatch(self, target, method, *args, **kwargs):
        """
        Call a specific method from a specific aggregated class.
        Example: obj._dispatch("classA", "method1", arg1, arg2, kw=value)
        """
        # Ensure the target exists
        if not hasattr(self, target):
            raise ValueError(f"No such subobject: {target}")

        subobj = getattr(self, target)

        # Ensure the method exists
        if not hasattr(subobj, method):
            raise AttributeError(f"{target} has no method {method}")

        func = getattr(subobj, method)
        if not callable(func):
            raise TypeError(f"{method} on {target} is not callable")

        # Call it
        return func(*args, **kwargs)

    def call(self, api_name, *args, **kwargs):
        results = self._dispatch(api_name, *args, **kwargs)
        return ApiCall(api_name, results, args, kwargs, datetime.datetime.now())


