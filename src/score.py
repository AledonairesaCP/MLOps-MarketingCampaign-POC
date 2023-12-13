import logging
import os
import json
import mlflow
from io import StringIO
from mlflow.pyfunc.scoring_server import infer_and_parse_json_input, predictions_to_json

import numpy as np
import pandas as pd
from datetime import datetime


def init():
    global model
    global input_schema
    # "model" is the path of the mlflow artifacts when the model was registered. For automl
    # models, this is generally "mlflow-model".
    model_path = os.path.join(os.getenv("AZUREML_MODEL_DIR"), "model")
    model = mlflow.pyfunc.load_model(model_path)
    input_schema = model.metadata.get_input_schema()


def run(raw_data):
    json_data = json.loads(raw_data)
    if "input_data" not in json_data.keys():
        raise Exception("Request must contain a top level key named 'input_data'")

    serving_input = json.dumps(json_data["input_data"])
    data = infer_and_parse_json_input(serving_input, input_schema)

    # Preprocessing
    # ============================================================================

    # ///// FEATURE SELECTION /////	
    
    # Variables that will be deleted from the dataset
    remove_list = ['ID', 'Year_Birth', 'NumDealsPurchases', 'NumStorePurchases',
                   'NumWebVisitsMonth', 'Complain', 'Z_CostContact', 'Z_Revenue']
    
    # Deleting previous list of variables from the dataset
    data = data.drop(remove_list, axis=1)

    
    # ///// FEATURE ENGINEERING /////

    # Marital_Status =======================================
    
    # Merging the least frequent categories in Marital_Status
    data['Marital_Status'] = data['Marital_Status'].replace(['YOLO', 'Absurd', 'Alone'], 'Others')

    # Dt_Customer ==========================================

    # Convert to datetime format
    date_objects = [datetime.strptime(date_str, "%Y-%m-%d") for date_str in data['Dt_Customer']]

    # The target date
    target_date = datetime(2023, 1, 1)

    # Calculate the difference in days between each date and the target date
    days_passed = [(target_date - date_object).days for date_object in date_objects]

    # Update the column
    data['Dt_Customer'] = days_passed


    # ///// OUTLIER TREATMENT /////

    # Determining which are outliers
    condition = data['Income'] == 666666
    
    # Setting outlier to NaN
    data.loc[condition, 'Income'] = np.nan


    # ///// IMPUTATION /////


    # ///// NORMALIZATION /////


    # ///// ENCODING /////

    # One-hot encoding for categorical variables
    data = pd.get_dummies(data, columns=['Education', 'Marital_Status'], prefix=['Edu', 'MS'])
    
    # Check if all dummies appear (consistency with traning dataset)
    all_dummies = ['Edu_2n Cycle', 'Edu_Basic', 'Edu_Graduation', 'Edu_Master', 'Edu_PhD',
                   'MS_Divorced', 'MS_Married', 'MS_Others', 'MS_Single', 'MS_Together', 'MS_Widow']
    for dummie in all_dummies:
        if dummie not in data.columns:
            data[dummie] = np.full((len(data)), False)
    
    # Ordering the columns (consistency with training dataset)
    order = ['Income', 'Kidhome', 'Teenhome', 'Dt_Customer', 'Recency', 'MntWines',
       'MntFruits', 'MntMeatProducts', 'MntFishProducts', 'MntSweetProducts',
       'MntGoldProds', 'NumWebPurchases', 'NumCatalogPurchases',
       'AcceptedCmp3', 'AcceptedCmp4', 'AcceptedCmp5', 'AcceptedCmp1',
       'AcceptedCmp2', 'Edu_2n Cycle', 'Edu_Basic',
       'Edu_Graduation', 'Edu_Master', 'Edu_PhD', 'MS_Divorced', 'MS_Married',
       'MS_Others', 'MS_Single', 'MS_Together', 'MS_Widow']
    
    data = data[order]

    # ============================================================================

    predictions = model.predict(data)

    return predictions.tolist()