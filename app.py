import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# Import project modules
from config.config import FILE_PATHS, RULE_CATALOG
from generate_data import main as run_data_generator
from loader import DataLoader, DataValidationError
from risk_engine import RiskEngine
from scoring import RiskScorer
import importlib
import llm
importlib.reload(llm)
from llm import LLMAgent
from utils.report_generator import PDFReportGenerator

# --- CACHED PIPELINE SPEEDUP ---
@st.cache_data(show_spinner="Evaluating transaction risk profiles via compliance engine (takes ~2 seconds)...")
def load_and_score_data():
    """Load datasets and precalculate risk score matrices to speed up layout updates."""
    loader = DataLoader()
    data = loader.load_all()
    
    # Evaluate rules
    engine = RiskEngine(data)
    triggered_rules = engine.evaluate_all_rules()
    
    # Calculate scores
    scorer = RiskScorer(triggered_rules)
    risk_scores = scorer.calculate_scores(data["customers"])
    
    return data, triggered_rules, risk_scores

def parse_report_sections(text: str) -> dict:
    """Helper to split AI report text into clean, simple sections for UI layout."""
    sections = {
        "Executive Summary": "",
        "Detected Signals": "",
        "Risk Reasoning": "",
        "Recommendations": "",
        "Confidence & Compliance": "",
        "Next Steps": ""
    }
    
    current_section = "Executive Summary"
    lines = text.split("\n")
    
    for line in lines:
        upper = line.upper()
        if "EXECUTIVE SUMMARY" in upper:
            current_section = "Executive Summary"
            continue
        elif "RISK EXPLANATION" in upper or "DETECTED SIGNALS" in upper:
            current_section = "Detected Signals"
            continue
        elif "REGULATORY IMPACT" in upper or "REASONING" in upper:
            current_section = "Risk Reasoning"
            continue
        elif "RECOMMENDED" in upper or "ACTION" in upper:
            current_section = "Recommendations"
            continue
        elif "CONFIDENCE" in upper:
            current_section = "Confidence & Compliance"
            continue
        elif "STEPS" in upper or "NEXT" in upper:
            current_section = "Next Steps"
            continue
            
        sections[current_section] += line + "\n"
        
    for k in sections:
        sections[k] = sections[k].strip()
        
    # Fallback if parsing resulted in empty sections
    if not any(sections.values()):
        sections["Executive Summary"] = text
        
    return sections

