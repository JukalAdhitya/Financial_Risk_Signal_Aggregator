import os
import random
import json
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from faker import Faker

# Import config parameters
from config.config import (
    FILE_PATHS, 
    GENERATED_DATA_DIR, 
    SANCTIONED_COUNTRIES, 
    HIGH_RISK_COUNTRIES, 
    STABLE_COUNTRIES, 
    ALL_COUNTRIES
)

# Set seeds for reproducibility
random.seed(42)
np.random.seed(42)
fake = Faker()
Faker.seed(42)

# Ensure folders exist
os.makedirs(GENERATED_DATA_DIR, exist_ok=True)

# Define target row counts
NUM_CUSTOMERS = 500
NUM_ACCOUNTS = 800
NUM_TRANSACTIONS = 10000
NUM_MERCHANTS = 250
NUM_DEVICES = 750
NUM_LOGINS = 6000
NUM_KYC = 500
NUM_EXTERNAL_ALERTS = 200
NUM_WATCHLIST = 30
NUM_SANCTIONS = 25
NUM_SUSPICIOUS_LOCS = 50
NUM_NEWS = 100

# --- 1. SANCTIONS DATA ---
def generate_sanctions():
    print("Generating Sanctions...")
    sanctions_list = []
    # Pre-populate some specific entities
    entities = [
        "Al-Barakaat", "Cariano Bank", "Vnesheconombank", "Al-Aqsa Foundation",
        "Sberbank Russia", "Rosneft", "Nord Stream AG", "Jihad Money Transfer",
        "Golden Coin Exchange", "CryptoWash Ltd", "Shadow Cargo Corp", "Far East Trade Co"
    ]
    for i in range(NUM_SANCTIONS):
        entity = entities[i % len(entities)] if i < len(entities) else fake.company() + " Import/Export"
        country = random.choice(SANCTIONED_COUNTRIES)
        sanctions_list.append({
            "sanction_id": f"SANC-{i+1:04d}",
            "entity_name": entity,
            "country": country,
            "sanction_type": random.choice(["OFAC Sanctions List", "EU Financial Sanctions", "UN Watchlist"])
        })
    df = pd.DataFrame(sanctions_list)
    df.to_csv(FILE_PATHS["sanctions"], index=False)
    return df

# --- 2. SUSPICIOUS LOCATIONS ---
def generate_suspicious_locations():
    print("Generating Suspicious Locations...")
    locs = []
    cities = [
        ("Caracas", "Venezuela"), ("Mogadishu", "Somalia"), ("Sanaa", "Yemen"),
        ("Kabul", "Afghanistan"), ("Yangon", "Myanmar"), ("Baghdad", "Iraq"),
        ("Tripoli", "Libya"), ("Tehran", "Iran"), ("Pyongyang", "North Korea"),
        ("Damascus", "Syria"), ("Moscow", "Russia"), ("Minsk", "Belarus"),
        ("Panama City", "Panama"), ("Cayman Islands", "Cayman Islands"),
        ("Nassau", "Bahamas"), ("Zurich", "Switzerland"), ("Macau", "Macau"),
        ("Nicosia", "Cyprus"), ("Gibraltar", "Gibraltar"), ("Valletta", "Malta")
    ]
    for i in range(NUM_SUSPICIOUS_LOCS):
        if i < len(cities):
            city, country = cities[i]
        else:
            city = fake.city()
            country = random.choice(HIGH_RISK_COUNTRIES + ["Panama", "Cyprus", "Malta"])
        
        locs.append({
            "location_id": f"LOC-{i+1:04d}",
            "city": city,
            "country": country,
            "risk_level": "HIGH" if country in HIGH_RISK_COUNTRIES or country in SANCTIONED_COUNTRIES else "MEDIUM"
        })
    df = pd.DataFrame(locs)
    df.to_csv(FILE_PATHS["suspicious_locations"], index=False)
    return df

