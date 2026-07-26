import os
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class PDFReportGenerator:
    @staticmethod
    def generate_dossier(
        output_path: str,
        customer_profile: dict,
        triggered_rules: list,
        ai_summary: str
    ):
        """Generates a professional PDF compliance dossier for an audited customer."""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )
        
        styles = getSampleStyleSheet()
        
        # Define custom styles to avoid collisions
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0F172A'), # Dark slate
            spaceAfter=12
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1E293B'),
            spaceBefore=10,
            spaceAfter=6,
            borderColor=colors.HexColor('#CBD5E1'),
            borderWidth=0.5,
            borderPadding=4
        )
        
        body_style = ParagraphStyle(
            'BodyTextCustom',
            parent=styles['Normal'],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor('#334155')
        )
        
        header_key_style = ParagraphStyle(
            'HeaderKey',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1E293B')
        )
        
        header_val_style = ParagraphStyle(
            'HeaderVal',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#475569')
        )

        story = []
        
        # 1. Header Banner
        story.append(Paragraph("FEDERAL & TRUST COMPLIANCE COMMAND CENTER", title_style))
        story.append(Paragraph("<b>CONFIDENTIAL | FOR AML INTERNAL AUDIT USE ONLY</b>", ParagraphStyle('Sub', parent=body_style, textColor=colors.HexColor('#EF4444'))))
        story.append(Spacer(1, 0.1 * inch))
        
        # 2. Customer Summary Grid Table
        score = customer_profile.get('risk_score', 0)
        level = customer_profile.get('risk_level', 'LOW')
        
        # Set badge color
        if level == "CRITICAL":
            badge_color = colors.HexColor('#EF4444') # Red
        elif level == "HIGH":
            badge_color = colors.HexColor('#F97316') # Orange
        elif level == "MEDIUM":
            badge_color = colors.HexColor('#EAB308') # Yellow/Amber
        else:
            badge_color = colors.HexColor('#22C55E') # Green

        summary_data = [
            [
                Paragraph("<b>Audited Entity:</b>", header_key_style),
                Paragraph(str(customer_profile.get('full_name')), header_val_style),
                Paragraph("<b>Investigation ID:</b>", header_key_style),
                Paragraph(f"INV-{customer_profile.get('customer_id')}", header_val_style)
            ],
            [
                Paragraph("<b>KYC Status:</b>", header_key_style),
                Paragraph(str(customer_profile.get('doc_status')), header_val_style),
                Paragraph("<b>Net Worth:</b>", header_key_style),
                Paragraph(f"${customer_profile.get('net_worth', 0):,}", header_val_style)
            ],
            [
                Paragraph("<b>Residence Country:</b>", header_key_style),
                Paragraph(str(customer_profile.get('residence_country')), header_val_style),
                Paragraph("<b>Politically Exposed (PEP):</b>", header_key_style),
                Paragraph(str(customer_profile.get('pep_status')), header_val_style)
            ],
            [
                Paragraph("<b>Calculated Risk Score:</b>", header_key_style),
                Paragraph(f"<b>{score}/100</b>", ParagraphStyle('Score', parent=header_val_style, textColor=badge_color, fontName='Helvetica-Bold')),
                Paragraph("<b>Assigned Severity:</b>", header_key_style),
                Paragraph(f"<b>{level}</b>", ParagraphStyle('Level', parent=header_val_style, textColor=badge_color, fontName='Helvetica-Bold'))
            ]
        ]
        
        t_summary = Table(summary_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 0.15 * inch))
        
        # 3. Triggered Rules Section
        story.append(Paragraph("DETECTED RISK SIGNALS & RED FLAGS", section_style))
        if not triggered_rules:
            story.append(Paragraph("No rule violations triggered for this customer.", body_style))
        else:
            rule_rows = [[
                Paragraph("<b>Code</b>", header_key_style),
                Paragraph("<b>Risk Rule Triggered</b>", header_key_style),
                Paragraph("<b>Weight</b>", header_key_style),
                Paragraph("<b>Flag Details</b>", header_key_style)
            ]]
            for r in triggered_rules:
                rule_rows.append([
                    Paragraph(r['rule_id'], header_val_style),
                    Paragraph(f"<b>{r['name']}</b>", header_val_style),
                    Paragraph(str(r['weight']), header_val_style),
                    Paragraph(r['details'], header_val_style)
                ])
            t_rules = Table(rule_rows, colWidths=[1.2 * inch, 1.8 * inch, 0.6 * inch, 3.8 * inch])
            t_rules.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(t_rules)
            
        story.append(Spacer(1, 0.15 * inch))
        
        # 4. AI Compliance Case Evaluation (Multi-line formatted text)
        story.append(Paragraph("AI-POWERED AUDIT DECISION & NARRATIVE", section_style))
        
        # Break summary into paragraph blocks for ReportLab Paragraph rendering
        summary_paragraphs = ai_summary.split("\n\n")
        for p_text in summary_paragraphs:
            clean_text = p_text.replace("\n", " ").strip()
            
            # Robust markdown replacement for rendering bolding in PDF
            parts = clean_text.split("**")
            result = []
            for idx, part in enumerate(parts):
                # Escape HTML special characters inside the text segments to prevent ReportLab XML parser crashes
                escaped_part = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if idx % 2 == 1:
                    result.append(f"<b>{escaped_part}</b>")
                else:
                    result.append(escaped_part)
            clean_text = "".join(result)
            
            if clean_text:
                story.append(Paragraph(clean_text, body_style))
                story.append(Spacer(1, 0.08 * inch))
                
        story.append(Spacer(1, 0.2 * inch))
        
        # 5. Signatures (Placed together to avoid orphans)
        sig_data = [
            [
                Paragraph("<b>PREPARED BY:</b>", header_key_style),
                Paragraph("<b>APPROVED BY:</b>", header_key_style)
            ],
            [
                Paragraph("Compliance Intelligence Agent (Gemini AI)", header_val_style),
                Paragraph("AML Audit Officer / Compliance Director", header_val_style)
            ],
            [
                Paragraph("<i>Signature generated electronically</i>", header_val_style),
                Paragraph("___________________________________<br/>Date: ________________________", header_val_style)
            ]
        ]
        t_sig = Table(sig_data, colWidths=[3.7 * inch, 3.7 * inch])
        t_sig.setStyle(TableStyle([
            ('PADDING', (0,0), (-1,-1), 4),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ]))
        
        story.append(KeepTogether([
            Spacer(1, 0.15 * inch),
            t_sig
        ]))
        
        # Build PDF
        doc.build(story)
        print(f"Compliance dossier PDF built successfully at {output_path}.")

    @staticmethod
    def generate_master_register(
        output_path: str,
        risk_df: pd.DataFrame
    ):
        """Generates a professional PDF document of the Master Risk Register."""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=12
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#1E293B'),
            spaceBefore=8,
            spaceAfter=6,
            borderColor=colors.HexColor('#CBD5E1'),
            borderWidth=0.5,
            borderPadding=4
        )
        
        body_style = ParagraphStyle(
            'BodyTextCustom',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#334155')
        )
        
        header_key_style = ParagraphStyle(
            'HeaderKey',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1E293B')
        )
        
        header_val_style = ParagraphStyle(
            'HeaderVal',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#475569')
        )

        story = []
        
        # Header Banner
        story.append(Paragraph("FEDERAL & TRUST COMPLIANCE COMMAND CENTER", title_style))
        story.append(Paragraph("<b>MASTER RISK REGISTER - AUDIT MONITORING SUMMARY</b>", ParagraphStyle('Sub', parent=body_style, textColor=colors.HexColor('#1E293B'))))
        story.append(Spacer(1, 0.1 * inch))
        
        # Summary metrics calculations
        total_audited = len(risk_df)
        crit_count = len(risk_df[risk_df["risk_level"] == "CRITICAL"])
        high_count = len(risk_df[risk_df["risk_level"] == "HIGH"])
        med_count = len(risk_df[risk_df["risk_level"] == "MEDIUM"])
        low_count = len(risk_df[risk_df["risk_level"] == "LOW"])
        
        summary_data = [
            [
                Paragraph("<b>Total Audited Portfolio:</b>", header_key_style),
                Paragraph(f"{total_audited} Accounts", header_val_style),
                Paragraph("<b>Critical Risk Cases:</b>", header_key_style),
                Paragraph(f"{crit_count} Cases (SAR Pending)", ParagraphStyle('CritCol', parent=header_val_style, textColor=colors.HexColor('#EF4444'), fontName='Helvetica-Bold'))
            ],
            [
                Paragraph("<b>High Risk Cases:</b>", header_key_style),
                Paragraph(f"{high_count} Cases", header_val_style),
                Paragraph("<b>Medium Risk Cases:</b>", header_key_style),
                Paragraph(f"{med_count} Cases", header_val_style)
            ],
            [
                Paragraph("<b>Low Risk Cases:</b>", header_key_style),
                Paragraph(f"{low_count} Cases", header_val_style),
                Paragraph("<b>Run Timestamp:</b>", header_key_style),
                Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), header_val_style)
            ]
        ]
        
        t_summary = Table(summary_data, colWidths=[1.85 * inch, 1.85 * inch, 1.85 * inch, 1.85 * inch])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 5),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 0.15 * inch))
        
        # Risk Queue Table
        story.append(Paragraph("PRIORITIZED COMPLIANCE MONITORING QUEUE (TOP 50)", section_style))
        
        # Render the top 50 records in a beautiful table
        table_rows = [[
            Paragraph("<b>ID</b>", header_key_style),
            Paragraph("<b>Client Name</b>", header_key_style),
            Paragraph("<b>Risk Score</b>", header_key_style),
            Paragraph("<b>Risk Tier</b>", header_key_style),
            Paragraph("<b>Flags</b>", header_key_style),
            Paragraph("<b>Triggered Alerts</b>", header_key_style)
        ]]
        
        top_records = risk_df.head(50)
        for _, row in top_records.iterrows():
            level = row["risk_level"]
            score = row["risk_score"]
            badge_color = colors.HexColor('#EF4444') if level == "CRITICAL" else colors.HexColor('#F97316') if level == "HIGH" else colors.HexColor('#EAB308') if level == "MEDIUM" else colors.HexColor('#22C55E')
            
            # Truncate rules list if too long
            rules_str = str(row["rules_triggered_ids"])
            if len(rules_str) > 42:
                rules_str = rules_str[:39] + "..."
            if not rules_str or rules_str == "nan":
                rules_str = "None"
                
            table_rows.append([
                Paragraph(row["customer_id"], header_val_style),
                Paragraph(row["full_name"], header_val_style),
                Paragraph(f"<b>{score}</b>", ParagraphStyle('Scr', parent=header_val_style, textColor=badge_color, fontName='Helvetica-Bold')),
                Paragraph(level, ParagraphStyle('Lvl', parent=header_val_style, textColor=badge_color, fontName='Helvetica-Bold')),
                Paragraph(str(row["rules_triggered_count"]), header_val_style),
                Paragraph(rules_str, header_val_style)
            ])
            
        t_queue = Table(table_rows, colWidths=[0.8 * inch, 1.8 * inch, 0.8 * inch, 0.8 * inch, 0.6 * inch, 2.6 * inch])
        t_queue.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_queue)
        
        doc.build(story)
        print(f"Master Register PDF built successfully at {output_path}.")
