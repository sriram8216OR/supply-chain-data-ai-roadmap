from pathlib import Path

def save_outputs(order_df, seller_df, time_df):
    output_path = Path("data/processed")
    output_path.mkdir(parents=True, exist_ok=True)

    # Save datasets
    order_df.to_csv(output_path / "orders_cleaned.csv", index=False)
    seller_df.to_csv(output_path / "seller_performance.csv", index=False)
    time_df.to_csv(output_path / "monthly_performance.csv", index=False)

    print("\nData saved to data/processed/")