import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class LLMAgent:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        self.api_available = api_key is not None

    def generate_compliance_summary(self, customer_profile: dict, triggered_rules: list, timeline: list) -> str:
        """
        Generates an executive-level compliance risk assessment using Gemini,
        trying multiple model engines sequentially if one fails, and falling
        back to local heuristics if all models or the API key fail.
        """
        if not self.api_available:
            return self._generate_mock_summary(customer_profile, triggered_rules)

        # Retrieve available models dynamically from the Gemini API
        try:
            api_models = []
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    name = m.name.replace("models/", "")
                    api_models.append(name)
        except Exception as list_err:
            print(f"Warning: Could not list models dynamically: {list_err}")
            api_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"]

        primary_model = self.model_name
        
        # Build attempt sequence ensuring primary model is attempted first
        models_to_try = []
        if primary_model in api_models:
            models_to_try.append(primary_model)
        elif primary_model.replace("models/", "") in api_models:
            models_to_try.append(primary_model.replace("models/", ""))
        else:
            models_to_try.append(primary_model)
            
        for m in api_models:
            if m not in models_to_try:
                models_to_try.append(m)

        errors = []
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                prompt = self._build_prompt(customer_profile, triggered_rules, timeline)
                
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.2}
                )
                return response.text
            except Exception as e:
                # Log the error details to console
                print(f"Error calling model '{model_name}': {e}")
                errors.append(f"{model_name}: {str(e)}")
                
        # If all models fail, return the local fallback summary cleanly
        # (Logging all errors to console instead of showing raw quota error trace in UI)
        print(f"API Failure: All model attempts failed. Errors: {'; '.join(errors)}")
        return self._generate_mock_summary(customer_profile, triggered_rules)

    def _build_prompt(self, customer_profile: dict, triggered_rules: list, timeline: list) -> str:
        # Format the inputs for the LLM
        rules_text = "\n".join([f"- [{r['rule_id']}] {r['name']}: {r['details']} (Weight: {r['weight']})" for r in triggered_rules])
        timeline_text = "\n".join([f"- {t['time']}: {t['event']} | Location: {t['location']} | Status: {t['status']}" for t in timeline[:30]])
        
        prompt = f"""
You are a Senior Banking Compliance Officer and Financial Crime Intelligence Analyst at a global investment bank.
Your task is to analyze the following customer dossier and output an Executive Compliance Risk Report.

==================================
CUSTOMER DOSSIER
==================================
Customer ID: {customer_profile.get('customer_id')}
Full Name: {customer_profile.get('full_name')}
Age: {customer_profile.get('customer_age')}
Residence Country: {customer_profile.get('residence_country')}
KYC Status: {customer_profile.get('doc_status')}
PEP Status: {customer_profile.get('pep_status')}
Net Worth: ${customer_profile.get('net_worth', 0):,}
Calculated Risk Score: {customer_profile.get('risk_score')}/100 ({customer_profile.get('risk_level')})

==================================
TRIGGERED RISK RULES
==================================
{rules_text}

==================================
CHRONOLOGICAL TIMELINE OF ACTIVITY
==================================
{timeline_text}

==================================
INSTRUCTIONS FOR THE COMPLIANCE REPORT
==================================
Write a professional, evidence-backed evaluation using standard banking compliance terminology. Ensure the following sections are clearly demarcated:

1. EXECUTIVE SUMMARY
Briefly summarize the customer's risk profile and state whether immediate compliance action is required.

2. RISK EXPLANATION & DETECTED SIGNALS
Detail the specific transaction and login signals that triggered the alarms. Group related anomalies (e.g., structuring, geographic velocity violations).

3. REGULATORY IMPACT & REASONING
Explain why this behavior poses a risk. Cite standard regulations if applicable (e.g., Bank Secrecy Act, FinCEN structuring thresholds, AML standards).

4. DETAILED EVIDENCE TIMELINE
Outline the core suspicious sequence of events from the timeline.

5. INVESTIGATION CONFIDENCE LEVEL
Choose between: LOW / MEDIUM / HIGH. Briefly justify based on the corroboration of signal sources (e.g., multiple alerts, devices, and watchlists).

6. RECOMMENDED IMMEDIATE ACTION
For example: File Suspicious Activity Report (SAR), Freeze account balances, Require Enhanced Due Diligence (EDD), or Close Account.

7. SUGGESTED INVESTIGATION STEPS FOR ANALYSTS
Provide 3-4 tactical next steps for the compliance analyst to perform to verify the source of funds or verify the identity of the user.

Format the response in structured Markdown with clear headings. Do not include introductory conversational filler. Start directly with the report.
"""
        return prompt

    def _generate_mock_summary(self, customer_profile: dict, triggered_rules: list) -> str:
        """Fallback mock engine to provide structured text when Gemini API key is missing."""
        risk_level = customer_profile.get("risk_level", "LOW")
        cust_name = customer_profile.get("full_name", "Customer")
        cust_id = customer_profile.get("customer_id")
        
        rule_list = "\n".join([f"- **{r['name']}**: {r['details']}" for r in triggered_rules])
        
        # Build mock report depending on risk level
        report = f"""### [MOCK MODE] EXECUTIVE COMPLIANCE REPORT (Gemini API Key Not Set)

**Entity Name:** {cust_name} ({cust_id})  
**Risk Level:** **{risk_level}** (Score: {customer_profile.get('risk_score')}/100)  

---

#### 1. EXECUTIVE SUMMARY
Customer {cust_name} exhibits behavioral patterns categorized as **{risk_level}** risk. A total of {len(triggered_rules)} compliance rule violations have been flagged in the audit logs.

#### 2. RISK EXPLANATION & DETECTED SIGNALS
The following rule triggers were evaluated:
{rule_list}

"""
        if risk_level == "CRITICAL":
            report += """
#### 3. REGULATORY IMPACT & REASONING
- **Money Laundering Structuring**: Repeated transactions just under $10,000 are a flagrant attempt to bypass CTR filing requirements under the Bank Secrecy Act (BSA) (31 U.S.C. § 5324).
- **Sanctions Violation**: Transactions or login sessions connecting to OFAC-restricted countries (e.g., Iran, Russia) present direct compliance and regulatory liability risks.
- **Impossible Travel**: Geographic velocity logins indicate credential sharing or active account takeover.

#### 4. INVESTIGATION CONFIDENCE LEVEL
**HIGH** — Multiple corroborating feeds (transactions, logins, watchlists, external agency alerts) align to indicate high probability of regulatory violation.

#### 5. RECOMMENDED IMMEDIATE ACTION
- **Freeze Account Assets immediately.**
- **File a Suspicious Activity Report (SAR)** with FinCEN within 30 days.
- Escalate to the AML Investigation Lead for final closure.

#### 6. SUGGESTED INVESTIGATION STEPS FOR ANALYSTS
1. Perform telephone verification and identity verification to confirm the customer's identity.
2. Request Source of Wealth (SOW) documents (tax filings, salary slips, or business registration).
3. Contact the external reporting agencies to fetch details on alerts.
"""
        elif risk_level == "HIGH":
            report += """
#### 3. REGULATORY IMPACT & REASONING
- **Enhanced Profile Risk**: The customer has matches on PEP/watchlist parameters or incomplete KYC records.
- **Crypto-Asset Interactions**: High amount transfers to crypto merchants increase anonymity and integration phase money laundering risk.

#### 4. INVESTIGATION CONFIDENCE LEVEL
**MEDIUM** — KYC gaps and high-risk merchants flag potential risks, but require corroborative proof of illicit origin of funds.

#### 5. RECOMMENDED IMMEDIATE ACTION
- **Initiate Enhanced Due Diligence (EDD)**.
- Request updated KYC documentation.
- Place account on a 14-day restrictive watch list.

#### 6. SUGGESTED INVESTIGATION STEPS FOR ANALYSTS
1. Review KYC document failures (status, expiry).
2. Validate source of crypto exchange funds.
3. Check for linked transaction accounts inside the bank.
"""
        else:
            report += """
#### 3. REGULATORY IMPACT & REASONING
- Behavior is consistent with standard consumer spending. No systemic AML/BSA violations observed.

#### 4. INVESTIGATION CONFIDENCE LEVEL
**LOW** — Minor or transient alerts.

#### 5. RECOMMENDED IMMEDIATE ACTION
- **No immediate action required.** Maintain standard transaction monitoring.
"""
        return report

    def audit_adhoc_payload(self, payload_text: str) -> str:
        """
        Runs real-time zero-shot AI auditing on custom pasted text or uploaded CSV data,
        extracting risk scores, tiers, anomalies, and regulatory reasoning.
        """
        if not self.api_available:
            return self._generate_mock_adhoc_report(payload_text)

        # Retrieve available models dynamically from the Gemini API
        try:
            api_models = []
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    name = m.name.replace("models/", "")
                    api_models.append(name)
        except Exception as list_err:
            print(f"Warning: Could not list models dynamically in ad-hoc auditor: {list_err}")
            api_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"]

        primary_model = self.model_name
        models_to_try = []
        if primary_model in api_models:
            models_to_try.append(primary_model)
        elif primary_model.replace("models/", "") in api_models:
            models_to_try.append(primary_model.replace("models/", ""))
        else:
            models_to_try.append(primary_model)
            
        for m in api_models:
            if m not in models_to_try:
                models_to_try.append(m)

        prompt = f"""
You are a Lead AML/BSA Compliance Auditor.
You have been provided with an ad-hoc financial dataset, transaction ledger, login coordinates, or unstructured customer logs.
Evaluate this data for potential risk signals, compliance alerts, and financial crime patterns.

Raw Data Payload:
---
{payload_text}
---

Your response MUST follow this structured format:

---
### calculated_risk_score: [Calculated Score between 0 and 100, e.g. 85.5]
### calculated_risk_level: [CRITICAL, HIGH, MEDIUM, or LOW]

#### 1. EXECUTIVE SUMMARY
[Brief high-level summary of the entity activity and overall threat level]

#### 2. RISK EXPLANATION & DETECTED SIGNALS
[Checklist/details of specific transaction anomalies or compliance rules broken, e.g., structuring, geographic speed hops, PEP anomalies]

#### 3. REGULATORY IMPACT & REASONING
[BSA/AML or regulatory laws violated or risk factors, e.g., SAR requirements, CTR evasion, OFAC liability]

#### 4. RECOMMENDED IMMEDIATE ACTION
[Clear compliance steps, e.g., freeze account, restrict transfers, file SAR]
---

Maintain a formal corporate compliance auditing tone. Return the report cleanly.
"""
        
        errors = []
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.2}
                )
                return response.text
            except Exception as e:
                print(f"Error calling model '{model_name}' in ad-hoc audit: {e}")
                errors.append(f"{model_name}: {str(e)}")
                
        print(f"Ad-Hoc API Failure: All model attempts failed. Errors: {'; '.join(errors)}")
        return self._generate_mock_adhoc_report(payload_text)

    def _generate_mock_adhoc_report(self, payload_text: str) -> str:
        """Generates a high-quality mock risk summary when API is offline or unavailable."""
        # Simple keyword heuristic to guess risk
        lower = payload_text.lower()
        score = 15.0
        level = "LOW"
        signals = "- Standard consumer transfer velocity.\n- Residence country matches registration domicile.\n- Standard VPN/login parameters."
        reasoning = "Activity aligns with standard personal spending profiles. No regulatory indicators flagged."
        action = "No immediate actions required. Continue routine automated compliance monitoring."
        
        if "structuring" in lower or "99" in lower or "98" in lower or "95" in lower or "threshold" in lower or "split" in lower:
            score = 88.5
            level = "CRITICAL"
            signals = "- **Evasion of AML Limits**: High frequency of structured deposits just under the $10,000 reporting threshold.\n- **BSA evasion**: Direct patterns of split transaction activities."
            reasoning = "Evasion of currency transaction reporting requirements directly violates 31 U.S.C. 5324 (BSA structuring provisions)."
            action = "File a Suspicious Activity Report (SAR) with FinCEN within 30 days and restrict transaction velocity."
        elif "takeover" in lower or "vpn" in lower or "china" in lower or "impossible travel" in lower:
            score = 74.0
            level = "HIGH"
            signals = "- **Impossible Travel Velocity**: Logins from geographically remote regions within minutes.\n- **VPN Bypass**: Active spoofing of network coordinates."
            reasoning = "High risk of credential theft, unauthorized login, or account takeover (ATO) violating general KYC security standards."
            action = "Initiate Enhanced Due Diligence (EDD), lock online banking access credentials, and request identity verification."
            
        return f"""### [MOCK MODE] AD-HOC COMPLIANCE REPORT (Gemini API Offline)

### calculated_risk_score: {score}
### calculated_risk_level: {level}

#### 1. EXECUTIVE SUMMARY
Ad-hoc audit evaluation completed for custom input logs. Entity exhibits indicators matching **{level}** severity risk.

#### 2. RISK EXPLANATION & DETECTED SIGNALS
{signals}

#### 3. REGULATORY IMPACT & REASONING
{reasoning}

#### 4. RECOMMENDED IMMEDIATE ACTION
{action}"""