# --- 3. MERCHANTS DATA ---
def generate_merchants():
    print("Generating Merchants...")
    merchants = []
    categories = ["Retail", "Groceries", "Dining", "Travel", "Crypto Exchange", "Casino & Gambling", "Pawn Shop", "Digital Services"]
    
    # Ensure some blacklisted ones
    for i in range(NUM_MERCHANTS):
        category = random.choices(
            categories,
            weights=[35, 25, 15, 10, 5, 4, 3, 3],
            k=1
        )[0]
        
        name = fake.company()
        if category == "Crypto Exchange":
            name = random.choice(["CoinBase-Mock", "Binance-Mock", "BitStamp-Mock", "CryptoWash", "CoinMixer"])
        elif category == "Casino & Gambling":
            name = name + " Casino"
        elif category == "Pawn Shop":
            name = name + " Pawnbrokers"
            
        country = random.choices(
            [random.choice(STABLE_COUNTRIES), random.choice(HIGH_RISK_COUNTRIES), random.choice(SANCTIONED_COUNTRIES)],
            weights=[85, 10, 5],
            k=1
        )[0]
        
        # Blacklisted rules: Crypto mixer or sanctioned country/entity
        blacklisted = False
        if name in ["CryptoWash", "CoinMixer"] or country in SANCTIONED_COUNTRIES:
            blacklisted = True
            
        merchants.append({
            "merchant_id": f"MERCH-{i+1:04d}",
            "merchant_name": name,
            "category": category,
            "country": country,
            "blacklisted": blacklisted
        })
    df = pd.DataFrame(merchants)
    df.to_csv(FILE_PATHS["merchants"], index=False)
    return df

# --- 4. CUSTOMERS DATA ---
def generate_customers():
    print("Generating Customers...")
    customers = []
    
    # Assign target risk segments
    # 75% Low Risk, 15% Medium Risk, 8% High Risk, 2% Critical Risk
    segments = ["LOW"] * 375 + ["MEDIUM"] * 75 + ["HIGH"] * 40 + ["CRITICAL"] * 10
    random.shuffle(segments)
    
    for i in range(NUM_CUSTOMERS):
        prof = segments[i]
        
        # Select residency country based on profile
        if prof == "CRITICAL":
            country = random.choices([random.choice(STABLE_COUNTRIES), random.choice(SANCTIONED_COUNTRIES)], weights=[70, 30])[0]
        elif prof == "HIGH":
            country = random.choices([random.choice(STABLE_COUNTRIES), random.choice(HIGH_RISK_COUNTRIES)], weights=[80, 20])[0]
        else:
            country = random.choice(STABLE_COUNTRIES)
            
        age = random.choices(
            [random.randint(18, 70), random.randint(71, 95), random.randint(12, 17)],
            weights=[90, 8, 2] # minor or senior risk plants
        )[0]
        
        customers.append({
            "customer_id": f"CUST-{i+1:04d}",
            "full_name": fake.name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "address": fake.address().replace("\n", ", "),
            "residence_country": country,
            "risk_profile": prof, # For internal logic only, not visible to the risk engine directly
            "customer_age": age
        })
    df = pd.DataFrame(customers)
    # We will remove 'risk_profile' from the saved customers.csv to make the risk engine evaluate purely from signals,
    # but let's keep it in the dataframe object returned by this function for downstream generators to adapt behavior.
    df.to_csv(FILE_PATHS["customers"], index=False, columns=["customer_id", "full_name", "email", "phone", "address", "residence_country", "customer_age"])
    return df

# --- 5. KYC RECORDS DATA ---
def generate_kyc(customers_df):
    print("Generating KYC Records...")
    kyc = []
    for i, row in customers_df.iterrows():
        cust_id = row["customer_id"]
        prof = row["risk_profile"]
        
        doc_type = random.choice(["Passport", "SSN", "Driving License", "National ID"])
        
        # Plant PEP state
        if prof == "CRITICAL":
            pep = random.choices(["YES", "NO"], weights=[40, 60])[0]
        elif prof == "HIGH":
            pep = random.choices(["YES", "NO"], weights=[20, 80])[0]
        else:
            pep = random.choices(["YES", "NO"], weights=[2, 98])[0]
            
        # Doc Status
        if prof == "CRITICAL":
            status = random.choices(["VERIFIED", "EXPIRED", "FAILED"], weights=[30, 40, 30])[0]
        elif prof == "HIGH":
            status = random.choices(["VERIFIED", "EXPIRED", "PENDING"], weights=[50, 30, 20])[0]
        else:
            status = "VERIFIED"
            
        expiry = datetime.now().date() + timedelta(days=random.randint(30, 1000))
        if status in ["EXPIRED", "FAILED"]:
            expiry = datetime.now().date() - timedelta(days=random.randint(10, 500))
            
        net_worth = random.choices(
            [random.randint(10000, 150000), random.randint(150001, 1000000), random.randint(1000001, 15000000)],
            weights=[70, 25, 5]
        )[0]
        
        kyc.append({
            "kyc_id": f"KYC-{i+1:04d}",
            "customer_id": cust_id,
            "doc_type": doc_type,
            "doc_status": status,
            "expiry_date": expiry.strftime("%Y-%m-%d"),
            "pep_status": pep,
            "net_worth": net_worth
        })
    df = pd.DataFrame(kyc)
    df.to_csv(FILE_PATHS["kyc_records"], index=False)
    return df

