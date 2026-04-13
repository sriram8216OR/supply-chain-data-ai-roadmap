from src.ingest import load_data

def main():
    df = load_data()
    print(df["customers"].head())

if __name__ =="__main__":
    main()
