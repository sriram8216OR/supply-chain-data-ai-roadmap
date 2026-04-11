# Supply Chain Fulfillment Risk Prediction System

## Objective
Predict and rank customer orders based on likelihood of late delivery, enabling proactive intervention by operations teams.

## Problem Context
In e-commerce logistics, a small percentage of orders are delivered late. Identifying these orders early allows prioritization of resources and improves customer satisfaction.

## Inputs
- Orders dataset (timestamps, delivery estimates)
- Order items (seller information)
- Customer data (location)
- Seller data
- Geolocation dataset (zip → lat/long)

## Feature Engineering
- Delivery metrics: delay_days, is_late
- Distance between seller and customer
- Expected delivery days
- Order complexity:
  - items_per_order
  - sellers_per_order
- Seller behavior:
  - seller_risk (historical delay rate)
  - seller_route_risk (seller-region interaction)
- Time features:
  - hour, day of week, month, weekend
- Derived:
  - distance_per_day (logistics pressure)

## Model
- Random Forest Classifier
- Class imbalance handled using:
  - class_weight = "balanced"
  - threshold tuning (0.3)
  - SMOTE (optional comparison)

## Outputs
- Binary prediction (late / not late)
- Risk score (probability of delay)
- Ranked list of high-risk orders

## Evaluation Strategy
- Focus on recall for late deliveries
- Precision-recall tradeoff analyzed
- Final model balances recall (~0.3) and precision (~0.4)

## Use Case
Operations team can:
- Focus on top X% risky orders
- Monitor problematic sellers and regions
- Improve SLA adherence

## Limitations
- No real-time logistics data (carrier delays, weather)
- Limited feature depth
- Moderate predictive performance due to data constraints