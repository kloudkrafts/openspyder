import json
from pymongo import MongoClient

from common.config import APP_NAME, DUMP_JSON, BASE_FILE_HANDLER as fh
from common.loggingHandler import logger

MONGO_QUERIES = fh.load_yaml("mongoDBQueries.yml",subpath="mongoDBConnector")
# SCHEMA_NAME = APP_NAME

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

    def upsert_dataset(self,input_data={},collection=None):

        result_dataset = []
        insert_count = 0
        update_count = 0
        
        model_name = input_data['header']['model_name']
        model = input_data['header']['model']
        dataset = input_data['data']

        if len(dataset) == 0:
            logger.info("Provided dataset is empty.")

        collection_name = collection if collection else model_name
        dbcollection = self.db[collection_name]
        logger.info("Upserting dataset to Mongo Collection: {}\nModel:\n{}".format(collection_name,model))

        for document in dataset:            

            filter = {}
            for key in model['index_keys']:
                filter[key] = document[key]
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

    def execute_queries(self, query_names=None, search_domain=None):
        
        queries = {}
        #extracting a subset of the MONGO_QUERIES dicitonary if query names were explicitly provided
        if query_names:
            queries = {query_name: MONGO_QUERIES[query_name] for query_name in set(query_names)}
        else:
            queries = MONGO_QUERIES

        for query_name,query_conf in queries.items():
            logger.info("Preparing Mongo Query {}: {}".format(query_name,query_conf))

            #if search domains were given, pile them up into a $match aggregation clause, with AND logic
            if search_domain:
                
                # matches = []

                # for sd in search_domains:
                sd = search_domain
                field = sd[0]
                operator = sd[1]
                value = sd[2]

                sd_conf = {}
                if operator == '=':
                    sd_conf = {field: value}
                elif operator == '~=':
                    sd_conf = { field: {'$regex': value} }
                else:
                    raise ValueError

                    # matches += sd_conf,

                match_conf = { '$match': sd_conf }

                old_conf = query_conf['operations']
                query_conf['operations'] = { **match_conf, **old_conf }

            result_dataset = self.execute_query(query_name,query_conf)

        # If DUMP_JSON is true, save last obtained dataset
        if DUMP_JSON:
            result_dataset = fh.dump_json(result_dataset,APP_NAME,query_name)

    def execute_query(self,query_name,query_conf):

        model_name, queryPipeline = build_mongo_query(query_conf)
        collection = self.db[model_name]

        logger.info("Executing mongo Query on Collection {}: {}".format(model_name,queryPipeline))

        results = collection.aggregate(queryPipeline)
        results_list = list(results)

        result_dataset = {
            "header": {
                "schema": APP_NAME,
                "model_name": model_name,
                "query_name": query_name,
                "query_conf": query_conf,
                "count": len(results_list),
            },
            "data": results_list
        }

        # If the query conf specifies the atomic query result needs to be dumped into csv or json,
        # proceed. Order is important : csv first, then json
        query_dump_json = query_conf['dump_json'] if 'dump_json' in query_conf.keys() else None
        query_dump_csv = query_conf['dump_csv'] if 'dump_csv' in query_conf.keys() else None

        if query_dump_csv:
            result_dataset = fh.dump_csv(result_dataset,APP_NAME,query_name)

        if query_dump_json:
            result_dataset = fh.dump_json(result_dataset,APP_NAME,query_name)

        return result_dataset

def build_mongo_query(query_conf):

    queryPipeline = []
    model_name = query_conf['collection']

    for operation_name,operation in query_conf['operations'].items():
        
        queryPipeline += {operation_name: operation},

    return model_name, queryPipeline
