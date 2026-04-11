from src.ingest import load_data
from src.clean import clean_orders, add_delivery_metrics
from src.transform import build_master_table, build_order_level_dataset,seller_performance_order_level,seller_region_performance,time_performance
from src.transform import build_summary, top_problem_states, top_problem_sellers
from src.transform import prepare_geo,add_distance_feature

from src.exporter import save_outputs
from src.transform import build_ml_dataset
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from imblearn.over_sampling import SMOTE
import pandas as pd

def main():
    data = load_data()

    orders = clean_orders(data["orders"])
    orders = add_delivery_metrics(orders)

    sellers_df = data["sellers"]
    geo_df = prepare_geo(data["geolocation"])
    

    master_df = build_master_table(
        orders,
        data["customers"],
        data["order_items"]
    )
    master_df = add_distance_feature(master_df,geo_df,sellers_df)


    order_df = build_order_level_dataset(master_df)

    ###########################################################################################

    ## Prediction System
    ml_df = build_ml_dataset(master_df)
    ml_df = ml_df.dropna()
    # Convert categorical
    ml_df = pd.get_dummies(ml_df, columns=["customer_state", "seller_state_route"], drop_first=True)

    X = ml_df.drop("is_late", axis=1)
    y = ml_df["is_late"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=50, random_state=42,
    class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print("\n===== MODEL PERFORMANCE =====")
    print(classification_report(y_test, y_pred))

    y_probs = model.predict_proba(X_test)[:, 1]

    # lower threshold
    y_pred_custom = (y_probs > 0.3).astype(int)

    print("\n===== MODEL PERFORMANCE (Adjusted Threshold) =====")
    print(classification_report(y_test, y_pred_custom))
    

    # SMOTE
    # sm = SMOTE(random_state=42)
    # X_train_res, y_train_res = sm.fit_resample(X_train, y_train)

    # # Train NEW model on resampled data
    # model_smote = RandomForestClassifier(
    #     n_estimators=50,
    #     random_state=42
    # )

    # model_smote.fit(X_train_res, y_train_res)

    # # Predict on TEST set (NOT training!)
    # y_pred_smote = model_smote.predict(X_test)

    # print("\n===== MODEL PERFORMANCE (SMOTE) =====")
    # print(classification_report(y_test, y_pred_smote))

    # Top Features
    feature_importance = pd.Series(
        model.feature_importances_,
        index=X_train.columns
    )

    top_features = feature_importance.sort_values(ascending=False).head(10)

    print("\n===== TOP FEATURE IMPORTANCE =====")
    print(top_features)
    #----------------------------------------------
    # Get probabilities instead of hard predictions
    y_probs = model.predict_proba(X_test)[:, 1]

    # Create a results DataFrame
    results_df = X_test.copy()
    results_df["actual"] = y_test.values
    results_df["risk_score"] = y_probs
    results_df["risk_percentile"] = results_df["risk_score"].rank(pct=True)

    # Sort by highest risk
    top_risky_orders = results_df.sort_values(
        by="risk_score",
        ascending=False
    ).head(20)

    print("\n===== TOP 20 RISKY ORDERS =====")
    print(top_risky_orders[["risk_score", "actual"]].head(20))


    #--------
    top_risky_orders.to_csv("data/processed/top_risky_orders.csv", index=False)

    
if __name__ == "__main__":
    main()