def generate_client_csv(c_profile: dict, risk_row, history: list) -> str:
    """Generates a structured, clean CSV string of the client profile and ledger history."""
    lines = []
    lines.append("SECTION,FIELD/PARAMETER,VALUE/DETAILS")
    lines.append(f"Client Profile,Client Name,{c_profile['full_name']}")
    lines.append(f"Client Profile,Client ID,{c_profile['customer_id']}")
    lines.append(f"Client Profile,Email,{c_profile['email']}")
    lines.append(f"Client Profile,Phone,{c_profile['phone']}")
    lines.append(f"Client Profile,Address,\"{c_profile['address']}\"")
    lines.append(f"Client Profile,Residency Country,{c_profile['residence_country']}")
    lines.append(f"Client Profile,Age,{c_profile['customer_age']}")
    
    lines.append(f"KYC Verification,Status,{c_profile['doc_status']}")
    lines.append(f"KYC Verification,Document Type,{c_profile['doc_type']}")
    lines.append(f"KYC Verification,Expiration Date,{c_profile['expiry_date']}")
    lines.append(f"KYC Verification,Net Worth,{c_profile['net_worth']}")
    lines.append(f"KYC Verification,PEP Status,{c_profile['pep_status']}")
    
    lines.append(f"Risk Assessment,Risk Level,{risk_row['risk_level']}")
    lines.append(f"Risk Assessment,Risk Score,{risk_row['risk_score']}")
    lines.append(f"Risk Assessment,Rules Triggered Count,{risk_row['rules_triggered_count']}")
    
    lines.append(",,")
    lines.append("HISTORICAL LEDGER,LOCATION,STATUS")
    for event in history:
        time_str = event["Time"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(event["Time"], datetime) else str(event["Time"])
        details = event["Details"].replace(",", ";")
        loc = event["Location"].replace(",", ";")
        res = event["Result"]
        lines.append(f"\"{time_str} - {details}\",\"{loc}\",{res}")
        
    return "\n".join(lines)


# --- PAGE CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Financial Risk Intelligence Hub",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Style Sheet
st.markdown("""
<style>
    /* Dark Theme Palette styling */
    .stApp {
        background-color: #0B1220;
        color: #FFFFFF;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #16213E !important;
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    
    /* Header Styling */
    h1, h2, h3, h4, h5, h6 {
        color: #06B6D4 !important;
        font-weight: 600 !important;
    }
    
    /* Metric container overrides */
    div[data-testid="stMetric"] {
        background-color: #16213E !important;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #2563EB;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        font-weight: bold;
        letter-spacing: 0.05em;
    }
    
    div[data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 1.8rem !important;
        font-weight: bold !important;
    }
    
    /* Utility Card panels class */
    .custom-card {
        background-color: #16213E !important;
        color: #FFFFFF !important;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .custom-card h1, .custom-card h2, .custom-card h3, .custom-card h4, .custom-card h5, .custom-card h6, .custom-card p, .custom-card span, .custom-card div, .custom-card b {
        color: #FFFFFF !important;
    }
    
    /* Buttons Custom Theme */
    .stButton>button {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        width: 100%;
    }
    
    .stButton>button:hover {
        background-color: #06B6D4 !important;
        border-color: #06B6D4 !important;
        box-shadow: 0 0 8px rgba(6, 182, 212, 0.4) !important;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0B1220 !important;
        border-bottom: 2px solid #334155;
        padding: 5px 10px 0px 10px;
        gap: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #16213E !important;
        color: #94A3B8 !important;
        border: 1px solid #334155 !important;
        border-bottom: none !important;
        border-radius: 6px 6px 0px 0px;
        padding: 8px 16px;
        font-weight: 600;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #FFFFFF !important;
        background-color: #1E293B !important;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border-color: #2563EB !important;
    }
    
    /* Expanders styling */
    .streamlit-expanderHeader {
        background-color: #16213E !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        color: #FFFFFF !important;
    }
    
    .streamlit-expanderContent {
        background-color: #0B1220 !important;
        color: #E2E8F0 !important;
        border-left: 1px solid #334155 !important;
        border-right: 1px solid #334155 !important;
        border-bottom: 1px solid #334155 !important;
        border-radius: 0px 0px 6px 6px !important;
        padding: 15px !important;
    }
    .streamlit-expanderContent p, .streamlit-expanderContent span, .streamlit-expanderContent div, .streamlit-expanderContent li, .streamlit-expanderContent ol, .streamlit-expanderContent ul, .streamlit-expanderContent b, .streamlit-expanderContent strong {
        color: #E2E8F0 !important;
    }
    
    /* Status Label classes */
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "db_loaded" not in st.session_state:
    st.session_state.db_loaded = False
if "data" not in st.session_state:
    st.session_state.data = {}
if "risk_scores" not in st.session_state:
    st.session_state.risk_scores = None
if "triggered_rules" not in st.session_state:
    st.session_state.triggered_rules = {}

# Check if database files exist
db_exists = all(os.path.exists(path) for key, path in FILE_PATHS.items() if key != "risk_scores")

# --- LOAD DATA WORKFLOW ---
if db_exists and not st.session_state.db_loaded:
    try:
        data, triggered_rules, risk_scores = load_and_score_data()
        st.session_state.data = data
        st.session_state.triggered_rules = triggered_rules
        st.session_state.risk_scores = risk_scores
        st.session_state.db_loaded = True
    except DataValidationError as ve:
        st.error(f"Database Integrity Violation: {ve}")
    except Exception as e:
        st.error(f"Error loading system: {e}")

# --- INITIALIZE MODEL ENGINE ---
model_choice = "gemini-3.5-flash"

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.subheader("Search & Filter Query")
    
    search_query = st.text_input("Customer ID / Name search:")
    
    # Dynamically extract residency countries
    res_countries = sorted(list(st.session_state.data["customers"]["residence_country"].unique())) if st.session_state.db_loaded else []
    countries_filter = st.multiselect(
        "Country Filter:",
        res_countries
    )
    
    risk_filter = st.multiselect(
        "Risk Level Filter:",
        ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    )
    
    min_score_filter = st.slider(
        "Minimum Risk Score:",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0
    )
    
    st.divider()
    st.subheader("System Configuration")
    st.markdown("**Compliance AI Core**: Active")
    if st.session_state.db_loaded:
        st.markdown("**AML Database**: Ready")
        st.markdown(f"**Transactions Ingested**: {len(st.session_state.data['transactions']):,}")
    else:
        st.markdown("**AML Database**: Offline")
    st.markdown(f"**System Time**: {datetime.now().strftime('%H:%M:%S')}")

# --- PAGE BODY LAYOUT ---
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.title("Financial Risk Intelligence Hub")
    st.caption("Federal Core Auditing & Suspicious Activity Command Center")
with header_col2:
    st.write("")
    st.write("")
    if st.button("Refresh Cache Data"):
        st.cache_data.clear()
        st.session_state.db_loaded = False
        st.rerun()

# Pandas style map definitions
def style_risk_level(val):
    if val == "CRITICAL":
        return "background-color: rgba(239, 68, 68, 0.15); color: #EF4444; font-weight: bold; border-left: 3px solid #EF4444;"
    elif val == "HIGH":
        return "background-color: rgba(249, 115, 22, 0.15); color: #F97316; font-weight: bold; border-left: 3px solid #F97316;"
    elif val == "MEDIUM":
        return "background-color: rgba(245, 158, 11, 0.15); color: #F59E0B; font-weight: bold; border-left: 3px solid #F59E0B;"
    elif val == "LOW":
        return "background-color: rgba(34, 197, 94, 0.15); color: #22C55E; font-weight: bold; border-left: 3px solid #22C55E;"
    return ""

if not st.session_state.db_loaded:
    st.warning("Relational transaction databases are not loaded or initialized.")
    if not db_exists:
        if st.button("Initialize & Write Mock Database Records"):
            with st.spinner("Compiling compliance databases..."):
                run_data_generator()
                st.success("Database records successfully written. Reloading...")
                st.rerun()
else:
    cust_df = st.session_state.data["customers"]
    tx_df = st.session_state.data["transactions"]
    acc_df = st.session_state.data["accounts"]
    risk_df = st.session_state.risk_scores
    
    # Align countries details
    cust_country_map = cust_df.set_index("customer_id")["residence_country"].to_dict()
    risk_df["residence_country"] = risk_df["customer_id"].map(cust_country_map)
    
    # Filter calculation logic
    filtered_df = risk_df.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df["full_name"].str.contains(search_query, case=False, na=False) |
            filtered_df["customer_id"].str.contains(search_query, case=False, na=False)
        ]
    if countries_filter:
        filtered_df = filtered_df[filtered_df["residence_country"].isin(countries_filter)]
    if risk_filter:
        filtered_df = filtered_df[filtered_df["risk_level"].isin(risk_filter)]
    if min_score_filter > 0.0:
        filtered_df = filtered_df[filtered_df["risk_score"] >= min_score_filter]

    # --- PORTAL ROUTING VIA HORIZONTAL TABS ---
    # --- PORTAL ROUTING VIA HORIZONTAL TABS ---
    tab_adhoc, tab_queue, tab_profile, tab_investigations, tab_narrative, tab_reports = st.tabs([
        "Ad-Hoc AI Auditor",
        "Risk Queue",
        "Client Dossier",
        "Compliance Review",
        "AI Analysis",
        "Report Generator"
    ])
    
    with tab_adhoc:
        st.divider()
        st.subheader("Ad-Hoc Data Ingestion & AI Auditor")
        st.write("Ingest unstructured customer logs, pasted transactions, or CSV ledgers to run real-time anomaly detection via Google Gemini.")
        
        # Scenario Templates
        structuring_template = """{
  "customer_id": "CUST-TEMP-9981",
  "full_name": "Marcus Vance",
  "pep_status": "No",
  "residence_country": "United States",
  "recent_transactions": [
    {"time": "2026-07-25 10:15", "amount": 9950, "merchant": "Local Deposit ATM", "location": "Miami, FL", "status": "COMPLETED"},
    {"time": "2026-07-25 10:22", "amount": 9800, "merchant": "Local Deposit ATM", "location": "Miami, FL", "status": "COMPLETED"},
    {"time": "2026-07-25 10:45", "amount": 9900, "merchant": "Local Deposit ATM", "location": "Miami, FL", "status": "COMPLETED"}
  ]
}"""

        ato_template = """{
  "customer_id": "CUST-TEMP-0422",
  "full_name": "Helena Rostova",
  "pep_status": "Yes",
  "residence_country": "Latvia",
  "login_history": [
    {"time": "2026-07-26 14:02", "device": "iPhone 15", "location": "Riga, Latvia", "vpn": false, "status": "SUCCESS"},
    {"time": "2026-07-26 14:08", "device": "Linux Desktop", "location": "Beijing, China", "vpn": true, "status": "SUCCESS"}
  ],
  "recent_transactions": [
    {"time": "2026-07-26 14:09", "amount": 250000, "merchant": "Crypto OTC Exchange", "location": "Hong Kong", "status": "COMPLETED"}
  ]
}"""
        input_mode = st.radio("Choose Input Mode:", ["Select Pre-defined Template Scenario", "Paste Custom Text / JSON Payload", "Upload CSV Transaction Ledger"], horizontal=True, key="adhoc_input_mode")
        
        payload_input = ""
        if input_mode == "Select Pre-defined Template Scenario":
            scenario_choice = st.selectbox(
                "Choose Template Scenario:",
                ["Scenario A: Money Laundering Structuring (Evasion of CTR threshold)", "Scenario B: Impossible Travel & Cryptocurrency Outflow (Account Takeover)"],
                key="adhoc_template_selector"
            )
            if "Scenario A" in scenario_choice:
                payload_input = structuring_template
            else:
                payload_input = ato_template
            st.text_area("Selected Scenario JSON (Read-Only):", value=payload_input, height=180, disabled=True, key="adhoc_template_display")
            
        elif input_mode == "Paste Custom Text / JSON Payload":
            payload_input = st.text_area("Paste unstructured logs, customer profiles, or JSON transaction details here:", height=200, placeholder="Paste data here...", key="adhoc_text_paste_input")
            
        else: # Upload CSV
            uploaded_file = st.file_uploader("Upload CSV transaction records:", type=["csv"], key="adhoc_csv_uploader")
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    st.dataframe(df_upload.head(10), use_container_width=True)
                    payload_input = f"Uploaded CSV Data (First 100 Rows):\n{df_upload.head(100).to_csv(index=False)}"
                except Exception as ex:
                    st.error(f"Error reading CSV file: {ex}")
            else:
                st.info("Upload a CSV file containing transactions or logs to continue.")
                
        st.write("")
        if st.button("Run AI Compliance Audit", key="adhoc_run_audit_btn"):
            if not payload_input.strip():
                st.warning("Please provide a valid payload to audit.")
            else:
                with st.spinner("Analyzing data payload for compliance anomalies via Gemini..."):
                    agent = LLMAgent(model_name=model_choice)
                    report_text = agent.audit_adhoc_payload(payload_input)
                    st.session_state["adhoc_report"] = report_text
                    
        if "adhoc_report" in st.session_state:
            report_text = st.session_state["adhoc_report"]
            
            # Parse calculated risk parameters if present
            score_line = [line for line in report_text.split("\n") if "calculated_risk_score" in line]
            level_line = [line for line in report_text.split("\n") if "calculated_risk_level" in line]
            
            extracted_score = 0.0
            extracted_level = "LOW"
            
            if score_line:
                try: extracted_score = float(score_line[0].split(":")[-1].strip().replace("[", "").replace("]", ""))
                except: pass
            if level_line:
                extracted_level = level_line[0].split(":")[-1].strip().replace("[", "").replace("]", "").strip()
                
            color_hex = "#EF4444" if extracted_level == "CRITICAL" else "#F97316" if extracted_level == "HIGH" else "#F59E0B" if extracted_level == "MEDIUM" else "#22C55E"
            
            st.divider()
            st.markdown("### AI Audit Evaluation Results")
            
            # Risk Score Card
            st.markdown(f"""
            <div class="custom-card" style="border-left: 5px solid {color_hex};">
                <h3>Calculated Case Risk: <span style="color:{color_hex};">{extracted_level} ({extracted_score}/100)</span></h3>
                <p>Generated via Real-Time Zero-Shot AI Audit Policy</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Display report body cleanly, skipping parameters markup lines
            clean_lines = [l for l in report_text.split("\n") if "calculated_risk_" not in l]
            clean_report = "\n".join(clean_lines).strip()
            st.markdown(clean_report)
            
            # Download button
            st.download_button(
                label="Download AI Audit Report (TXT)",
                data=clean_report,
                file_name="adhoc_audit_report.txt",
                mime="text/plain",
                key="adhoc_download_txt_btn",
                use_container_width=True
            )

    with tab_queue:
        # Calculations of metrics
        crit_count = len(filtered_df[filtered_df["risk_level"] == "CRITICAL"])
        high_count = len(filtered_df[filtered_df["risk_level"] == "HIGH"])
        total_volume = tx_df[tx_df["transaction_status"] == "COMPLETED"]["amount"].sum()
        avg_risk = filtered_df["risk_score"].mean() if not filtered_df.empty else 0.0
        
        # Metric Grid Row
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric(label="Total Audited Customers", value=f"{len(cust_df):,}", delta="Registry Base")
        col_m2.metric(label="Active Accounts", value=f"{len(acc_df):,}", delta="Financial Core")
        col_m3.metric(label="Completed Outflow Volume", value=f"${total_volume:,.2f}", delta="Completed Tx")
        col_m4.metric(label="Critical Risk Profiles", value=crit_count, delta=f"{crit_count/len(risk_df)*100:.1f}% Queue Share", delta_color="inverse")
        
        col_m5, col_m6, col_m7, col_m8 = st.columns(4)
        col_m5.metric(label="High Risk Accounts", value=high_count, delta=f"{high_count/len(risk_df)*100:.1f}% Queue Share", delta_color="inverse")
        col_m6.metric(label="Open Investigations", value=crit_count + high_count, delta="Active Audit Queue")
        col_m7.metric(label="Ingested AI Alerts", value=len(st.session_state.data["external_alerts"]), delta="External Registry")
        col_m8.metric(label="Average Risk Score", value=f"{avg_risk:.1f} / 100", delta="Base Average")

        st.divider()
        st.subheader("Financial Analytics & Alerts Distribution")
        
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            risk_dist = filtered_df["risk_level"].value_counts().reset_index()
            risk_dist.columns = ["Risk Level", "Count"]
            fig_pie = px.pie(
                risk_dist, 
                values="Count", 
                names="Risk Level",
                title="Overall Profile Risk Distribution",
                color="Risk Level",
                color_discrete_map={
                    "CRITICAL": "#EF4444",
                    "HIGH": "#F97316",
                    "MEDIUM": "#F59E0B",
                    "LOW": "#22C55E"
                },
                hole=0.4
            )
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0")
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with chart_col2:
            tx_df["date"] = pd.to_datetime(tx_df["transaction_time"]).dt.date
            daily_txs = tx_df.groupby("date")["amount"].sum().reset_index()
            fig_trend = px.line(
                daily_txs, 
                x="date", 
                y="amount", 
                title="Outbound Transaction Volume Trend", 
                markers=True, 
                color_discrete_sequence=["#06B6D4"]
            )
            fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0")
            st.plotly_chart(fig_trend, use_container_width=True)

        chart_col3, chart_col4 = st.columns(2)
        with chart_col3:
            # Rule counts extraction
            rule_tally = {}
            for c_id, rules in st.session_state.triggered_rules.items():
                for rule in rules:
                    r_id = rule["rule_id"]
                    rule_tally[r_id] = rule_tally.get(r_id, 0) + 1
            tally_df = pd.DataFrame(list(rule_tally.items()), columns=["Rule Code", "Alarms Triggered"]).sort_values("Alarms Triggered", ascending=False).head(10)
            fig_bar = px.bar(
                tally_df, 
                x="Alarms Triggered", 
                y="Rule Code", 
                orientation="h", 
                title="Frequently Triggered Compliance Rules",
                color="Alarms Triggered",
                color_continuous_scale="Viridis"
            )
            fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with chart_col4:
            country_dist = filtered_df[filtered_df["risk_level"].isin(["CRITICAL", "HIGH"])].groupby("residence_country").size().reset_index(name="Flagged Accounts")
            fig_country = px.bar(
                country_dist, 
                x="residence_country", 
                y="Flagged Accounts", 
                title="Critical & High Risk Counts by Country", 
                color="Flagged Accounts", 
                color_continuous_scale="Oranges"
            )
            fig_country.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0")
            st.plotly_chart(fig_country, use_container_width=True)

        st.divider()
        st.subheader("Audited Risk Queue")
        
        # Prepare queue representation dataframe
        disp_df = filtered_df.copy()
        def get_confidence(score):
            if score >= 70: return "High"
            elif score >= 40: return "Medium"
            return "Low"
        disp_df["Confidence"] = disp_df["risk_score"].map(get_confidence)
        disp_df["Status"] = disp_df["risk_level"].map(lambda x: "Under Investigation" if x in ["CRITICAL", "HIGH"] else "Active Monitoring")
        disp_df["Action"] = disp_df["risk_level"].map(lambda x: "ESC / FREEZE" if x == "CRITICAL" else "MANUAL EDD" if x == "HIGH" else "MONITOR" if x == "MEDIUM" else "CLEAR")
        
        disp_df = disp_df.rename(columns={
            "customer_id": "Customer ID",
            "full_name": "Customer Name",
            "risk_score": "Risk Score",
            "risk_level": "Risk Level",
            "rules_triggered_count": "Signals Triggered"
        })
        
        display_cols = ["Customer ID", "Customer Name", "Risk Score", "Risk Level", "Signals Triggered", "Confidence", "Status", "Action"]
        
        if not disp_df.empty:
            try:
                styled_queue = disp_df[display_cols].style.map(style_risk_level, subset=["Risk Level"])
            except AttributeError:
                styled_queue = disp_df[display_cols].style.applymap(style_risk_level, subset=["Risk Level"])
            st.dataframe(styled_queue, use_container_width=True, hide_index=True)
        else:
            st.info("No records match the active criteria.")

    with tab_profile:
        # Select customer
        options = [f"{row['customer_id']} | {row['full_name']}" for _, row in filtered_df.iterrows()]
        if not options:
            st.warning("No audited profiles match the active filters.")
        else:
            col_sel, col_dl = st.columns([3, 2])
            with col_sel:
                selected_option = st.selectbox("Select Profile for Unified Audit:", options)
                selected_id = selected_option.split(" | ")[0]
            
            selected_row = risk_df[risk_df["customer_id"] == selected_id].iloc[0]
            c_profile = cust_df[cust_df["customer_id"] == selected_id].iloc[0].to_dict()
            kyc_rec = st.session_state.data["kyc_records"][st.session_state.data["kyc_records"]["customer_id"] == selected_id].iloc[0].to_dict()
            c_profile.update(kyc_rec)
            c_profile["risk_score"] = selected_row["risk_score"]
            c_profile["risk_level"] = selected_row["risk_level"]
            
            # Precalculate/fetch related accounts, logins, and ledger history for display and download
            c_accs = acc_df[acc_df["customer_id"] == selected_id]
            c_acc_numbers = c_accs["account_number"].tolist()
            c_txs = tx_df[tx_df["account_number"].isin(c_acc_numbers)].copy()
            c_txs = c_txs.merge(st.session_state.data["merchants"], on="merchant_id", how="left")
            c_logins = st.session_state.data["login_history"][st.session_state.data["login_history"]["customer_id"] == selected_id].copy()
            
            history = []
            for _, row in c_txs.iterrows():
                history.append({
                    "Time": pd.to_datetime(row["transaction_time"]),
                    "Details": f"Tx: {row['transaction_type']} to {row['merchant_name']} | Amount: ${row['amount']:,.2f}",
                    "Location": f"{row['location_city']}, {row['location_country']}",
                    "Result": row["transaction_status"]
                })
            for _, row in c_logins.iterrows():
                history.append({
                    "Time": pd.to_datetime(row["login_time"]),
                    "Details": f"Login Device: {row['device_id']}",
                    "Location": f"{row['city']}, {row['country']} (VPN: {row['is_vpn']})",
                    "Result": row["login_status"]
                })
            sorted_history = sorted(history, key=lambda x: x["Time"], reverse=True)
            history_df = pd.DataFrame(sorted_history)
            
            with col_dl:
                # Select report format dropdown
                st.write("") # align
                st.write("")
                report_format = st.selectbox(
                    "Choose Download Format:",
                    ["PDF Report (Dossier)", "CSV Spreadsheet (Profile & Ledger)"],
                    key=f"dl_format_{selected_id}"
                )
                
                if report_format == "PDF Report (Dossier)":
                    # PDF Download block
                    if f"ai_report_{selected_id}" in st.session_state:
                        ai_report_text = st.session_state[f"ai_report_{selected_id}"]
                    else:
                        agent = LLMAgent(model_name=model_choice)
                        ai_report_text = agent._generate_mock_summary(c_profile, st.session_state.triggered_rules.get(selected_id, []))
                        
                    pdf_filename = f"dossier_{selected_id}.pdf"
                    pdf_path = os.path.join(FILE_PATHS["risk_scores"].replace("risk_scores.csv", ""), pdf_filename)
                    
                    PDFReportGenerator.generate_dossier(
                        pdf_path,
                        c_profile,
                        st.session_state.triggered_rules.get(selected_id, []),
                        ai_report_text
                    )
                    
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        st.download_button(
                            label="Download PDF Report",
                            data=pdf_bytes,
                            file_name=pdf_filename,
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"profile_dl_pdf_{selected_id}"
                        )
                else:
                    # CSV Download block
                    csv_data = generate_client_csv(c_profile, selected_row, history)
                    st.download_button(
                        label="Download CSV Spreadsheet",
                        data=csv_data,
                        file_name=f"audit_report_{selected_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"profile_dl_csv_{selected_id}"
                    )
            
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("### Client Demographics & Details")
                st.write(f"**Client Name**: {c_profile['full_name']}")
                st.write(f"**Client ID**: {c_profile['customer_id']}")
                st.write(f"**Primary Email**: {c_profile['email']}")
                st.write(f"**Contact Number**: {c_profile['phone']}")
                st.write(f"**Registered Domicile**: {c_profile['address']}")
                st.write(f"**Jurisdictional Residency**: {c_profile['residence_country']}")
                st.write(f"**Client Age**: {c_profile['customer_age']} years old")
                
                st.markdown("### Compliance & Verification Status (KYC)")
                st.write(f"**Verification Status**: {c_profile['doc_status']}")
                st.write(f"**Identification Registry**: {c_profile['doc_type']}")
                st.write(f"**Credential Expiration**: {c_profile['expiry_date']}")
                st.write(f"**Estimated Client Net Worth**: ${c_profile['net_worth']:,}")
                st.write(f"**PEP Classification Status**: {c_profile['pep_status']}")

                st.markdown("### Regulatory Screening & Watchlists")
                # Watchlist checks
                wl_hits = st.session_state.data["aml_watchlist"][st.session_state.data["aml_watchlist"]["customer_id"] == selected_id]
                if not wl_hits.empty:
                    st.error(f"Watchlist Hit: {wl_hits.iloc[0]['reason']} ({wl_hits.iloc[0]['status']})")
                else:
                    st.success("No Direct AML Watchlist entries matched.")
                    
                # Sanction checks
                sanc_hits = st.session_state.data["sanctions"][st.session_state.data["sanctions"]["country"] == c_profile["residence_country"]]
                if not sanc_hits.empty:
                    st.warning(f"Residency country matches {len(sanc_hits)} Sanctioned Entities list: {sanc_hits.iloc[0]['entity_name']} ({sanc_hits.iloc[0]['sanction_type']})")
                else:
                    st.success("No Direct Sanctions country records found.")
                
            with col_r:
                st.markdown("### Risk Score Matrix")
                level = selected_row["risk_level"]
                score = selected_row["risk_score"]
                color_hex = "#EF4444" if level == "CRITICAL" else "#F97316" if level == "HIGH" else "#F59E0B" if level == "MEDIUM" else "#22C55E"
                st.markdown(f"**Calculated Score Category**: <span class='status-badge' style='background-color:{color_hex}; color:#FFFFFF;'>{level} ({score}/100)</span>", unsafe_allow_html=True)
                
                st.markdown("### Registered Customer Accounts")
                st.dataframe(c_accs[["account_number", "account_type", "open_date", "balance", "status"]], use_container_width=True, hide_index=True)
                
                st.markdown("### Associated Login Access Devices")
                c_devs = st.session_state.data["devices"][st.session_state.data["devices"]["customer_id"] == selected_id]
                if not c_devs.empty:
                    st.dataframe(c_devs[["device_id", "device_type", "ip_address", "os"]], use_container_width=True, hide_index=True)
                else:
                    st.write("No registered devices.")

                st.markdown("### Audited Transaction & Session Ledger")
                if not history_df.empty:
                    st.dataframe(history_df, use_container_width=True, hide_index=True)
                else:
                    st.write("No recorded transactions or login sessions.")

    with tab_investigations:
        st.divider()
        st.subheader("Compliance Audit & Decision Manager")
        
        crit_invs = risk_df
        options = [f"{row['customer_id']} | {row['full_name']} (Risk: {row['risk_score']})" for _, row in crit_invs.iterrows()]
        
        if not options:
            st.success("No active cases require compliance audit.")
        else:
            selected_option = st.selectbox("Select Target File for Compliance Review:", options, key="investigations_selectbox_target")
            selected_id = selected_option.split(" | ")[0]
            
            selected_row = risk_df[risk_df["customer_id"] == selected_id].iloc[0]
            c_profile = cust_df[cust_df["customer_id"] == selected_id].iloc[0].to_dict()
            kyc_rec = st.session_state.data["kyc_records"][st.session_state.data["kyc_records"]["customer_id"] == selected_id].iloc[0].to_dict()
            c_profile.update(kyc_rec)
            c_profile["risk_score"] = selected_row["risk_score"]
            c_profile["risk_level"] = selected_row["risk_level"]
            
            # Fetch accounts & transaction ledger
            c_accs = acc_df[acc_df["customer_id"] == selected_id]
            c_acc_numbers = c_accs["account_number"].tolist()
            c_txs = tx_df[tx_df["account_number"].isin(c_acc_numbers)].copy()
            c_txs = c_txs.merge(st.session_state.data["merchants"], on="merchant_id", how="left")
            c_logins = st.session_state.data["login_history"][st.session_state.data["login_history"]["customer_id"] == selected_id].copy()
            
            timeline = []
            for _, row in c_txs.iterrows():
                timeline.append({
                    "time": pd.to_datetime(row["transaction_time"]),
                    "event": f"Tx: {row['transaction_type']} | Amount: ${row['amount']:,.2f}",
                    "location": f"{row['location_city']}, {row['location_country']}",
                    "status": row["transaction_status"]
                })
            for _, row in c_logins.iterrows():
                timeline.append({
                    "time": pd.to_datetime(row["login_time"]),
                    "event": f"User Login | Device: {row['device_id']}",
                    "location": f"{row['city']}, {row['country']} (VPN: {row['is_vpn']})",
                    "status": row["login_status"]
                })
            timeline_sorted = sorted(timeline, key=lambda x: x["time"], reverse=True)
            
            st.markdown(f"**Active Review File**: CASE-{selected_id} | **Calculated Priority**: **{selected_row['risk_level']}** (Score: {selected_row['risk_score']}/100)")
            
            col_ov1, col_ov2 = st.columns(2)
            with col_ov1:
                st.markdown("#### High-Level Profile Summary")
                st.write(f"**Client Name**: {c_profile['full_name']}")
                st.write(f"**Jurisdiction Domicile**: {c_profile['residence_country']}")
                st.write(f"**PEP Status**: {c_profile['pep_status']}")
                st.write(f"**Estimated Net Worth**: ${c_profile['net_worth']:,}")
                st.write(f"**Verification Status**: {c_profile['doc_status']} ({c_profile['doc_type']})")
                
            with col_ov2:
                st.markdown("#### compliance Decision Action Center")
                analyst_notes = st.text_area("Write Analyst Notes:", placeholder="Document audit assessments and next verification steps...", key=f"inv_notes_input_{selected_id}")
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Approve & Mark Clear", key=f"inv_btn_approve_{selected_id}"):
                        st.success("Case marked as approved / verified.")
                with col_b2:
                    if st.button("Escalate Case to Director", key=f"inv_btn_escalate_{selected_id}"):
                        st.warning("Case successfully escalated to Director review.")
                        
            st.divider()
            st.markdown("### Triggered Risk Signals Checklist")
            triggered = st.session_state.triggered_rules.get(selected_id, [])
            if not triggered:
                st.success("No compliance alerts triggered.")
            else:
                rules_disp = pd.DataFrame(triggered)[["rule_id", "name", "category", "weight", "details"]]
                rules_disp = rules_disp.rename(columns={
                    "rule_id": "Rule Code",
                    "name": "Triggered Signal",
                    "category": "Risk Category",
                    "weight": "Weight Factor",
                    "details": "Details"
                })
                st.dataframe(rules_disp, use_container_width=True, hide_index=True)
                
            st.divider()
            st.markdown("### AI Compliance Narrative & Dossier Generation")
            
            triggered_list = st.session_state.triggered_rules.get(selected_id, [])
            timeline_ctx = [{
                "time": e["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "event": e["event"],
                "location": e["location"],
                "status": e["status"]
            } for e in sorted(timeline, key=lambda x: x["time"], reverse=False)]
            
            if st.button("Generate Case Report via Gemini Engine", key=f"inv_btn_generate_ai_{selected_id}"):
                with st.spinner("Analyzing risk parameters via Gemini..."):
                    agent = LLMAgent(model_name=model_choice)
                    report = agent.generate_compliance_summary(c_profile, triggered_list, timeline_ctx)
                    st.session_state[f"ai_report_{selected_id}"] = report
                    
            if f"ai_report_{selected_id}" in st.session_state:
                ai_report_text = st.session_state[f"ai_report_{selected_id}"]
                st.markdown(ai_report_text)
                
                # Generate PDF button
                pdf_filename = f"dossier_{selected_id}.pdf"
                pdf_path = os.path.join(FILE_PATHS["risk_scores"].replace("risk_scores.csv", ""), pdf_filename)
                
                if st.button("Compile Dossier PDF", key=f"inv_btn_compile_pdf_{selected_id}"):
                    PDFReportGenerator.generate_dossier(
                        pdf_path,
                        c_profile,
                        triggered_list,
                        ai_report_text
                    )
                    st.success(f"Dossier PDF compiled.")
                    
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="Download Dossier PDF",
                                data=f,
                                file_name=pdf_filename,
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"inv_btn_download_pdf_{selected_id}"
                            )
            else:
                st.info("Click 'Generate Case Report via Gemini Engine' above to run AI compliance check.")

    with tab_narrative:
        st.divider()
        st.subheader("AI Case Narratives & Risk Summaries")
        
        crit_invs = risk_df
        options = [f"{row['customer_id']} | {row['full_name']}" for _, row in crit_invs.iterrows()]
        
        if not options:
            st.success("No active critical or high-risk cases.")
        else:
            selected_option = st.selectbox("Select Target File for AI Details:", options)
            selected_id = selected_option.split(" | ")[0]
            
            selected_row = risk_df[risk_df["customer_id"] == selected_id].iloc[0]
            
            if f"ai_report_{selected_id}" in st.session_state:
                ai_report_text = st.session_state[f"ai_report_{selected_id}"]
                sections = parse_report_sections(ai_report_text)
                
                # Overall Risk Card
                st.markdown(f"""
                <div class="custom-card" style="border-left: 5px solid #EF4444;">
                    <h3>Overall Case Risk Classification: {selected_row['risk_level']}</h3>
                    <p><b>Risk Score</b>: {selected_row['risk_score']}/100 | <b>Triggered Count</b>: {selected_row['rules_triggered_count']} Flags</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("Executive Summary", expanded=True):
                    st.markdown(sections["Executive Summary"] if sections["Executive Summary"] else "No summary details.")
                    
                with st.expander("Detected Risk Signals", expanded=True):
                    st.markdown(sections["Detected Signals"] if sections["Detected Signals"] else "No signals details.")
                    
                with st.expander("Regulatory Impact & Reasoning", expanded=True):
                    st.markdown(sections["Risk Reasoning"] if sections["Risk Reasoning"] else "No reasoning details.")
                    
                with st.expander("Recommended Actions & Next Steps", expanded=True):
                    st.markdown(sections["Recommendations"] if sections["Recommendations"] else "No recommendations details.")
                    st.markdown(sections["Confidence & Compliance"] if sections["Confidence & Compliance"] else "")
                    st.markdown(sections["Next Steps"] if sections["Next Steps"] else "")
            else:
                st.info("No AI Compliance Summary loaded for this customer.")
                if st.button("Generate Case Report via Gemini Engine", key=f"gen_summary_page_{selected_id}"):
                    # Build profile context
                    c_profile = cust_df[cust_df["customer_id"] == selected_id].iloc[0].to_dict()
                    kyc_rec = st.session_state.data["kyc_records"][st.session_state.data["kyc_records"]["customer_id"] == selected_id].iloc[0].to_dict()
                    c_profile.update(kyc_rec)
                    c_profile["risk_score"] = selected_row["risk_score"]
                    c_profile["risk_level"] = selected_row["risk_level"]
                    
                    # Fetch accounts
                    c_accs = acc_df[acc_df["customer_id"] == selected_id]
                    c_acc_numbers = c_accs["account_number"].tolist()
                    
                    # Fetch transactions and merchants
                    c_txs = tx_df[tx_df["account_number"].isin(c_acc_numbers)].copy()
                    c_txs = c_txs.merge(st.session_state.data["merchants"], on="merchant_id", how="left")
                    
                    # Fetch login history
                    c_logins = st.session_state.data["login_history"][st.session_state.data["login_history"]["customer_id"] == selected_id].copy()
                    
                    # Reconstruct timeline
                    timeline = []
                    for _, row in c_txs.iterrows():
                        timeline.append({
                            "time": pd.to_datetime(row["transaction_time"]),
                            "event": f"Tx: {row['transaction_type']} | Amount: ${row['amount']:,.2f}",
                            "location": f"{row['location_city']}, {row['location_country']}",
                            "status": row["transaction_status"]
                        })
                    for _, row in c_logins.iterrows():
                        timeline.append({
                            "time": pd.to_datetime(row["login_time"]),
                            "event": f"User Login | Device: {row['device_id']}",
                            "location": f"{row['city']}, {row['country']} (VPN: {row['is_vpn']})",
                            "status": row["login_status"]
                        })
                    
                    # Sort timeline chronologically
                    timeline_ctx = [{
                        "time": e["time"].strftime("%Y-%m-%d %H:%M:%S"),
                        "event": e["event"],
                        "location": e["location"],
                        "status": e["status"]
                    } for e in sorted(timeline, key=lambda x: x["time"], reverse=False)]
                    
                    triggered_list = st.session_state.triggered_rules.get(selected_id, [])
                    
                    with st.spinner("Analyzing risk parameters via Gemini..."):
                        agent = LLMAgent(model_name=model_choice)
                        report = agent.generate_compliance_summary(c_profile, triggered_list, timeline_ctx)
                        st.session_state[f"ai_report_{selected_id}"] = report
                        st.rerun()

    with tab_reports:
        st.divider()
        st.subheader("Compliance Export & Reports Center")
        
        col_rep1, col_rep2 = st.columns(2)
        
        with col_rep1:
            st.markdown("### Export Master Risk Register")
            st.write("Extract the calculated risk scoring table for active monitoring across all portfolios.")
            
            master_format = st.selectbox(
                "Choose Register Format:",
                ["CSV Spreadsheet (Full Registry)", "PDF Summary Report (Top 50 Cases)"],
                key="master_register_format"
            )
            
            risk_csv_path = FILE_PATHS["risk_scores"]
            if os.path.exists(risk_csv_path):
                if master_format == "CSV Spreadsheet (Full Registry)":
                    with open(risk_csv_path, "r") as f:
                        st.download_button(
                            label="Download Full Risk Scores (CSV)",
                            data=f.read(),
                            file_name="risk_scores_export.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="master_register_dl_csv"
                        )
                else:
                    pdf_master_filename = "master_risk_register.pdf"
                    pdf_master_path = os.path.join(FILE_PATHS["risk_scores"].replace("risk_scores.csv", ""), pdf_master_filename)
                    
                    PDFReportGenerator.generate_master_register(
                        pdf_master_path,
                        risk_df
                    )
                    
                    if os.path.exists(pdf_master_path):
                        with open(pdf_master_path, "rb") as f:
                            pdf_master_bytes = f.read()
                        st.download_button(
                            label="Download Master Register PDF",
                            data=pdf_master_bytes,
                            file_name=pdf_master_filename,
                            mime="application/pdf",
                            use_container_width=True,
                            key="master_register_dl_pdf"
                        )
            else:
                st.error("No risk scoring index file found. Go to the Dashboard page first to run calculations.")
                
        with col_rep2:
            st.markdown("### Individual Client Compliance Reports")
            st.write("Generate and download formal audit files for specific accounts.")
            
            # Select customer from all records (including low/no risk)
            options = [f"{row['customer_id']} | {row['full_name']}" for _, row in risk_df.iterrows()]
            if not options:
                st.info("No audited client files available.")
            else:
                selected_option = st.selectbox("Select Target Client File:", options, key="reports_page_client_select")
                selected_id = selected_option.split(" | ")[0]
                
                selected_row = risk_df[risk_df["customer_id"] == selected_id].iloc[0]
                c_profile = cust_df[cust_df["customer_id"] == selected_id].iloc[0].to_dict()
                kyc_rec = st.session_state.data["kyc_records"][st.session_state.data["kyc_records"]["customer_id"] == selected_id].iloc[0].to_dict()
                c_profile.update(kyc_rec)
                c_profile["risk_score"] = selected_row["risk_score"]
                c_profile["risk_level"] = selected_row["risk_level"]
                
                # Fetch accounts & ledger history
                c_accs = acc_df[acc_df["customer_id"] == selected_id]
                c_acc_numbers = c_accs["account_number"].tolist()
                c_txs = tx_df[tx_df["account_number"].isin(c_acc_numbers)].copy()
                c_txs = c_txs.merge(st.session_state.data["merchants"], on="merchant_id", how="left")
                c_logins = st.session_state.data["login_history"][st.session_state.data["login_history"]["customer_id"] == selected_id].copy()
                
                history = []
                for _, row in c_txs.iterrows():
                    history.append({
                        "Time": pd.to_datetime(row["transaction_time"]),
                        "Details": f"Tx: {row['transaction_type']} to {row['merchant_name']} | Amount: ${row['amount']:,.2f}",
                        "Location": f"{row['location_city']}, {row['location_country']}",
                        "Result": row["transaction_status"]
                    })
                for _, row in c_logins.iterrows():
                    history.append({
                        "Time": pd.to_datetime(row["login_time"]),
                        "Details": f"Login Device: {row['device_id']}",
                        "Location": f"{row['city']}, {row['country']} (VPN: {row['is_vpn']})",
                        "Result": row["login_status"]
                    })
                
                report_format = st.selectbox(
                    "Choose Download Format:",
                    ["PDF Report (Dossier)", "CSV Spreadsheet (Profile & Ledger)"],
                    key=f"reports_page_dl_format_{selected_id}"
                )
                
                if report_format == "PDF Report (Dossier)":
                    if f"ai_report_{selected_id}" in st.session_state:
                        ai_report_text = st.session_state[f"ai_report_{selected_id}"]
                    else:
                        agent = LLMAgent(model_name=model_choice)
                        ai_report_text = agent._generate_mock_summary(c_profile, st.session_state.triggered_rules.get(selected_id, []))
                        
                    pdf_filename = f"dossier_{selected_id}.pdf"
                    pdf_path = os.path.join(FILE_PATHS["risk_scores"].replace("risk_scores.csv", ""), pdf_filename)
                    
                    PDFReportGenerator.generate_dossier(
                        pdf_path,
                        c_profile,
                        st.session_state.triggered_rules.get(selected_id, []),
                        ai_report_text
                    )
                    
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        st.download_button(
                            label="Download PDF Report",
                            data=pdf_bytes,
                            file_name=pdf_filename,
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"reports_page_dl_pdf_{selected_id}"
                        )
                else:
                    csv_data = generate_client_csv(c_profile, selected_row, history)
                    st.download_button(
                        label="Download CSV Spreadsheet",
                        data=csv_data,
                        file_name=f"audit_report_{selected_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"reports_page_dl_csv_{selected_id}"
                    )

