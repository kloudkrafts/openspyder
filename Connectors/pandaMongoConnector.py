import pymongoarrow
from pymongoarrow.monkey import patch_all

from Connectors.mongoDBConnector import mongoDBConnector
from Connectors.pandaXLSConnector import pandaXLSConnector
from common.config import BASE_FILE_HANDLER as fh
from common.loggingHandler import logger

class pandaMongoConnector(mongoDBConnector,pandaXLSConnector):

    def __init__(self):
        patch_all()
        mongoDBConnector.__init__(self)
        pandaXLSConnector.__init__(self)

    def pull_dataset(self,collection_name):
        
        collection = self.db[collection_name]
        df = collection.find_pandas_all()
        logger.debug(df.head())

        return df

