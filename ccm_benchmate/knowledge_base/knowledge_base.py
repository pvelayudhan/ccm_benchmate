import pandas as pd

from sqlalchemy import MetaData, select
from sqlalchemy.orm import sessionmaker

from ccm_benchmate.knowledge_base.tables import *


class KnowledgeBase:
    def __init__(self, engine):
        """
        basic db constructor, will create the tables if it doesn't exist but we assume that the database is already created
        :param engine: sqlalchemy engine created from sqlalchemy.create_engine()
        """
        self.engine=engine
        self.meta = MetaData(bind=self.engine)
        self.meta.reflect(bind=self.engine)
        self.session = sessionmaker(self.engine)
        self.db_tables = self.meta.tables

    def _create_kb(self):
        if len(self.db_tables)==0:
            Base.metadata.create_all(self.engine)
            self.meta.reflect(bind=self.engine)
            self.db_tables = self.meta.tables
        else:
            print("Database already exists")

