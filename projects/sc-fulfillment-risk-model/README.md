# Supply Chain Fulfillment Risk Prediction System

## Overview
This project builds a machine learning system to predict and rank e-commerce orders based on risk of late delivery.

## Why this matters
Late deliveries impact customer satisfaction and operational efficiency. This system helps identify high-risk orders early.

## Features
- Distance-based logistics complexity
- Seller performance modeling
- Seller-region interaction effects
- Time-based features
- Order complexity features

## Model
- Random Forest Classifier
- Handles class imbalance via:
  - class_weight
  - threshold tuning
  - SMOTE (optional)

## Results
| Model Type | Recall (Late) | Precision (Late) |
|----------|--------------|------------------|
| Baseline | 0.11 | 0.57 |
| Threshold Adjusted | 0.32 | 0.42 |
| SMOTE | 0.29 | 0.46 |

## Key Insight
Feature engineering (distance, seller behavior) had greater impact than model tuning.

## How to run

```bash
pip install -r requirements.txt
python main.py




🔹 Sample output
===== MODEL PERFORMANCE =====
              precision    recall  f1-score   support

       False       0.94      0.99      0.97     17924
        True       0.57      0.11      0.19      1276

    accuracy                           0.94     19200
   macro avg       0.75      0.55      0.58     19200
weighted avg       0.92      0.94      0.91     19200


===== MODEL PERFORMANCE (Adjusted Threshold) =====
              precision    recall  f1-score   support

       False       0.95      0.97      0.96     17924
        True       0.42      0.32      0.36      1276

    accuracy                           0.93     19200
   macro avg       0.69      0.64      0.66     19200
weighted avg       0.92      0.93      0.92     19200


===== TOP FEATURE IMPORTANCE =====
seller_route_risk    0.220656
seller_risk          0.080183
distance_per_day     0.079141
distance             0.074516
expected_days        0.068471
order_month          0.068451
order_hour           0.052447
order_dayofweek      0.034074
customer_state_SP    0.009858
customer_state_RJ    0.009265
dtype: float64
