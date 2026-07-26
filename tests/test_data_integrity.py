import os
import pytest
import pandas as pd
from config.config import FILE_PATHS
from loader import DataLoader, DataValidationError

def test_generated_files_exist():
    """Ensure all required input CSV and JSON files exist in the data directory."""
    for key, path in FILE_PATHS.items():
        if key == "risk_scores":
            continue
        assert os.path.exists(path), f"Missing database file: {path}. Please run generate_data.py first."

def test_loader_validates_successfully():
    """Ensure DataLoader can parse and validate all files without structure or integrity errors."""
    try:
        loader = DataLoader()
        data = loader.load_all()
        assert len(data) == 12
        assert "customers" in data
        assert "transactions" in data
    except DataValidationError as e:
        pytest.fail(f"Data validation failed unexpectedly: {e}")

def test_customer_count_and_distribution():
    """Ensure customer record counts match design parameters."""
    cust_df = pd.read_csv(FILE_PATHS["customers"])
    assert len(cust_df) >= 500, "Should generate at least 500 customers."

def test_referential_integrity_violations():
    """Deliberately modify foreign keys to ensure the DataLoader catches integrity breaches."""
    loader = DataLoader()
    data = loader.load_all()
    
    # Introduce an orphaned customer ID into the accounts table
    original_accounts = data["accounts"].copy()
    data["accounts"].loc[0, "customer_id"] = "CUST-99999" # Orphaned ID
    
    with pytest.raises(DataValidationError) as excinfo:
        loader.validate_referential_integrity()
    assert "Referential Integrity Breach" in str(excinfo.value)
