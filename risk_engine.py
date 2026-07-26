import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
from config.config import RULE_CATALOG, HIGH_RISK_COUNTRIES, SANCTIONED_COUNTRIES

class RiskEngine:
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.triggered_rules: Dict[str, List[Dict[str, Any]]] = {}
        # Preprocess datetime fields
        self._preprocess_datetimes()

    def _preprocess_datetimes(self):
        """Converts timestamp columns to datetime objects for accurate age/speed math."""
        if "transactions" in self.data:
            self.data["transactions"]["transaction_time"] = pd.to_datetime(self.data["transactions"]["transaction_time"])
        if "login_history" in self.data:
            self.data["login_history"]["login_time"] = pd.to_datetime(self.data["login_history"]["login_time"])
        if "accounts" in self.data:
            self.data["accounts"]["open_date"] = pd.to_datetime(self.data["accounts"]["open_date"])
        if "kyc_records" in self.data:
            self.data["kyc_records"]["expiry_date"] = pd.to_datetime(self.data["kyc_records"]["expiry_date"])
        if "external_alerts" in self.data:
            self.data["external_alerts"]["alert_time"] = pd.to_datetime(self.data["external_alerts"]["alert_time"])

    def _trigger_rule(self, customer_id: str, rule_id: str, details: str):
        """Helper to append a triggered rule to a customer profile."""
        if customer_id not in self.triggered_rules:
            self.triggered_rules[customer_id] = []
        # Avoid duplicate rule triggers for the same customer
        if not any(r["rule_id"] == rule_id for r in self.triggered_rules[customer_id]):
            self.triggered_rules[customer_id].append({
                "rule_id": rule_id,
                "name": RULE_CATALOG[rule_id]["name"],
                "category": RULE_CATALOG[rule_id]["category"],
                "description": RULE_CATALOG[rule_id]["description"],
                "weight": RULE_CATALOG[rule_id]["weight"],
                "details": details
            })

    def evaluate_all_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Runs the entire catalog of 30 compliance checks."""
        self.triggered_rules = {}
        
        # Load tables
        cust_df = self.data["customers"]
        acc_df = self.data["accounts"]
        tx_df = self.data["transactions"]
        merch_df = self.data["merchants"]
        dev_df = self.data["devices"]
        log_df = self.data["login_history"]
        kyc_df = self.data["kyc_records"]
        alerts_df = self.data["external_alerts"]
        wl_df = self.data["aml_watchlist"]
        sanc_df = self.data["sanctions"]
        susp_df = self.data["suspicious_locations"]
        
        # Group references
        acc_cust_map = acc_df.set_index("account_number")["customer_id"].to_dict()
        cust_res_map = cust_df.set_index("customer_id")["residence_country"].to_dict()
        cust_age_map = cust_df.set_index("customer_id")["customer_age"].to_dict()
        
        # Merge Transactions with Merchants for quick lookup
        tx_merch = tx_df.merge(merch_df, on="merchant_id", how="left")
        tx_merch["customer_id"] = tx_merch["account_number"].map(acc_cust_map)
        
        # ----------------------------------------------------
        # R01: LARGE TRANSACTION (> $50,000)
        # ----------------------------------------------------
        r01_hits = tx_merch[tx_merch["amount"] > 50000]
        for _, row in r01_hits.iterrows():
            self._trigger_rule(
                row["customer_id"], 
                "R01_LARGE_TRANSACTION", 
                f"Transaction {row['transaction_id']} of ${row['amount']:,.2f} exceeds limit."
            )

        # ----------------------------------------------------
        # R02: RAPID TRANSFERS (3+ transfers in 10 minutes)
        # ----------------------------------------------------
        transfers = tx_merch[tx_merch["transaction_type"] == "TRANSFER"].sort_values("transaction_time")
        for acc_num, group in transfers.groupby("account_number"):
            if len(group) < 4:
                continue
            times = group["transaction_time"].tolist()
            for i in range(len(times) - 3):
                diff = (times[i+3] - times[i]).total_seconds()
                if diff <= 600: # 10 minutes
                    cust_id = acc_cust_map.get(acc_num)
                    if cust_id:
                        self._trigger_rule(
                            cust_id,
                            "R02_RAPID_TRANSFERS",
                            f"Account {acc_num} conducted 4 transfers within {(diff/60):.1f} minutes."
                        )
                    break

        # ----------------------------------------------------
        # R03: TRANSACTION STRUCTURING (3+ deposits/transfers in $9,000-$9,999 in 48h)
        # ----------------------------------------------------
        struct_tx = tx_merch[
            (tx_merch["amount"] >= 9000) & 
            (tx_merch["amount"] < 10000) & 
            (tx_merch["transaction_type"].isin(["TRANSFER", "DEPOSIT"]))
        ].sort_values("transaction_time")
        for acc_num, group in struct_tx.groupby("account_number"):
            if len(group) < 3:
                continue
            times = group["transaction_time"].tolist()
            amounts = group["amount"].tolist()
            for i in range(len(times) - 2):
                diff = (times[i+2] - times[i]).total_seconds()
                if diff <= 172800: # 48 hours
                    cust_id = acc_cust_map.get(acc_num)
                    if cust_id:
                        self._trigger_rule(
                            cust_id,
                            "R03_STRUCTURING",
                            f"Structuring warning: 3 transactions in $9,000-$9,999 range within {(diff/3600):.1f} hours. Amounts: {amounts[i:i+3]}"
                        )
                    break

        # ----------------------------------------------------
        # R04: CRYPTO MERCHANT TRANSACTION
        # ----------------------------------------------------
        r04_hits = tx_merch[tx_merch["category"] == "Crypto Exchange"]
        for _, row in r04_hits.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R04_CRYPTO_MERCHANT",
                f"Transaction {row['transaction_id']} to crypto merchant: {row['merchant_name']}."
            )

        # ----------------------------------------------------
        # R05: CASH INTENSIVE MERCHANT (Casino / Pawn Shop)
        # ----------------------------------------------------
        r05_hits = tx_merch[tx_merch["category"].isin(["Casino & Gambling", "Pawn Shop"])]
        for _, row in r05_hits.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R05_CASH_INTENSIVE_MERCHANT",
                f"Cash-intensive merchant activity: {row['merchant_name']} ({row['category']})."
            )

        # ----------------------------------------------------
        # R06: HIGH RISK MERCHANT (Merchant in suspicious country)
        # ----------------------------------------------------
        r06_hits = tx_merch[tx_merch["country"].isin(HIGH_RISK_COUNTRIES)]
        for _, row in r06_hits.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R06_HIGH_RISK_MERCHANT",
                f"Transaction with merchant in high-risk country: {row['merchant_name']} ({row['country']})."
            )

        # ----------------------------------------------------
        # R07: SANCTIONED COUNTRY LINK (Tx or Login)
        # ----------------------------------------------------
        sanc_tx = tx_merch[tx_merch["location_country"].isin(SANCTIONED_COUNTRIES)]
        for _, row in sanc_tx.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R07_SANCTION_COUNTRY",
                f"Transaction {row['transaction_id']} routed to sanctioned jurisdiction: {row['location_country']}."
            )
        sanc_logins = log_df[log_df["country"].isin(SANCTIONED_COUNTRIES)]
        for _, row in sanc_logins.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R07_SANCTION_COUNTRY",
                f"User session opened from sanctioned jurisdiction: {row['country']}."
            )

        # ----------------------------------------------------
        # R08: AML WATCHLIST MATCH
        # ----------------------------------------------------
        active_wl = wl_df[wl_df["status"] == "ACTIVE"]
        for _, row in active_wl.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R08_AML_WATCHLIST",
                f"Active listing on compliance watchlist: {row['reason']}."
            )

        # ----------------------------------------------------
        # R09: PEP CUSTOMER
        # ----------------------------------------------------
        peps = kyc_df[kyc_df["pep_status"] == "YES"]
        for _, row in peps.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R09_PEP_CUSTOMER",
                f"Customer matches Politically Exposed Person (PEP) list."
            )

        # ----------------------------------------------------
        # R10: NEGATIVE NEWS (Adverse Media)
        # ----------------------------------------------------
        neg_news = news_df = self.data["news_events"]
        neg_news = neg_news[neg_news["news_sentiment"] == "NEGATIVE"]
        for _, row in cust_df.iterrows():
            cust_name = row["full_name"]
            cust_id = row["customer_id"]
            # Search for customer name matches in sentiment negative news
            matches = neg_news[
                neg_news["entity_name"].str.contains(cust_name, case=False, na=False) |
                neg_news["summary"].str.contains(cust_name, case=False, na=False)
            ]
            if len(matches) > 0:
                self._trigger_rule(
                    cust_id,
                    "R10_NEGATIVE_NEWS",
                    f"Adverse media match: '{matches.iloc[0]['summary']}' ({matches.iloc[0]['source']})."
                )

        # ----------------------------------------------------
        # R11: INCOMPLETE KYC PROFILE
        # ----------------------------------------------------
        inc_kyc = kyc_df[kyc_df["doc_status"].isin(["PENDING", "EXPIRED", "FAILED"])]
        for _, row in inc_kyc.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R11_INCOMPLETE_KYC",
                f"KYC Document Status: {row['doc_status']}. Expiry: {row['expiry_date'].strftime('%Y-%m-%d')}."
            )

        # ----------------------------------------------------
        # R12: NEW DEVICE LOGIN (Device used only once)
        # ----------------------------------------------------
        # Check login counts per device/customer
        dev_counts = log_df.groupby(["customer_id", "device_id"]).size().reset_index(name="count")
        single_logs = dev_counts[dev_counts["count"] == 1]
        for _, row in single_logs.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R12_NEW_DEVICE_LOGIN",
                f"Login logged from newly authorized device: {row['device_id']}."
            )

        # ----------------------------------------------------
        # R13: MULTIPLE FAILED LOGINS (3+ in 24h)
        # ----------------------------------------------------
        failed_logs = log_df[log_df["login_status"] == "FAILED"].sort_values("login_time")
        for cust_id, group in failed_logs.groupby("customer_id"):
            if len(group) < 3:
                continue
            times = group["login_time"].tolist()
            for i in range(len(times) - 2):
                diff = (times[i+2] - times[i]).total_seconds()
                if diff <= 86400: # 24 hours
                    self._trigger_rule(
                        cust_id,
                        "R13_MULTIPLE_FAILED_LOGINS",
                        f"3 login failures recorded within {(diff/3600):.1f} hours."
                    )
                    break

        # ----------------------------------------------------
        # R14: IMPOSSIBLE TRAVEL (Velocity > 800 km/h)
        # ----------------------------------------------------
        # Predefined coordinates
        coords = {
            "New York": (40.7128, -74.0060),
            "London": (51.5074, -0.1278),
            "Tokyo": (35.6762, 139.6503),
            "Moscow": (55.7558, 37.6173),
            "Mogadishu": (2.0469, 45.3182)
        }
        
        def calc_distance(city1, city2):
            if city1 == city2:
                return 0.0
            loc1, loc2 = coords.get(city1), coords.get(city2)
            if not loc1 or not loc2:
                # generate approximation by hashing if not standard coords
                return float(abs(hash(city1) - hash(city2)) % 8000 + 500)
            
            # Simple spherical distance (Haversine)
            lat1, lon1 = np.radians(loc1[0]), np.radians(loc1[1])
            lat2, lon2 = np.radians(loc2[0]), np.radians(loc2[1])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            return 6371 * c # km

        sorted_logins = log_df.sort_values("login_time")
        for cust_id, group in sorted_logins.groupby("customer_id"):
            if len(group) < 2:
                continue
            records = group.to_dict("records")
            for idx in range(len(records) - 1):
                l1, l2 = records[idx], records[idx+1]
                time_diff = (l2["login_time"] - l1["login_time"]).total_seconds() / 3600.0 # hours
                if time_diff <= 0.0:
                    continue
                dist = calc_distance(l1["city"], l2["city"])
                if dist == 0:
                    continue
                speed = dist / time_diff
                if speed > 800: # Exceeds flight speed limit
                    self._trigger_rule(
                        cust_id,
                        "R14_IMPOSSIBLE_TRAVEL",
                        f"Geographic hop: {l1['city']} ({l1['country']}) -> {l2['city']} ({l2['country']}) "
                        f"within {time_diff*60:.1f} minutes. Required Speed: {speed:,.1f} km/h."
                    )
                    break

        # ----------------------------------------------------
        # R15: VPN LOGIN
        # ----------------------------------------------------
        vpn_logs = log_df[log_df["is_vpn"] == True]
        for _, row in vpn_logs.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R15_VPN_LOGIN",
                f"Login {row['login_id']} routed through virtual private network (VPN)."
            )

        # ----------------------------------------------------
        # R16: FOREIGN LOGIN (Login country != home country)
        # ----------------------------------------------------
        for _, row in log_df.iterrows():
            cust_id = row["customer_id"]
            home_country = cust_res_map.get(cust_id)
            if home_country and row["country"] != home_country:
                self._trigger_rule(
                    cust_id,
                    "R16_FOREIGN_LOGIN",
                    f"Session opened in country '{row['country']}', different from home country '{home_country}'."
                )

        # ----------------------------------------------------
        # R17: SUDDEN ACTIVATION OF DORMANT ACCOUNT
        # ----------------------------------------------------
        dormant_accs = set(acc_df[acc_df["status"] == "DORMANT"]["account_number"])
        dormant_txs = tx_merch[tx_merch["account_number"].isin(dormant_accs)]
        for _, row in dormant_txs.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R17_DORMANT_ACCOUNT_ACTIVE",
                f"Dormant account {row['account_number']} received transaction activity (ID: {row['transaction_id']})."
            )

        # ----------------------------------------------------
        # R18: HIGH TRANSACTION FREQUENCY BURST (> 3 std dev)
        # ----------------------------------------------------
        tx_merch["date"] = tx_merch["transaction_time"].dt.date
        freq_df = tx_merch.groupby(["customer_id", "date"]).size().reset_index(name="daily_count")
        for cust_id, group in freq_df.groupby("customer_id"):
            counts = group["daily_count"].values
            if len(counts) < 5: # Not enough history to verify standard deviations
                continue
            mean_f = np.mean(counts)
            std_f = np.std(counts)
            if std_f == 0:
                continue
            limit = mean_f + 3 * std_f
            outliers = group[group["daily_count"] > limit]
            if len(outliers) > 0:
                self._trigger_rule(
                    cust_id,
                    "R18_HIGH_TRANSACTION_FREQUENCY",
                    f"Transaction volume burst: {outliers.iloc[0]['daily_count']} transactions in one day (Mean: {mean_f:.1f}, Limit: {limit:.1f})."
                )

        # ----------------------------------------------------
        # R19: ACCOUNT TAKEOVER (ATO) SEQUENCE
        # ----------------------------------------------------
        # Sequence: Fail login or new device login -> transaction of > $30k within 2 hours
        for _, row in tx_merch[tx_merch["amount"] > 30000].iterrows():
            cust_id = row["customer_id"]
            tx_time = row["transaction_time"]
            # Look for failed logins or single device logins within 2 hours prior to this tx
            recent_fails = log_df[
                (log_df["customer_id"] == cust_id) & 
                (log_df["login_status"] == "FAILED") &
                (log_df["login_time"] < tx_time) &
                (log_df["login_time"] >= tx_time - pd.Timedelta(hours=2))
            ]
            if len(recent_fails) > 0:
                self._trigger_rule(
                    cust_id,
                    "R19_ACCOUNT_TAKEOVER_INDICATOR",
                    f"Credential mismatch followed by transaction: Failed login at {recent_fails.iloc[0]['login_time']} followed by transaction of ${row['amount']:,.2f} at {tx_time}."
                )

        # ----------------------------------------------------
        # R20: SHARED DEVICE FOOTPRINT (Device shared by 3+ customers)
        # ----------------------------------------------------
        dev_links = dev_df.groupby("device_id")["customer_id"].nunique()
        shared_devs = set(dev_links[dev_links >= 3].index)
        # Find which customers share these devices
        shared_customers = dev_df[dev_df["device_id"].isin(shared_devs)]["customer_id"].unique()
        for c_id in shared_customers:
            matched_devs = dev_df[(dev_df["customer_id"] == c_id) & (dev_df["device_id"].isin(shared_devs))]["device_id"].tolist()
            self._trigger_rule(
                c_id,
                "R20_SHARED_DEVICE",
                f"Device sharing warning: Linked to device(s) {matched_devs} which are associated with 3+ distinct customer records."
            )

        # ----------------------------------------------------
        # R21: SEVERE BALANCE DEPLETION (> 80% baseline)
        # ----------------------------------------------------
        # Calculate daily sum of outbound transactions
        outbound = tx_merch[tx_merch["transaction_type"].isin(["TRANSFER", "WITHDRAWAL", "PAYMENT"])]
        outbound_daily = outbound.groupby(["account_number", "date"])["amount"].sum().reset_index()
        for _, row in outbound_daily.iterrows():
            acc_num = row["account_number"]
            # Find account balance
            acc_info = acc_df[acc_df["account_number"] == acc_num]
            if len(acc_info) == 0:
                continue
            balance = acc_info.iloc[0]["balance"]
            if balance <= 100:
                continue
            daily_outflow = row["amount"]
            ratio = daily_outflow / (balance + daily_outflow)
            if ratio > 0.8:
                cust_id = acc_cust_map.get(acc_num)
                if cust_id:
                    self._trigger_rule(
                        cust_id,
                        "R21_LARGE_BALANCE_CHANGE",
                        f"Account {acc_num} balance depleted by {ratio*100:.1f}% in one day (Outflow: ${daily_outflow:,.2f})."
                    )

        # ----------------------------------------------------
        # R22: OUT-OF-PATTERN AMOUNT (Tx > 5x customer average)
        # ----------------------------------------------------
        cust_avg_tx = tx_merch.groupby("customer_id")["amount"].mean().to_dict()
        for _, row in tx_merch.iterrows():
            cust_id = row["customer_id"]
            avg = cust_avg_tx.get(cust_id, 0.0)
            if avg > 100 and row["amount"] > 5 * avg:
                self._trigger_rule(
                    cust_id,
                    "R22_OUTSIDE_CUSTOMER_PATTERN",
                    f"Out of pattern transaction: {row['transaction_id']} of ${row['amount']:,.2f} is > 5x historical average of ${avg:,.2f}."
                )

        # ----------------------------------------------------
        # R23: ROUND NUMBER TRANSACTION (Exact multiples of $5,000 / $10,000)
        # ----------------------------------------------------
        r23_hits = tx_merch[
            (tx_merch["amount"] >= 5000) & 
            (tx_merch["amount"] % 5000 == 0)
        ]
        for _, row in r23_hits.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R23_ROUND_NUMBER_PAYMENT",
                f"Large exact round transaction amount processed: ${row['amount']:,.2f} (ID: {row['transaction_id']})."
            )

        # ----------------------------------------------------
        # R24: MERCHANT BLACKLIST DIRECT HIT
        # ----------------------------------------------------
        r24_hits = tx_merch[tx_merch["blacklisted"] == True]
        for _, row in r24_hits.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R24_MERCHANT_BLACKLIST",
                f"Direct transaction hit with blacklisted merchant entity: {row['merchant_name']}."
            )

        # ----------------------------------------------------
        # R25: EXTERNAL FRAUD ALERT TRIGGERED
        # ----------------------------------------------------
        critical_alerts = alerts_df[alerts_df["severity"].isin(["HIGH", "CRITICAL"])]
        for _, row in critical_alerts.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R25_EXTERNAL_FRAUD_ALERT",
                f"External flag received from agency {row['source_agency']}: {row['alert_type']} ({row['severity']})."
            )

        # ----------------------------------------------------
        # R26: HIGH-RISK JURISDICTION ASSOCIATION
        # ----------------------------------------------------
        # Checks residence country or transaction partners
        for cust_id, row in cust_df.iterrows():
            c_id = row["customer_id"]
            if row["residence_country"] in HIGH_RISK_COUNTRIES:
                self._trigger_rule(
                    c_id,
                    "R26_COUNTRY_RISK",
                    f"Customer resides in designated high-risk jurisdiction: {row['residence_country']}."
                )
        tx_risk_country = tx_merch[tx_merch["location_country"].isin(HIGH_RISK_COUNTRIES)]
        for _, row in tx_risk_country.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R26_COUNTRY_RISK",
                f"Transaction {row['transaction_id']} routed to designated high-risk country: {row['location_country']}."
            )

        # ----------------------------------------------------
        # R27: LOGIN TO TX LOCATION MISMATCH (Within 1 hour)
        # ----------------------------------------------------
        logins_by_cust = {c_id: gp for c_id, gp in log_df.groupby("customer_id")}
        
        for _, row in tx_merch.iterrows():
            cust_id = row["customer_id"]
            tx_time = row["transaction_time"]
            tx_country = row["location_country"]
            
            cust_logins = logins_by_cust.get(cust_id)
            if cust_logins is None or cust_logins.empty:
                continue
                
            # Filter logins for this specific customer within 1 hour (extremely fast)
            recent_logs = cust_logins[
                (cust_logins["login_time"] >= tx_time - pd.Timedelta(hours=1)) &
                (cust_logins["login_time"] <= tx_time + pd.Timedelta(hours=1))
            ]
            if len(recent_logs) > 0:
                different_locs = recent_logs[recent_logs["country"] != tx_country]
                if len(different_locs) == len(recent_logs):
                    # Trigger only if all logins in this window differ from tx country
                    self._trigger_rule(
                        cust_id,
                        "R27_LOCATION_MISMATCH",
                        f"Location mismatch: login at {recent_logs.iloc[0]['city']} ({recent_logs.iloc[0]['country']}) "
                        f"but transaction routed from {row['location_city']} ({tx_country}) within 1 hour."
                    )

        # ----------------------------------------------------
        # R28: NEW ACCOUNT RAPID ACTIVITY (opened < 30 days ago, tx > $20k)
        # ----------------------------------------------------
        for _, row in tx_merch[tx_merch["amount"] > 20000].iterrows():
            acc_num = row["account_number"]
            # find account open date
            acc_info = acc_df[acc_df["account_number"] == acc_num]
            if len(acc_info) == 0:
                continue
            open_date = acc_info.iloc[0]["open_date"]
            tx_time = row["transaction_time"]
            age_days = (tx_time - open_date).days
            if 0 <= age_days <= 30:
                self._trigger_rule(
                    row["customer_id"],
                    "R28_ACCOUNT_AGE",
                    f"New account ({age_days} days old) initiated high-value transaction of ${row['amount']:,.2f}."
                )

        # ----------------------------------------------------
        # R29: DEMOGRAPHIC ACTIVITY MISMATCH (Age < 18 or > 90, tx > $10k)
        # ----------------------------------------------------
        for _, row in tx_merch[tx_merch["amount"] > 10000].iterrows():
            cust_id = row["customer_id"]
            age = cust_age_map.get(cust_id)
            if age and (age < 18 or age > 90):
                self._trigger_rule(
                    cust_id,
                    "R29_CUSTOMER_AGE",
                    f"High-value transaction of ${row['amount']:,.2f} processed on account of age outlier: {age} years old."
                )

        # ----------------------------------------------------
        # R30: OFF-HOURS HIGH-VALUE ACTIVITY (Hour 12-5 AM, amount > $20k)
        # ----------------------------------------------------
        off_hours_tx = tx_merch[
            (tx_merch["amount"] > 20000) & 
            (tx_merch["transaction_time"].dt.hour >= 0) & 
            (tx_merch["transaction_time"].dt.hour <= 5)
        ]
        for _, row in off_hours_tx.iterrows():
            self._trigger_rule(
                row["customer_id"],
                "R30_BEHAVIOURAL_ANOMALY",
                f"Transfer of ${row['amount']:,.2f} executed at {row['transaction_time'].strftime('%H:%M')} during sleeping hours."
            )

        return self.triggered_rules
