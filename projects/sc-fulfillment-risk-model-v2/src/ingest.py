import pandas as pd
path = r"C:\Users\singsing\Desktop\Sriram\supply-chain-data-ai-roadmap\projects\sc-fulfillment-risk-model-v2\data\raw"


def load_data():

    data ={}
    data["customers"] = pd.read_csv(path+"\\olist_customers_dataset.csv")
    return data
                                