# --- 6. ACCOUNTS DATA ---
def generate_accounts(customers_df):
    print("Generating Accounts...")
    accounts = []
    acc_counter = 1
    
    for i, row in customers_df.iterrows():
        cust_id = row["customer_id"]
        prof = row["risk_profile"]
        
        # Normal customers have 1-2 accounts, High/Critical risk might have 2-4 accounts
        num_accs = random.choices([1, 2, 3], weights=[70, 25, 5])[0]
        if prof in ["HIGH", "CRITICAL"]:
            num_accs = random.choices([1, 2, 3, 4], weights=[20, 40, 30, 10])[0]
            
        for _ in range(num_accs):
            acc_type = random.choice(["Savings", "Checking", "Credit Card"])
            open_days = random.randint(30, 3000)
            
            # Plant account age anomaly (new account)
            if prof in ["HIGH", "CRITICAL"] and random.random() < 0.3:
                open_days = random.randint(2, 25)
                
            open_date = datetime.now().date() - timedelta(days=open_days)
            
            # Balances
            balance = float(random.choices(
                [random.randint(100, 10000), random.randint(10001, 100000), random.randint(100001, 5000000)],
                weights=[60, 30, 10]
            )[0])
            
            # Status
            status = "ACTIVE"
            # Plant dormant account reactivation anomaly
            if prof in ["HIGH", "CRITICAL"] and random.random() < 0.2:
                status = "DORMANT"
                
            accounts.append({
                "account_number": f"ACC-{acc_counter:05d}",
                "customer_id": cust_id,
                "account_type": acc_type,
                "open_date": open_date.strftime("%Y-%m-%d"),
                "balance": balance,
                "status": status
            })
            acc_counter += 1
            
    # Force generating at least 800 accounts
    while len(accounts) < NUM_ACCOUNTS:
        row = customers_df.sample(n=1).iloc[0]
        cust_id = row["customer_id"]
        acc_type = random.choice(["Savings", "Checking", "Credit Card"])
        open_date = datetime.now().date() - timedelta(days=random.randint(30, 3000))
        balance = float(random.randint(500, 50000))
        accounts.append({
            "account_number": f"ACC-{acc_counter:05d}",
            "customer_id": cust_id,
            "account_type": acc_type,
            "open_date": open_date.strftime("%Y-%m-%d"),
            "balance": balance,
            "status": "ACTIVE"
        })
        acc_counter += 1
        
    df = pd.DataFrame(accounts)
    df.to_csv(FILE_PATHS["accounts"], index=False)
    return df

# --- 7. DEVICES DATA ---
def generate_devices(customers_df):
    print("Generating Devices...")
    devices = []
    dev_counter = 1
    
    # Store mapping of CUST_ID to device ids
    cust_devices = {}
    
    # Ensure there's a shared device footprint
    # Plant a shared device: Device 111 shared by CUST-0001, CUST-0002, CUST-0003
    shared_device_id = "DEV-9999"
    
    for i, row in customers_df.iterrows():
        cust_id = row["customer_id"]
        prof = row["risk_profile"]
        
        # Low risk: 1 device, High/Critical: multiple devices
        num_devices = random.choices([1, 2], weights=[90, 10])[0]
        if prof in ["HIGH", "CRITICAL"]:
            num_devices = random.choices([2, 3, 4], weights=[40, 45, 15])[0]
            
        cust_devices[cust_id] = []
        for d_idx in range(num_devices):
            d_id = f"DEV-{dev_counter:05d}"
            device_type = random.choice(["Mobile", "Desktop", "Tablet"])
            os_name = random.choice(["iOS", "Android", "Windows", "MacOS"])
            ip = fake.ipv4_public()
            
            devices.append({
                "device_id": d_id,
                "customer_id": cust_id,
                "device_type": device_type,
                "os": os_name,
                "ip_address": ip
            })
            cust_devices[cust_id].append(d_id)
            dev_counter += 1
            
    # Inject Shared Device anomaly
    # Pick 4 critical/high risk customers and force them to use the same device ID
    target_custs = customers_df[customers_df["risk_profile"].isin(["CRITICAL", "HIGH"])]["customer_id"].head(4).tolist()
    if len(target_custs) >= 3:
        for c in target_custs:
            devices.append({
                "device_id": shared_device_id,
                "customer_id": c,
                "device_type": "Mobile",
                "os": "Android",
                "ip_address": "198.51.100.42"
            })
            cust_devices[c].append(shared_device_id)
            
    # Force generating ~750 devices
    while len(devices) < NUM_DEVICES:
        cust_row = customers_df.sample(n=1).iloc[0]
        c_id = cust_row["customer_id"]
        d_id = f"DEV-{dev_counter:05d}"
        devices.append({
            "device_id": d_id,
            "customer_id": c_id,
            "device_type": random.choice(["Mobile", "Desktop"]),
            "os": random.choice(["iOS", "Windows"]),
            "ip_address": fake.ipv4_public()
        })
        cust_devices[c_id].append(d_id)
        dev_counter += 1
        
    df = pd.DataFrame(devices)
    df.to_csv(FILE_PATHS["devices"], index=False)
    return df, cust_devices

