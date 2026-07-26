import os
import json
import pandas as pd
from typing import Dict, Any, Tuple
from config.config import FILE_PATHS

class DataValidationError(Exception):
    """Custom exception raised for database schema or integrity validation errors."""
    pass

class DataLoader:
    def __init__(self, file_paths: Dict[str, str] = FILE_PATHS):
        self.file_paths = file_paths
        self.data: Dict[str, Any] = {}

    def load_all(self) -> Dict[str, Any]:
        """Loads and validates all datasets. Returns a dictionary of DataFrames."""
        print("Starting Data Loader & Schema Validation...")
        
        # Load CSVs
        for key, path in self.file_paths.items():
            if key == "risk_scores":
                continue # This is an output file, we don't load it initially
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing required database file: {path}. Run data generation first.")

            if path.endswith(".csv"):
                self.data[key] = pd.read_csv(path)
            elif path.endswith(".json"):
                with open(path, "r") as f:
                    self.data[key] = pd.DataFrame(json.load(f))
                    
        # Validate data
        self.validate_schemas()
        self.validate_referential_integrity()
        
        print("Data loaded and validated successfully.")
        return self.data

    def validate_schemas(self):
        """Verifies that all columns, data types, and primary keys satisfy constraints."""
        required_columns = {
            "customers": ["customer_id", "full_name", "email", "phone", "address", "residence_country", "customer_age"],
            "accounts": ["account_number", "customer_id", "account_type", "open_date", "balance", "status"],
            "transactions": ["transaction_id", "account_number", "transaction_time", "amount", "merchant_id", 
                             "transaction_type", "transaction_status", "ip_address", "location_city", "location_country"],
            "merchants": ["merchant_id", "merchant_name", "category", "country", "blacklisted"],
            "devices": ["device_id", "customer_id", "device_type", "os", "ip_address"],
            "login_history": ["login_id", "device_id", "customer_id", "login_time", "login_status", "ip_address", "country", "city", "is_vpn"],
            "kyc_records": ["kyc_id", "customer_id", "doc_type", "doc_status", "expiry_date", "pep_status", "net_worth"],
            "external_alerts": ["alert_id", "customer_id", "transaction_id", "source_agency", "alert_type", "severity", "alert_time"],
            "aml_watchlist": ["watchlist_id", "customer_id", "status", "reason"],
            "sanctions": ["sanction_id", "entity_name", "country", "sanction_type"],
            "suspicious_locations": ["location_id", "city", "country", "risk_level"],
            "news_events": ["news_id", "entity_name", "news_sentiment", "source", "summary"]
        }
        
        # Check column existence
        for name, cols in required_columns.items():
            df = self.data[name]
            missing_cols = [c for c in cols if c not in df.columns]
            if missing_cols:
                raise DataValidationError(f"Table '{name}' is missing columns: {missing_cols}")
                
            # Verify primary key uniqueness and not null
            pk_map = {
                "customers": "customer_id",
                "accounts": "account_number",
                "transactions": "transaction_id",
                "merchants": "merchant_id",
                "devices": ["device_id", "customer_id"], # Composite PK to allow shared devices
                "login_history": "login_id",
                "kyc_records": "kyc_id",
                "external_alerts": "alert_id",
                "aml_watchlist": "watchlist_id",
                "sanctions": "sanction_id",
                "suspicious_locations": "location_id",
                "news_events": "news_id"
            }
            pk = pk_map[name]
            if isinstance(pk, list):
                if df[pk].isnull().any().any():
                    raise DataValidationError(f"Null values found in composite Primary Key '{pk}' in table '{name}'.")
                if df.duplicated(subset=pk).any():
                    duplicated_rows = df[df.duplicated(subset=pk)][pk].head().to_dict("records")
                    raise DataValidationError(f"Duplicate composite Primary Key values found in '{pk}' in table '{name}': {duplicated_rows}")
            else:
                if df[pk].isnull().any():
                    raise DataValidationError(f"Null values found in Primary Key '{pk}' in table '{name}'.")
                if df[pk].duplicated().any():
                    duplicated_pks = df[df[pk].duplicated()][pk].tolist()
                    raise DataValidationError(f"Duplicate Primary Key values found in '{pk}' in table '{name}': {duplicated_pks[:5]}")

    def validate_referential_integrity(self):
        """Verifies all Foreign Key relationships match existing Primary Keys."""
        # 1. Accounts -> Customers (customer_id)
        self._check_fk("accounts", "customer_id", "customers", "customer_id")
        
        # 2. Transactions -> Accounts (account_number)
        self._check_fk("transactions", "account_number", "accounts", "account_number")
        
        # 3. Transactions -> Merchants (merchant_id)
        self._check_fk("transactions", "merchant_id", "merchants", "merchant_id")
        
        # 4. Devices -> Customers (customer_id)
        self._check_fk("devices", "customer_id", "customers", "customer_id")
        
        # 5. Login History -> Customers (customer_id)
        self._check_fk("login_history", "customer_id", "customers", "customer_id")
        
        # 6. Login History -> Devices (device_id)
        self._check_fk("login_history", "device_id", "devices", "device_id")
        
        # 7. KYC Records -> Customers (customer_id)
        self._check_fk("kyc_records", "customer_id", "customers", "customer_id")
        
        # 8. External Alerts -> Customers (customer_id)
        self._check_fk("external_alerts", "customer_id", "customers", "customer_id")
        
        # 9. AML Watchlist -> Customers (customer_id)
        self._check_fk("aml_watchlist", "customer_id", "customers", "customer_id")
        
        # 10. External Alerts -> Transactions (transaction_id, allow nulls)
        self._check_fk("external_alerts", "transaction_id", "transactions", "transaction_id", allow_null=True)

    def _check_fk(self, child_table: str, child_col: str, parent_table: str, parent_col: str, allow_null: bool = False):
        child_df = self.data[child_table]
        parent_df = self.data[parent_table]
        
        child_series = child_df[child_col]
        if allow_null:
            child_series = child_series.dropna()
            
        parent_keys = set(parent_df[parent_col])
        invalid_fks = child_series[~child_series.isin(parent_keys)].unique()
        
        if len(invalid_fks) > 0:
            raise DataValidationError(
                f"Referential Integrity Breach: Foreign key '{child_col}' in '{child_table}' "
                f"contains values not found in parent table '{parent_table}'('{parent_col}'): {list(invalid_fks[:5])}"
            )
            
if __name__ == "__main__":
    # Self-test when run directly
    try:
        loader = DataLoader()
        data = loader.load_all()
        print("Success! Datasets summary:")
        for k, v in data.items():
            print(f" - {k}: {v.shape[0]} rows, {v.shape[1]} columns")
    except Exception as e:
        print(f"Error: {e}")
