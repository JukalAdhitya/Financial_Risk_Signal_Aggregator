import os

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
GENERATED_DATA_DIR = os.path.join(DATA_DIR, "generated_data")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Ensure directories exist
os.makedirs(GENERATED_DATA_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# File Paths
FILE_PATHS = {
    "customers": os.path.join(GENERATED_DATA_DIR, "customers.csv"),
    "accounts": os.path.join(GENERATED_DATA_DIR, "accounts.csv"),
    "transactions": os.path.join(GENERATED_DATA_DIR, "transactions.csv"),
    "merchants": os.path.join(GENERATED_DATA_DIR, "merchants.csv"),
    "devices": os.path.join(GENERATED_DATA_DIR, "devices.csv"),
    "login_history": os.path.join(GENERATED_DATA_DIR, "login_history.csv"),
    "kyc_records": os.path.join(GENERATED_DATA_DIR, "kyc_records.csv"),
    "external_alerts": os.path.join(GENERATED_DATA_DIR, "external_alerts.csv"),
    "aml_watchlist": os.path.join(GENERATED_DATA_DIR, "aml_watchlist.csv"),
    "sanctions": os.path.join(GENERATED_DATA_DIR, "sanctions.csv"),
    "suspicious_locations": os.path.join(GENERATED_DATA_DIR, "suspicious_locations.csv"),
    "news_events": os.path.join(GENERATED_DATA_DIR, "news_events.json"),
    "risk_scores": os.path.join(OUTPUTS_DIR, "risk_scores.csv"),
}

# Threshold Definitions
RISK_THRESHOLDS = {
    "LOW": (0, 20),
    "MEDIUM": (21, 40),
    "HIGH": (41, 70),
    "CRITICAL": (71, 100),
}

# Country classifications
SANCTIONED_COUNTRIES = ["Iran", "North Korea", "Syria", "Cuba", "Sudan", "Russia", "Belarus"]
HIGH_RISK_COUNTRIES = ["Venezuela", "Somalia", "Yemen", "Afghanistan", "Myanmar", "Iraq", "Libya"]
STABLE_COUNTRIES = ["United States", "United Kingdom", "Canada", "Germany", "France", "Japan", "Singapore", "Australia", "India", "Switzerland"]
ALL_COUNTRIES = STABLE_COUNTRIES + HIGH_RISK_COUNTRIES + SANCTIONED_COUNTRIES

# Rule Specifications and Weights
# Total rule weights can exceed 100, but final score is capped at 100
RULE_CATALOG = {
    "R01_LARGE_TRANSACTION": {
        "name": "Large Transaction Alert",
        "description": "Single transaction amount exceeds $50,000",
        "weight": 20,
        "category": "Transaction Anomaly",
    },
    "R02_RAPID_TRANSFERS": {
        "name": "Rapid Fund Transfers",
        "description": "More than 3 transfers to different accounts within 10 minutes",
        "weight": 15,
        "category": "Behavioral Anomaly",
    },
    "R03_STRUCTURING": {
        "name": "Transaction Structuring",
        "description": "Multiple transactions just below the $10,000 reporting threshold ($9,000-$9,999) within 48 hours",
        "weight": 30,
        "category": "Regulatory Signal",
    },
    "R04_CRYPTO_MERCHANT": {
        "name": "Crypto Asset Merchant Transaction",
        "description": "Transaction involving a crypto exchange or digital asset provider",
        "weight": 15,
        "category": "Merchant Risk",
    },
    "R05_CASH_INTENSIVE_MERCHANT": {
        "name": "Cash-Intensive Merchant Transaction",
        "description": "Transactions with high-risk cash industries like casinos, pawn shops, or cash-out terminals",
        "weight": 15,
        "category": "Merchant Risk",
    },
    "R06_HIGH_RISK_MERCHANT": {
        "name": "High-Risk Merchant Association",
        "description": "Transaction with a merchant flagged for compliance concerns",
        "weight": 20,
        "category": "Merchant Risk",
    },
    "R07_SANCTION_COUNTRY": {
        "name": "Sanctioned Jurisdiction Link",
        "description": "Transactions or logins originating from or connected to a sanctioned country",
        "weight": 35,
        "category": "Geopolitical Risk",
    },
    "R08_AML_WATCHLIST": {
        "name": "AML Watchlist Match",
        "description": "Customer name matches OFAC, PEP, or internal AML watchlists",
        "weight": 40,
        "category": "Regulatory Signal",
    },
    "R09_PEP_CUSTOMER": {
        "name": "Politically Exposed Person (PEP)",
        "description": "Customer is flagged as a PEP or close associate",
        "weight": 25,
        "category": "KYC Profile Risk",
    },
    "R10_NEGATIVE_NEWS": {
        "name": "Adverse Media Match",
        "description": "Adverse or negative news sentiments found in media regarding the customer",
        "weight": 20,
        "category": "Adverse Media",
    },
    "R11_INCOMPLETE_KYC": {
        "name": "Incomplete KYC Profile",
        "description": "KYC documentation is pending, expired, or failed verification",
        "weight": 15,
        "category": "KYC Profile Risk",
    },
    "R12_NEW_DEVICE_LOGIN": {
        "name": "New Device Authorization",
        "description": "Login from a newly registered or unverified device",
        "weight": 10,
        "category": "Credential Security",
    },
    "R13_MULTIPLE_FAILED_LOGINS": {
        "name": "Multiple Failed Logins",
        "description": "More than 3 failed login attempts within 24 hours",
        "weight": 15,
        "category": "Credential Security",
    },
    "R14_IMPOSSIBLE_TRAVEL": {
        "name": "Geographic Velocity Anomaly (Impossible Travel)",
        "description": "Consecutive logins from geographic locations requiring velocity > 800 km/h",
        "weight": 30,
        "category": "Credential Security",
    },
    "R15_VPN_LOGIN": {
        "name": "VPN or Proxy Access",
        "description": "Logins originating from known VPN or proxy IP hosting subnets",
        "weight": 10,
        "category": "Credential Security",
    },
    "R16_FOREIGN_LOGIN": {
        "name": "Foreign Login Activity",
        "description": "Login originating from a country other than the customer's home residence country",
        "weight": 15,
        "category": "Credential Security",
    },
    "R17_DORMANT_ACCOUNT_ACTIVE": {
        "name": "Sudden Activation of Dormant Account",
        "description": "Account inactive for 180+ days suddenly has high-volume transaction activity",
        "weight": 20,
        "category": "Transaction Anomaly",
    },
    "R18_HIGH_TRANSACTION_FREQUENCY": {
        "name": "High Transaction Frequency Burst",
        "description": "Daily transaction frequency exceeds 3 standard deviations of customer's historical average",
        "weight": 15,
        "category": "Behavioral Anomaly",
    },
    "R19_ACCOUNT_TAKEOVER_INDICATOR": {
        "name": "Account Takeover Signal (ATO)",
        "description": "Coordinated sequence: new device login + password reset + immediate large withdrawal",
        "weight": 30,
        "category": "Transaction Anomaly",
    },
    "R20_SHARED_DEVICE": {
        "name": "Shared Device Footprint",
        "description": "A single device is linked to 3 or more distinct customer accounts",
        "weight": 25,
        "category": "Credential Security",
    },
    "R21_LARGE_BALANCE_CHANGE": {
        "name": "Severe Balance Depletion",
        "description": "Single-day net balance reduction exceeding 80% of account baseline",
        "weight": 20,
        "category": "Transaction Anomaly",
    },
    "R22_OUTSIDE_CUSTOMER_PATTERN": {
        "name": "Out-of-Pattern Amount",
        "description": "Transaction amount exceeds 5x of customer's average transaction amount",
        "weight": 15,
        "category": "Behavioral Anomaly",
    },
    "R23_ROUND_NUMBER_PAYMENT": {
        "name": "Round Number Transaction",
        "description": "Large transaction of exact round amount (e.g. multiples of $5,000 or $10,000) indicating potential structuring/informal transfers",
        "weight": 10,
        "category": "Transaction Anomaly",
    },
    "R24_MERCHANT_BLACKLIST": {
        "name": "Blacklisted Merchant Direct Hit",
        "description": "Direct transaction with a merchant on the bank's active blacklist",
        "weight": 25,
        "category": "Merchant Risk",
    },
    "R25_EXTERNAL_FRAUD_ALERT": {
        "name": "External Fraud Alert Triggered",
        "description": "Direct alert from external financial systems (e.g. FinCEN, FIU) regarding a transaction/customer",
        "weight": 20,
        "category": "Regulatory Signal",
    },
    "R26_COUNTRY_RISK": {
        "name": "High-Risk Jurisdiction Association",
        "description": "Customer residence or transaction partner located in high-risk non-cooperative jurisdictions",
        "weight": 15,
        "category": "Geopolitical Risk",
    },
    "R27_LOCATION_MISMATCH": {
        "name": "Login-to-Transaction Location Mismatch",
        "description": "Login location and transaction merchant location country differ within 1 hour",
        "weight": 20,
        "category": "Credential Security",
    },
    "R28_ACCOUNT_AGE": {
        "name": "Rapid Activity on New Account",
        "description": "High-volume or high-value transactions occurring within 30 days of account opening",
        "weight": 15,
        "category": "KYC Profile Risk",
    },
    "R29_CUSTOMER_AGE": {
        "name": "Demographic Activity Mismatch",
        "description": "High-value transactions occurring on accounts of customers aged under 18 or over 90",
        "weight": 15,
        "category": "KYC Profile Risk",
    },
    "R30_BEHAVIOURAL_ANOMALY": {
        "name": "Off-Hours High-Value Activity",
        "description": "Large transfers performed during typical sleeping hours (12 AM - 5 AM)",
        "weight": 20,
        "category": "Behavioral Anomaly",
    },
}
