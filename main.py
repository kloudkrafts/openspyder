#!python3

import argparse

from common.config import DEFAULT_TIMESPAN
from common.loggingHandler import logger
from common.clientHandler import clientHandler

from Engines.pipelineEngine import pipelineEngine
from Connectors.mongoDBConnector import mongoDBConnector


operation = 'operation'
source = None
model_name = None
input_file = 'file'
last_days = None
fetch_all = None
action = None
scopes = None
search_domain = None
input_data = [{}]

params = {}

ch = clientHandler()

def extract():

    full_results = []

    logger.info("Instantiating Extractor {} with scopes : {}".format(source,scopes))
    client = ch.get_client(source=source, scopes=scopes)  
    
    for model_name in models:
        logger.info("Extracting schema: {} - model: {}".format(source,model_name))
        dataset = client.get_data(model_name=model_name,search_domains=[search_domain],**params)
        full_results += dataset,
        
    return full_results

def pipelines():

    p_engine = pipelineEngine()
    for model_name in models:
        p_engine.execute_pipeline_from_file(model_name)

def get_to_mongo():
    full_dataset = extract()
    mgconn = mongoDBConnector()
    mgconn.upsert_dataset(input_data=full_dataset)

def insert_to_mongo():
    mgconn = mongoDBConnector()
    mgconn.insert_from_jsonfile(input_file)

def transform_xls():

    for model_name in models:
        pdxls = ch.get_client(source,pipeline_def=model_name)
        dataframes = pdxls.apply_transforms()


class KwargsParse(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        for value in values:
            key, value = value.split('=')
            getattr(namespace, self.dest)[key] = value


if __name__ == "__main__":


    # Define Arg Parser
    parser = argparse.ArgumentParser(prog='kspyder')
    parser.add_argument('operation',action='store',type=str)
    parser.add_argument('-s','--source',action='store',type=str,dest=source)
    parser.add_argument('-k','--scopes',action='store',type=str,nargs='+',dest=scopes)
    parser.add_argument('-m','--model',action='store',type=str,nargs='+',dest=model_name)
    parser.add_argument('-f','--file',action='store',type=str,dest=input_file)
    parser.add_argument('-t','--timespan',action='store',type=int,dest=last_days,default=DEFAULT_TIMESPAN)
    parser.add_argument('-a','--all',action='store_true',dest=fetch_all,default=True)
    parser.add_argument('-x','--action',action='store',type=str,dest=action)
    parser.add_argument('-d','--searchdomain',action='store',type=str,nargs=3,dest=search_domain)
    parser.add_argument('-i', '--inputs', action=KwargsParse, nargs='*', default={})

    args = parser.parse_args()

    operation = args.operation
    source = args.source
    fetch_all = args.all
    last_days = args.timespan
    models = args.model
    input_file = args.file
    action = args.action
    scopes = args.scopes
    search_domain = args.searchdomain
    input_data = [args.inputs]
    
    params = {
        'trigger': 'cli',
        'last_days': None if fetch_all else last_days,
        'models': models,
        'search_domain': search_domain,
        'source': source,
        'action': action,
        'scopes': scopes,
        'input_data': input_data
    }

    function = locals()[args.operation]
    function()

