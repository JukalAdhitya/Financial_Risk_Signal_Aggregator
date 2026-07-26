import pandas as pd
from typing import Dict, List, Any
from config.config import RISK_THRESHOLDS, FILE_PATHS

class RiskScorer:
    def __init__(self, triggered_rules: Dict[str, List[Dict[str, Any]]]):
        self.triggered_rules = triggered_rules

    def calculate_scores(self, customers_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates risk scores for all customers, classifies them, and returns a DataFrame.
        Also exports the results to outputs/risk_scores.csv.
        """
        records = []
        for _, row in customers_df.iterrows():
            cust_id = row["customer_id"]
            cust_name = row["full_name"]
            
            # Sum up weights of triggered rules
            rules = self.triggered_rules.get(cust_id, [])
            raw_score = sum(r["weight"] for r in rules)
            
            if raw_score <= 70:
                final_score = float(raw_score)
            else:
                import math
                # Asymptotic curve between 71 and 97.5 based on raw score severity
                curve_val = 71.0 + 26.5 * (1.0 - math.exp(-(raw_score - 71.0) / 60.0))
                # Deterministic tie-breaker based on customer ID to ensure unique scores
                cust_num = int(cust_id.split("-")[1]) if "-" in cust_id else 0
                tie_breaker = (cust_num % 100) / 50.0 # Adds between 0.00 and 1.98
                final_score = round(curve_val + tie_breaker, 2)
                final_score = min(final_score, 100.0)
            
            # Classify Risk Level
            risk_level = self.classify_risk_level(final_score)
            
            records.append({
                "customer_id": cust_id,
                "full_name": cust_name,
                "risk_score": final_score,
                "risk_level": risk_level,
                "rules_triggered_count": len(rules),
                "rules_triggered_ids": ";".join([r["rule_id"] for r in rules])
            })
            
        df = pd.DataFrame(records)
        # Sort by risk score descending so high risk customers are at the top
        df = df.sort_values("risk_score", ascending=False)
        
        # Save output
        df.to_csv(FILE_PATHS["risk_scores"], index=False)
        print(f"Risk scores saved to {FILE_PATHS['risk_scores']}.")
        return df

    @staticmethod
    def classify_risk_level(score: float) -> str:
        """
        Classifies risk scores into bank compliance tiers using float boundaries.
        
        Compliance Threshold Rationale:
        - LOW (0-20): Matches standard customer demographics and domestic transaction limits.
        - MEDIUM (21-40): Slight anomalies (e.g. login from VPN or high transaction count).
        - HIGH (41-70): Significant red flags present (e.g. Structuring or Crypto Merchant transactions).
        - CRITICAL (71-100): Confirmed AML matches or high-velocity travel anomalies.
        """
        if score <= 20.0:
            return "LOW"
        elif score <= 40.0:
            return "MEDIUM"
        elif score <= 70.0:
            return "HIGH"
        else:
            return "CRITICAL"
