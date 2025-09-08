import json

import requests


class StringDb:
    def __init__(self):
        """
        constructor for StringDb class
        :param name: some sort of identifier for the protein it support uniprot, gene name, gene name synonyms
        :param species: species id for the protein, default is human, you can taxanomy id from ncbi
        :param network_depth: how deep you want to go in the network, default is 1, if more than 1 it will re search all the
        results for the next depth this will increase the time it takes to get the network and the number will increase exponentially
        """
        # name parameter supports use of uniprot id, uniprot accession #, gene name, or gene name synonyms
        # default organism is homo sapiens
        self.url="https://string-db.org/api/json/get_string_ids?identifiers={}&species={}"
        self.headers = {"Content-Type": "application/json"}

    def gather(self, species, name, get_network=False, network_depth=1):
        string_id, common_name, annotation = self._get_identifiers(species, name)
        interactions = self._get_interactions(string_id)

        results={"string_id":string_id, "common_name":common_name,
                 "annotation":annotation, "interactions":interactions}

        if get_network and network_depth > 1:
            network = self._get_network(string_id, visited_nodes=None, network_depth=network_depth)
            results["network"]=network

        return results

    def _get_identifiers(self, species, name):
        """
        get all the identifiers for the protein of interest.
        :return: self (will change)
        """
        response = requests.get(
            f"https://string-db.org/api/json/get_string_ids?identifiers={name}&species={species}")

        response.raise_for_status()
        content = response.content.decode().strip()
        content = json.loads(content)

        string_id = content[0]["stringId"]
        common_name = content[0]["preferredName"]
        annotation = content[0]["annotation"]
        return string_id, common_name, annotation

    def _get_interactions(self, string_id):
        """
        return interactions
        :return: self
        """
        response = requests.get(
            f"https://string-db.org/api/json/network?identifiers={string_id}")
        response.raise_for_status()

        interactions = response.content.decode().strip()
        interactions = json.loads(interactions)
        return interactions

    def _get_network(self, id, visited_nodes=None, network_depth=2):
        """

        :param id:
        :param visited_nodes:
        :param network_depth:
        :return:
        """
        if visited_nodes is None:
            visited_nodes = set()

        if id in visited_nodes or network_depth < 1:
            return {}

        visited_nodes.add(id)
        interactions = self._get_interactions(string_id=id)
        results = {id: interactions}
        current_depth = network_depth - 1
        while current_depth >= 1:
            for interaction in interactions:
                a = interaction["preferredName_A"]
                b = interaction["preferredName_B"]
                for partner in (a, b):
                    if partner not in visited_nodes:
                        results.update(self._get_network(partner, visited_nodes, current_depth))
            current_depth -= 1
        return results