# --- 8. LOGIN HISTORY DATA ---
def generate_logins(customers_df, cust_devices):
    print("Generating Login History...")
    logins = []
    login_counter = 1
    
    # Impossible travel locations catalog
    cities_coords = [
        {"city": "New York", "country": "United States", "ip": "104.244.42.1"},
        {"city": "London", "country": "United Kingdom", "ip": "25.192.12.3"},
        {"city": "Tokyo", "country": "Japan", "ip": "120.50.32.9"},
        {"city": "Moscow", "country": "Russia", "ip": "95.165.120.4"}
    ]
    
    for i, row in customers_df.iterrows():
        cust_id = row["customer_id"]
        prof = row["risk_profile"]
        res_country = row["residence_country"]
        devices_list = cust_devices.get(cust_id, ["DEV-00001"])
        
        # Low risk: ~8 logins, Medium: ~12, High/Critical: ~25
        num_logs = random.randint(5, 10)
        if prof == "MEDIUM":
            num_logs = random.randint(10, 18)
        elif prof in ["HIGH", "CRITICAL"]:
            num_logs = random.randint(20, 40)
            
        base_time = datetime.now() - timedelta(days=60)
        
        for l_idx in range(num_logs):
            dev_id = random.choice(devices_list)
            base_time += timedelta(hours=random.randint(12, 48))
            
            status = "SUCCESS"
            ip = fake.ipv4_public()
            vpn = random.choices([True, False], weights=[3, 97])[0]
            country = res_country
            city = fake.city()
            
            # Plant profiles
            if prof == "HIGH":
                # Occasional VPN
                vpn = random.choices([True, False], weights=[20, 80])[0]
                # Failed logins
                if random.random() < 0.15:
                    status = "FAILED"
                # Foreign login
                if random.random() < 0.2:
                    country = random.choice(STABLE_COUNTRIES)
                    while country == res_country:
                        country = random.choice(STABLE_COUNTRIES)
            elif prof == "CRITICAL":
                # Multiple failed logins in a row
                if random.random() < 0.3:
                    # failed streak
                    for f in range(3):
                        logins.append({
                            "login_id": f"LOG-{login_counter:05d}",
                            "device_id": dev_id,
                            "customer_id": cust_id,
                            "login_time": (base_time - timedelta(minutes=5*(3-f))).strftime("%Y-%m-%d %H:%M:%S"),
                            "login_status": "FAILED",
                            "ip_address": fake.ipv4_public(),
                            "country": res_country,
                            "city": city,
                            "is_vpn": vpn
                        })
                        login_counter += 1
                
                # Sanction country login
                if random.random() < 0.25:
                    country = random.choice(SANCTIONED_COUNTRIES)
                    city = "SanctionCity"
                
                # VPN login
                vpn = random.choices([True, False], weights=[50, 50])[0]
                
            logins.append({
                "login_id": f"LOG-{login_counter:05d}",
                "device_id": dev_id,
                "customer_id": cust_id,
                "login_time": base_time.strftime("%Y-%m-%d %H:%M:%S"),
                "login_status": status,
                "ip_address": ip,
                "country": country,
                "city": city,
                "is_vpn": vpn
            })
            login_counter += 1
            
            # Plant Impossible Travel anomaly for critical risk customers
            if prof == "CRITICAL" and l_idx == num_logs - 2:
                # Add two consecutive logins within 1 hour in New York and London
                travel_time = base_time + timedelta(minutes=30)
                # First: New York
                logins.append({
                    "login_id": f"LOG-{login_counter:05d}",
                    "device_id": dev_id,
                    "customer_id": cust_id,
                    "login_time": travel_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "login_status": "SUCCESS",
                    "ip_address": cities_coords[0]["ip"],
                    "country": cities_coords[0]["country"],
                    "city": cities_coords[0]["city"],
                    "is_vpn": False
                })
                login_counter += 1
                
                # Second: London, 15 minutes later (Impossible speed!)
                logins.append({
                    "login_id": f"LOG-{login_counter:05d}",
                    "device_id": dev_id,
                    "customer_id": cust_id,
                    "login_time": (travel_time + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
                    "login_status": "SUCCESS",
                    "ip_address": cities_coords[1]["ip"],
                    "country": cities_coords[1]["country"],
                    "city": cities_coords[1]["city"],
                    "is_vpn": False
                })
                login_counter += 1
                base_time = travel_time + timedelta(hours=2) # skip ahead
                
    # Scale up / trim to target ~6000 records
    while len(logins) < NUM_LOGINS:
        cust_row = customers_df.sample(n=1).iloc[0]
        c_id = cust_row["customer_id"]
        devs = cust_devices.get(c_id, ["DEV-00001"])
        logins.append({
            "login_id": f"LOG-{login_counter:05d}",
            "device_id": random.choice(devs),
            "customer_id": c_id,
            "login_time": (datetime.now() - timedelta(days=random.randint(1, 40))).strftime("%Y-%m-%d %H:%M:%S"),
            "login_status": "SUCCESS",
            "ip_address": fake.ipv4_public(),
            "country": cust_row["residence_country"],
            "city": fake.city(),
            "is_vpn": False
        })
        login_counter += 1
        
    df = pd.DataFrame(logins)
    df.to_csv(FILE_PATHS["login_history"], index=False)
    return df

# --- 9. TRANSACTIONS DATA ---
def generate_transactions(accounts_df, customers_df, merchants_df):
    print("Generating Transactions...")
    txs = []
    tx_counter = 1
    
    # Index accounts and customers for fast retrieval
    custs_by_id = customers_df.set_index("customer_id")
    accs_by_cust = accounts_df.groupby("customer_id")
    
    # Store list of active/dormant accounts and reference mappings
    # Find accounts and merchants
    crypto_merchants = merchants_df[merchants_df["category"] == "Crypto Exchange"]["merchant_id"].tolist()
    cash_merchants = merchants_df[merchants_df["category"].isin(["Casino & Gambling", "Pawn Shop"])]["merchant_id"].tolist()
    blacklisted_merchants = merchants_df[merchants_df["blacklisted"] == True]["merchant_id"].tolist()
    standard_merchants = merchants_df[~merchants_df["merchant_id"].isin(crypto_merchants + cash_merchants + blacklisted_merchants)]["merchant_id"].tolist()
    
    # Distribute transaction logs
    # Group customers to map transaction frequencies
    for cust_id, row in customers_df.iterrows():
        c_id = row["customer_id"]
        prof = row["risk_profile"]
        res_country = row["residence_country"]
        
        # Get customer's accounts
        if c_id not in accs_by_cust.groups:
            continue
        c_accs = accs_by_cust.get_group(c_id)
        
        # Determine frequency
        num_txs = random.randint(10, 20)
        if prof == "MEDIUM":
            num_txs = random.randint(25, 45)
        elif prof in ["HIGH", "CRITICAL"]:
            num_txs = random.randint(60, 90)
            
        base_time = datetime.now() - timedelta(days=60)
        
        for t_idx in range(num_txs):
            acc_row = c_accs.sample(n=1).iloc[0]
            acc_num = acc_row["account_number"]
            acc_status = acc_row["status"]
            
            # Timestamps
            base_time += timedelta(minutes=random.randint(60, 2880))
            if base_time > datetime.now():
                break
                
            # Type & status
            tx_type = random.choice(["TRANSFER", "DEPOSIT", "WITHDRAWAL", "PAYMENT"])
            status = "COMPLETED"
            
            # Select amount & merchant based on risk profile
            amount = float(random.randint(5, 500))
            merchant_id = random.choice(standard_merchants)
            dest_country = res_country
            city = fake.city()
            
            # Anomalies behavior injections
            if prof == "LOW":
                # Standard regular domestic spending
                pass
            elif prof == "MEDIUM":
                # Moderate amount, occasional high-value, occasional foreign merchant
                if random.random() < 0.1:
                    amount = float(random.randint(1000, 4500))
                if random.random() < 0.1:
                    merchant_id = random.choice(standard_merchants)
                    merch_row = merchants_df[merchants_df["merchant_id"] == merchant_id].iloc[0]
                    dest_country = merch_row["country"]
            elif prof == "HIGH":
                # Crypto transactions
                if random.random() < 0.25 and len(crypto_merchants) > 0:
                    merchant_id = random.choice(crypto_merchants)
                    amount = float(random.randint(500, 9500))
                # Higher amounts
                if random.random() < 0.15:
                    amount = float(random.randint(10000, 25000))
                # Failed transactions
                if random.random() < 0.1:
                    status = "FAILED"
            elif prof == "CRITICAL":
                # Structuring anomaly: multiple transactions of exact $9,900 to $9,980 in short window
                # Let's plant structuring for 5 of the critical customers
                if t_idx == 10 and random.random() < 0.7:
                    structuring_time = base_time
                    for s in range(3):
                        txs.append({
                            "transaction_id": f"TX-{tx_counter:06d}",
                            "account_number": acc_num,
                            "transaction_time": (structuring_time + timedelta(hours=3*s)).strftime("%Y-%m-%d %H:%M:%S"),
                            "amount": float(random.randint(9900, 9980)), # structuring below 10,000 threshold
                            "merchant_id": random.choice(standard_merchants),
                            "transaction_type": "DEPOSIT",
                            "transaction_status": "COMPLETED",
                            "ip_address": fake.ipv4_public(),
                            "location_city": city,
                            "location_country": res_country
                        })
                        tx_counter += 1
                    base_time = structuring_time + timedelta(days=2) # advance time
                
                # Sanction country transaction
                if random.random() < 0.25:
                    dest_country = random.choice(SANCTIONED_COUNTRIES)
                    merchant_id = random.choice(blacklisted_merchants) if len(blacklisted_merchants) > 0 else random.choice(standard_merchants)
                    amount = float(random.randint(500, 15000))
                
                # Off hours transaction
                if random.random() < 0.2:
                    # force middle of night 2:00 AM
                    off_time = datetime(base_time.year, base_time.month, base_time.day, 2, random.randint(10, 50))
                    txs.append({
                        "transaction_id": f"TX-{tx_counter:06d}",
                        "account_number": acc_num,
                        "transaction_time": off_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": float(random.randint(25000, 60000)), # Large amount
                        "merchant_id": random.choice(standard_merchants),
                        "transaction_type": "TRANSFER",
                        "transaction_status": "COMPLETED",
                        "ip_address": fake.ipv4_public(),
                        "location_city": city,
                        "location_country": res_country
                    })
                    tx_counter += 1
                
                # Blacklisted merchant
                if random.random() < 0.2 and len(blacklisted_merchants) > 0:
                    merchant_id = random.choice(blacklisted_merchants)
                    amount = float(random.randint(100, 8000))
                    
                # Round number payments
                if random.random() < 0.15:
                    amount = float(random.choice([10000.0, 15000.0, 20000.0, 25000.0, 50000.0]))
                    
            # Plant Dormant Account suddenly active
            if acc_status == "DORMANT" and t_idx > 5:
                # Add large transaction
                amount = float(random.randint(40000, 80000))
                tx_type = "TRANSFER"
            
            txs.append({
                "transaction_id": f"TX-{tx_counter:06d}",
                "account_number": acc_num,
                "transaction_time": base_time.strftime("%Y-%m-%d %H:%M:%S"),
                "amount": amount,
                "merchant_id": merchant_id,
                "transaction_type": tx_type,
                "transaction_status": status,
                "ip_address": fake.ipv4_public(),
                "location_city": city,
                "location_country": dest_country
            })
            tx_counter += 1
            
            # Plant Account Takeover (ATO) Indicators
            # Coordinated sequence: new login at odd time + instant large withdrawal
            if prof == "CRITICAL" and t_idx == 15:
                ato_time = base_time + timedelta(minutes=5)
                # instant withdrawal
                txs.append({
                    "transaction_id": f"TX-{tx_counter:06d}",
                    "account_number": acc_num,
                    "transaction_time": ato_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "amount": float(random.randint(48000, 49900)), # Close to account limit
                    "merchant_id": random.choice(crypto_merchants) if len(crypto_merchants) > 0 else merchant_id,
                    "transaction_type": "WITHDRAWAL",
                    "transaction_status": "COMPLETED",
                    "ip_address": "198.51.100.42", # same as shared device / VPN login IP
                    "location_city": "Mogadishu",
                    "location_country": "Somalia"
                })
                tx_counter += 1
                base_time = ato_time + timedelta(hours=12)

    # Scale up / trim to target ~10000 transactions
    while len(txs) < NUM_TRANSACTIONS:
        acc_row = accounts_df.sample(n=1).iloc[0]
        acc_num = acc_row["account_number"]
        cust_row = customers_df[customers_df["customer_id"] == acc_row["customer_id"]].iloc[0]
        txs.append({
            "transaction_id": f"TX-{tx_counter:06d}",
            "account_number": acc_num,
            "transaction_time": (datetime.now() - timedelta(days=random.randint(1, 40))).strftime("%Y-%m-%d %H:%M:%S"),
            "amount": float(random.randint(10, 2000)),
            "merchant_id": random.choice(standard_merchants),
            "transaction_type": random.choice(["TRANSFER", "PAYMENT", "WITHDRAWAL"]),
            "transaction_status": "COMPLETED",
            "ip_address": fake.ipv4_public(),
            "location_city": fake.city(),
            "location_country": cust_row["residence_country"]
        })
        tx_counter += 1
        
    df = pd.DataFrame(txs)
    df.to_csv(FILE_PATHS["transactions"], index=False)
    return df

# --- 10. EXTERNAL ALERTS DATA ---
def generate_external_alerts(customers_df, transactions_df):
    print("Generating External Alerts...")
    alerts = []
    alert_counter = 1
    
    # Pick transactions to attach alerts to (to ensure relational integrity)
    c_indices = customers_df.set_index("customer_id")
    
    for i in range(NUM_EXTERNAL_ALERTS):
        # Pick random high or critical risk customers to cluster alerts
        sample_cust_row = customers_df.sample(n=1).iloc[0]
        c_id = sample_cust_row["customer_id"]
        prof = sample_cust_row["risk_profile"]
        
        # Prefer critical/high risk customers
        if prof not in ["HIGH", "CRITICAL"] and random.random() < 0.7:
            # try again to skew it
            sample_cust_row = customers_df[customers_df["risk_profile"].isin(["HIGH", "CRITICAL"])].sample(n=1).iloc[0]
            c_id = sample_cust_row["customer_id"]
            
        # Get customer's accounts and transactions
        # Find transactions mapping to the customer's accounts
        cust_accs = pd.read_csv(FILE_PATHS["accounts"])
        cust_acc_nums = cust_accs[cust_accs["customer_id"] == c_id]["account_number"].tolist()
        cust_txs = transactions_df[transactions_df["account_number"].isin(cust_acc_nums)]
        
        tx_id = ""
        if len(cust_txs) > 0:
            tx_id = cust_txs.sample(n=1).iloc[0]["transaction_id"]
            
        source = random.choice(["FinCEN", "OFAC", "Interpol", "FIU", "National Crime Agency"])
        a_type = random.choice(["Suspicious Activity Report", "Structuring Warning", "Card Fraud Alert", "High-Risk Merchant Interaction"])
        severity = random.choice(["MEDIUM", "HIGH", "CRITICAL"])
        if prof == "CRITICAL":
            severity = "CRITICAL"
        elif prof == "LOW":
            severity = "MEDIUM"
            
        alerts.append({
            "alert_id": f"ALERT-{alert_counter:04d}",
            "customer_id": c_id,
            "transaction_id": tx_id if tx_id != "" else np.nan,
            "source_agency": source,
            "alert_type": a_type,
            "severity": severity,
            "alert_time": (datetime.now() - timedelta(days=random.randint(1, 55))).strftime("%Y-%m-%d %H:%M:%S")
        })
        alert_counter += 1
        
    df = pd.DataFrame(alerts)
    df.to_csv(FILE_PATHS["external_alerts"], index=False)
    return df

# --- 11. AML WATCHLIST DATA ---
def generate_aml_watchlist(customers_df):
    print("Generating AML Watchlist...")
    watchlist = []
    
    # Fetch critical risk customers to populate
    crit_custs = customers_df[customers_df["risk_profile"] == "CRITICAL"]["customer_id"].tolist()
    high_custs = customers_df[customers_df["risk_profile"] == "HIGH"]["customer_id"].tolist()
    
    wl_counter = 1
    # First, matching critical risk customers
    for c_id in crit_custs:
        watchlist.append({
            "watchlist_id": f"WL-{wl_counter:04d}",
            "customer_id": c_id,
            "status": "ACTIVE",
            "reason": random.choice(["OFAC SDN list match", "Known money mule network connection", "Structuring indicator warning"])
        })
        wl_counter += 1
        
    # Then add some high risk customers
    for c_id in high_custs[:10]:
        watchlist.append({
            "watchlist_id": f"WL-{wl_counter:04d}",
            "customer_id": c_id,
            "status": "ACTIVE",
            "reason": random.choice(["PEP associated account monitoring", "Repeated suspicious structuring flags"])
        })
        wl_counter += 1
        
    # Standardize to ~30 entries
    while len(watchlist) < NUM_WATCHLIST:
        c_id = customers_df.sample(n=1).iloc[0]["customer_id"]
        # check if already added
        if not any(x["customer_id"] == c_id for x in watchlist):
            watchlist.append({
                "watchlist_id": f"WL-{wl_counter:04d}",
                "customer_id": c_id,
                "status": "RESOLVED" if random.random() < 0.7 else "ACTIVE",
                "reason": "False positive match on name spelling"
            })
            wl_counter += 1
            
    df = pd.DataFrame(watchlist)
    df.to_csv(FILE_PATHS["aml_watchlist"], index=False)
    return df

# --- 12. NEWS EVENTS DATA ---
def generate_news_events(customers_df, merchants_df):
    print("Generating News Events...")
    news = []
    news_id_counter = 1
    
    # Pick some high risk / critical customer names
    crit_cust_names = customers_df[customers_df["risk_profile"] == "CRITICAL"]["full_name"].tolist()
    high_cust_names = customers_df[customers_df["risk_profile"] == "HIGH"]["full_name"].tolist()
    crypto_merchant_names = merchants_df[merchants_df["category"] == "Crypto Exchange"]["merchant_name"].tolist()
    
    # Inject negative news articles on critical customers
    for name in crit_cust_names:
        news.append({
            "news_id": f"NEWS-{news_id_counter:04d}",
            "entity_name": name,
            "news_sentiment": "NEGATIVE",
            "source": random.choice(["Bloomberg", "Reuters", "Financial Times"]),
            "summary": f"Federal authorities open inquiry into financial transactions of {name} due to suspected asset concealment."
        })
        news_id_counter += 1
        
    for name in high_cust_names[:5]:
        news.append({
            "news_id": f"NEWS-{news_id_counter:04d}",
            "entity_name": name,
            "news_sentiment": "NEGATIVE",
            "source": "Wall Street Journal",
            "summary": f"Regulatory audit finds undisclosed PEP relations linking back to accounts managed by {name}."
        })
        news_id_counter += 1
        
    # Add negative news on crypto mixers
    for m_name in ["CryptoWash", "CoinMixer"]:
        news.append({
            "news_id": f"NEWS-{news_id_counter:04d}",
            "entity_name": m_name,
            "news_sentiment": "NEGATIVE",
            "source": "Coindesk",
            "summary": f"FinCEN blocks operations of {m_name} charging them with laundering over $50M in crypto tokens."
        })
        news_id_counter += 1
        
    # Scale up with neutral/positive news
    sources = ["Reuters", "Bloomberg", "Wall Street Journal", "Financial Times", "New York Times"]
    while len(news) < NUM_NEWS:
        # standard random name or business name
        entity = random.choice([fake.name(), fake.company(), random.choice(crypto_merchant_names) if len(crypto_merchant_names) > 0 else fake.company()])
        sentiment = random.choice(["NEUTRAL", "POSITIVE", "NEGATIVE"])
        summary = ""
        if sentiment == "POSITIVE":
            summary = f"{entity} announces record quarterly growth and expansion into European markets."
        elif sentiment == "NEGATIVE":
            summary = f"Class-action lawsuit filed against {entity} alleging breach of data governance standards."
        else:
            summary = f"Industry analysis panel conducts case study review on operations model of {entity}."
            
        news.append({
            "news_id": f"NEWS-{news_id_counter:04d}",
            "entity_name": entity,
            "news_sentiment": sentiment,
            "source": random.choice(sources),
            "summary": summary
        })
        news_id_counter += 1
        
    with open(FILE_PATHS["news_events"], "w") as f:
        json.dump(news, f, indent=4)
    print("News Events generated successfully.")
    return news

# --- MAIN GENERATION PIPELINE ---
def main():
    print("Starting Financial Risk Signal Aggregator Data Generator...")
    sanctions_df = generate_sanctions()
    suspicious_locs_df = generate_suspicious_locations()
    merchants_df = generate_merchants()
    
    customers_df = generate_customers()
    kyc_df = generate_kyc(customers_df)
    accounts_df = generate_accounts(customers_df)
    
    devices_df, cust_devices = generate_devices(customers_df)
    logins_df = generate_logins(customers_df, cust_devices)
    
    transactions_df = generate_transactions(accounts_df, customers_df, merchants_df)
    alerts_df = generate_external_alerts(customers_df, transactions_df)
    watchlist_df = generate_aml_watchlist(customers_df)
    
    generate_news_events(customers_df, merchants_df)
    
    print("\nDataset Generation Complete!")
    print(f"Customers: {len(customers_df)}")
    print(f"Accounts: {len(accounts_df)}")
    print(f"Transactions: {len(transactions_df)}")
    print(f"Merchants: {len(merchants_df)}")
    print(f"Devices: {len(devices_df)}")
    print(f"Logins: {len(logins_df)}")
    print(f"KYC Records: {len(kyc_df)}")
    print(f"External Alerts: {len(alerts_df)}")
    print(f"AML Watchlist: {len(watchlist_df)}")
    print(f"Sanctions: {len(sanctions_df)}")
    print(f"Suspicious Locations: {len(suspicious_locs_df)}")

if __name__ == "__main__":
    main()
