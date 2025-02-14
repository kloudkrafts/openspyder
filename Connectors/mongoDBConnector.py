import json, jmespath
from pymongo import MongoClient,errors
import datetime

from common.config import APP_NAME, DUMP_JSON, BASE_FILE_HANDLER as fh
from common.loggingHandler import logger


ACCEPTED_OPS = {
    "=": None,
    "~=": "$regex",
    ">": "$gt",
    ">=": "$gte",
    "<": "$lt",
    "<=": "$lte"
}

class mongoDBConnector():

    def __init__(self):
        self.client = MongoClient('localhost',27017)
        self.db = self.client[APP_NAME]
        self.schema = __name__

    def insert_dataset(self,input_data={},collection=None,key='name'):

        logger.info("Inserting dataset to Mongo Collection: {}".format(collection))

        collection = self.db[collection]
        result = collection.insert_many(input_data)

        return result

    def upsert_dataset(self,input_data={},collection=None,model=None):

        result_dataset = []
        insert_count = 0
        update_count = 0
        
        model_name = model['name'] if model else input_data['header']['model_name']
        model = model if model else input_data['header']['model']
        target_schema = input_data['header']['schema']
        api_name = model['API'] if 'API' in model.keys() else None
        dataset = input_data['data']

        if len(dataset) == 0:
            logger.info("Provided dataset is empty.")

        short_namespace = "%s.%s" %( target_schema, model_name)
        namespace = "%s.%s.%s" %( target_schema, api_name, model_name) if api_name else short_namespace
        collection_name = collection if collection else namespace
        dbcollection = self.db[collection_name]
        logger.info("Upserting dataset to Mongo Collection: {}\nModel:\n{}".format(collection_name,model))

        for document in dataset:            

            filter = {}
            for key in model['index_keys']:
                filter[key] = jmespath.search(key,document)
            # logger.debug("Using the following filter: {}".format(filter))
            # logger.debug("Upserting document: {}".format(document))
            upsert_result = dbcollection.replace_one(filter, document, upsert=True)

            if upsert_result.did_upsert:
                insert_count += 1
            else:
                update_count += upsert_result.modified_count

            context_result = {
                'upsert_filter': filter,
                'result': upsert_result.raw_result
            }

            result_dataset.append(context_result)

        full_dataset = {
                'header': {
                    'schema': self.schema,
                    'operation': 'upsert_dataset',
                    'collection_name': collection_name,
                    'model_name': model_name,
                    'model': model,
                    'count': len(result_dataset),
                    'insert_count': insert_count,
                    'update_count': update_count,
                    'json_dump': None,
                    'csv_dump': None
                },
                'data': result_dataset
            }
        
        if len(result_dataset) == 0:
            logger.info("Provided dataset is empty.")
        else:
            if DUMP_JSON:
                full_dataset = fh.dump_json(full_dataset, schema=self.schema, name=model_name)

        return full_dataset

    def insert_from_jsonfile(self,jsonpath):
        
        if jsonpath:
            with open(jsonpath,'r') as jf:
                json_data = json.load(jf)
                model_name = json_data['header']['model_name']
                input_data = json_data['data']
                self.insert_dataset(input_data=input_data, collection=model_name)

    def process_filter(self,filter_def):

        filter = {}

        operator = filter_def[1]
        if operator == "=":
            filter['$match'] = {
                filter_def[0]: filter_def[2]
            }
        else:
            filter['$match'] = {
                filter_def[0]: {
                    ACCEPTED_OPS[operator]: filter_def[2]
                }
            }
        
        return filter

    def aggregate_data(self,save_to=None,collection_name=None,pipeline=None,filters=[],**params):
        
        count = 0
        results_list = []
        processed_filter_chain = []

        for filter in filters:
            processed_filter_chain += self.process_filter(filter),
        logger.debug("Adding filters to the pipeline: {}".format(processed_filter_chain))

        if len(processed_filter_chain) > 0:
            pipeline = processed_filter_chain + pipeline
            
        logger.debug("Final pipeline: {}".format(pipeline))

        if save_to:
            view, count = self.create_view(
                name = save_to,
                collection_name = collection_name,
                pipeline = pipeline,
                overwrite = True
                )

            results = view.find()
            results_list = results.to_list()
        
        else:
            collection = self.db[collection_name]

            logger.info("Executing aggregation on Collection {}: {}".format(collection_name,pipeline))

            results = collection.aggregate(pipeline)
            results_list = results.to_list()
            count = len(results_list)

            logger.info("Query returned {} items.".format(count))

        result_dataset = {
            "header": {
                "schema": APP_NAME,
                "view": save_to,
                "collection": collection_name,
                "pipeline": pipeline,
                "count": count,
            },
            "data": results_list
        }

        return result_dataset

    def create_view(self,name=None,collection_name=None,pipeline=None,overwrite=False):

        now = datetime.datetime.now()
        count = 0
        logger.info("Creating view {} from collection : {}".format(name,collection_name))
        logger.debug("pipeline definition: \n {}".format(pipeline))

        try:
            view = self.db.create_collection(name, viewOn=collection_name, pipeline=pipeline)
            count = view.estimated_document_count()

        except errors.CollectionInvalid:
            
            if overwrite:
                logger.info("Collection already exists: {}. Overwriting.".format(name))
                existing_collection = self.db[name]
                existing_collection.drop()
                view = self.db.create_collection(name, viewOn=collection_name, pipeline=pipeline)
                count = view.estimated_document_count()

            else:
                logger.info("Collection already exists: {}. NOT Overwriting.".format(name))
                view = self.db[name]
                count = view.estimated_document_count()

        logger.info("Collection {} has {} documents.".format(name,count))

        return view, count
