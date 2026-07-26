import pytest
import pandas as pd
from datetime import datetime, timedelta
from risk_engine import RiskEngine

@pytest.fixture
def base_mock_data():
    """Generates a minimal valid base dataset for mocking rules testing."""
    customers = pd.DataFrame([{
        "customer_id": "CUST-0001",
        "full_name": "Test Subject",
        "email": "test@subject.com",
        "phone": "555-0100",
        "address": "123 Test St",
        "residence_country": "United States",
        "customer_age": 35
    }])
    
    accounts = pd.DataFrame([{
        "account_number": "ACC-0001",
        "customer_id": "CUST-0001",
        "account_type": "Savings",
        "open_date": "2024-01-01",
        "balance": 100000.0,
        "status": "ACTIVE"
    }])
    
    merchants = pd.DataFrame([
        {"merchant_id": "M-99", "merchant_name": "Standard Store", "category": "Retail", "country": "United States", "blacklisted": False},
        {"merchant_id": "M-CRYP", "merchant_name": "MockExchange", "category": "Crypto Exchange", "country": "United States", "blacklisted": False},
        {"merchant_id": "M-BLACK", "merchant_name": "Mixer Services", "category": "Crypto Exchange", "country": "Russia", "blacklisted": True}
    ])
    
    devices = pd.DataFrame([{
        "device_id": "DEV-0001",
        "customer_id": "CUST-0001",
        "device_type": "Mobile",
        "os": "iOS",
        "ip_address": "192.168.1.1"
    }])
    
    login_history = pd.DataFrame([{
        "login_id": "LOG-0001",
        "device_id": "DEV-0001",
        "customer_id": "CUST-0001",
        "login_time": "2024-01-02 10:00:00",
        "login_status": "SUCCESS",
        "ip_address": "192.168.1.1",
        "country": "United States",
        "city": "New York",
        "is_vpn": False
    }])
    
    kyc_records = pd.DataFrame([{
        "kyc_id": "KYC-0001",
        "customer_id": "CUST-0001",
        "doc_type": "Passport",
        "doc_status": "VERIFIED",
        "expiry_date": "2028-01-01",
        "pep_status": "NO",
        "net_worth": 500000
    }])
    
    external_alerts = pd.DataFrame(columns=["alert_id", "customer_id", "transaction_id", "source_agency", "alert_type", "severity", "alert_time"])
    aml_watchlist = pd.DataFrame(columns=["watchlist_id", "customer_id", "status", "reason"])
    sanctions = pd.DataFrame(columns=["sanction_id", "entity_name", "country", "sanction_type"])
    suspicious_locations = pd.DataFrame(columns=["location_id", "city", "country", "risk_level"])
    news_events = pd.DataFrame(columns=["news_id", "entity_name", "news_sentiment", "source", "summary"])
    transactions = pd.DataFrame(columns=["transaction_id", "account_number", "transaction_time", "amount", "merchant_id", "transaction_type", "transaction_status", "ip_address", "location_city", "location_country"])
    
    return {
        "customers": customers,
        "accounts": accounts,
        "transactions": transactions,
        "merchants": merchants,
        "devices": devices,
        "login_history": login_history,
        "kyc_records": kyc_records,
        "external_alerts": external_alerts,
        "aml_watchlist": aml_watchlist,
        "sanctions": sanctions,
        "suspicious_locations": suspicious_locations,
        "news_events": news_events
    }

def test_rule_large_transaction(base_mock_data):
    """Ensure R01_LARGE_TRANSACTION flags transaction amounts over $50,000."""
    data = base_mock_data
    # Create transaction over $50,000
    data["transactions"] = pd.DataFrame([{
        "transaction_id": "TX-0001",
        "account_number": "ACC-0001",
        "transaction_time": "2024-01-02 12:00:00",
        "amount": 55000.0,
        "merchant_id": "M-99",
        "transaction_type": "TRANSFER",
        "transaction_status": "COMPLETED",
        "ip_address": "192.168.1.1",
        "location_city": "New York",
        "location_country": "United States"
    }])
    
    engine = RiskEngine(data)
    results = engine.evaluate_all_rules()
    
    assert "CUST-0001" in results
    rules = [r["rule_id"] for r in results["CUST-0001"]]
    assert "R01_LARGE_TRANSACTION" in rules

def test_rule_structuring(base_mock_data):
    """Ensure R03_STRUCTURING flags rapid transactions just below the $10,000 threshold."""
    data = base_mock_data
    # Create 3 transactions of $9,950 within 4 hours
    data["transactions"] = pd.DataFrame([
        {"transaction_id": "TX-0001", "account_number": "ACC-0001", "transaction_time": "2024-01-02 12:00:00", "amount": 9950.0, "merchant_id": "M-99", "transaction_type": "DEPOSIT", "transaction_status": "COMPLETED", "ip_address": "192.168.1.1", "location_city": "New York", "location_country": "United States"},
        {"transaction_id": "TX-0002", "account_number": "ACC-0001", "transaction_time": "2024-01-02 13:00:00", "amount": 9920.0, "merchant_id": "M-99", "transaction_type": "DEPOSIT", "transaction_status": "COMPLETED", "ip_address": "192.168.1.1", "location_city": "New York", "location_country": "United States"},
        {"transaction_id": "TX-0003", "account_number": "ACC-0001", "transaction_time": "2024-01-02 14:00:00", "amount": 9960.0, "merchant_id": "M-99", "transaction_type": "DEPOSIT", "transaction_status": "COMPLETED", "ip_address": "192.168.1.1", "location_city": "New York", "location_country": "United States"}
    ])
    
    engine = RiskEngine(data)
    results = engine.evaluate_all_rules()
    
    assert "CUST-0001" in results
    rules = [r["rule_id"] for r in results["CUST-0001"]]
    assert "R03_STRUCTURING" in rules

def test_rule_impossible_travel(base_mock_data):
    """Ensure R14_IMPOSSIBLE_TRAVEL flags logins occurring at velocity > 800 km/h."""
    data = base_mock_data
    # First login in NY, second login 15 mins later in London
    data["login_history"] = pd.DataFrame([
        {"login_id": "LOG-0001", "device_id": "DEV-0001", "customer_id": "CUST-0001", "login_time": "2024-01-02 10:00:00", "login_status": "SUCCESS", "ip_address": "104.244.42.1", "country": "United States", "city": "New York", "is_vpn": False},
        {"login_id": "LOG-0002", "device_id": "DEV-0001", "customer_id": "CUST-0001", "login_time": "2024-01-02 10:15:00", "login_status": "SUCCESS", "ip_address": "25.192.12.3", "country": "United Kingdom", "city": "London", "is_vpn": False}
    ])
    
    engine = RiskEngine(data)
    results = engine.evaluate_all_rules()
    
    assert "CUST-0001" in results
    rules = [r["rule_id"] for r in results["CUST-0001"]]
    assert "R14_IMPOSSIBLE_TRAVEL" in rules
