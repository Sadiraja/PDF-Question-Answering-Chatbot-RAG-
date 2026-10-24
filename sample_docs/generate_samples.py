import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_ai_healthcare_pdf(filename="sample_docs/AI_Healthcare_Whitepaper.pdf"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54
    )
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E40AF'),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=8
    )
    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E3A8A'),
        backColor=colors.HexColor('#EFF6FF'),
        borderColor=colors.HexColor('#93C5FD'),
        borderWidth=1,
        borderPadding=8,
        spaceAfter=10
    )

    story = []

    # --- PAGE 1 ---
    story.append(Paragraph("Clinical Whitepaper: Artificial Intelligence in Modern Diagnostic Radiology", title_style))
    story.append(Paragraph("<b>Document ID:</b> MED-AI-2024-V2 | <b>Release Date:</b> October 2024 | <b>Author:</b> Global Healthcare AI Consortium", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Executive Summary & Overview", h2_style))
    story.append(Paragraph(
        "Artificial Intelligence (AI) and deep convolutional neural networks (CNNs) have emerged as pivotal tools in augmenting clinical radiology workflows. "
        "This whitepaper documents the clinical validation, regulatory architecture, and technical benchmarks of the <b>PulseVision-AI platform</b>, "
        "designed specifically for automated triage and computer-aided detection (CADe) of thoracic abnormalities in emergency department settings.",
        body_style
    ))

    story.append(Paragraph("2. Diagnostic Model Performance (CheXNet-Pro Engine)", h2_style))
    story.append(Paragraph(
        "The underlying diagnostic inference engine, designated as <b>CheXNet-Pro v2.4</b>, was evaluated on a curated multi-center dataset of 142,500 chest radiographs. "
        "In prospective clinical trials across 12 academic medical centers, the model demonstrated an overall sensitivity of <b>94.7%</b> and a specificity of <b>91.3%</b> "
        "in identifying malignant pulmonary nodules (>6mm). For tension pneumothorax triage, CheXNet-Pro achieved an area under the receiver operating characteristic curve (AUROC) of <b>0.982</b>.",
        body_style
    ))

    story.append(Paragraph(
        "<b>Key Benchmark Summary:</b> The model reduced average time-to-treatment for critical findings from 74 minutes to 11.5 minutes, resulting in an 84.4% reduction in reporting latency.",
        callout_style
    ))

    story.append(PageBreak())

    # --- PAGE 2 ---
    story.append(Paragraph("3. Clinical Workflow & DICOM / PACS Integration", h2_style))
    story.append(Paragraph(
        "Integration into hospital IT ecosystems is accomplished via zero-footprint microservices adhering to DICOM 3.0 and HL7 FHIR standards. "
        "Upon completion of a thoracic computed tomography (CT) scan or plain film radiograph, images are routed through the secure hospital PACS gateway "
        "to the local inference node. Processing latency is strictly governed under a Service Level Agreement (SLA) of <b>less than 1.8 seconds per volumetric CT series</b>.",
        body_style
    ))

    story.append(Paragraph("4. Hardware Specifications & Edge Inference", h2_style))
    story.append(Paragraph(
        "To guarantee high availability even during external network interruptions, inference is conducted on on-premise edge servers. "
        "Each diagnostic node is equipped with dual NVIDIA RTX 6000 Ada Generation GPUs (96 GB total VRAM) and an AMD EPYC 9354 32-core processor. "
        "Power redundancy is backed by dual 1600W hot-swappable titanium-grade power supplies providing 4 hours of uninterrupted battery backup.",
        body_style
    ))

    story.append(PageBreak())

    # --- PAGE 3 ---
    story.append(Paragraph("5. Regulatory Clearances & Quality Management", h2_style))
    story.append(Paragraph(
        "PulseVision-AI has achieved regulatory clearance under the United States Food and Drug Administration (FDA) <b>510(k) pathway (K233912)</b> as a Class II Software as a Medical Device (SaMD). "
        "The clearance adheres strictly to the FDA's June 2024 Good Machine Learning Practice (GMLP) guidelines. "
        "In the European Union, the system holds CE Mark certification under the Medical Device Regulation (EU MDR 2017/745), categorized as Class IIb software.",
        body_style
    ))

    story.append(Paragraph("6. Algorithmic Drift Monitoring & Post-Market Surveillance", h2_style))
    story.append(Paragraph(
        "To mitigate dataset shift and population drift over time, the system implements continuous statistical monitoring using Population Stability Index (PSI) calculations. "
        "Whenever the PSI metric exceeds the threshold of <b>0.15</b> over a rolling 30-day window, automated alerts are dispatched to the lead medical physicist, "
        "triggering a mandatory model recalibration and blind clinical audit before re-certification.",
        body_style
    ))

    story.append(PageBreak())

    # --- PAGE 4 ---
    story.append(Paragraph("7. Data Privacy, Encryption & HIPAA Security Safeguards", h2_style))
    story.append(Paragraph(
        "To maintain rigorous compliance with HIPAA Title II administrative and security standards, all patient health information (PHI) undergoes automated de-identification "
        "prior to secondary telemetry transmission. The de-identification protocol complies with the HIPAA <b>Safe Harbor Method</b>, systematically stripping all 18 designated personal identifiers, "
        "including patient names, geographic codes below state level, dates, and medical record numbers (MRNs).",
        body_style
    ))

    story.append(Paragraph("8. Cryptographic Protocols & Access Control", h2_style))
    story.append(Paragraph(
        "All data at rest is encrypted using <b>256-bit AES-GCM</b> cryptographic algorithms with hardware security module (HSM) managed keys. "
        "Data in transit across hospital networks requires mandatory <b>TLS 1.3</b> transport encryption with mutual certificate authentication (mTLS). "
        "User role-based access control (RBAC) mandates hardware security key (FIDO2/WebAuthn) multi-factor authentication for all clinical and administrative accounts.",
        body_style
    ))

    doc.build(story)
    print(f"Generated {filename}")

def create_company_policy_pdf(filename="sample_docs/Company_Policy_Handbook.pdf"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle2',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#134E4A'),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom2',
        parent=styles['Heading2'],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0F766E'),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body_Custom2',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=8
    )

    story = []

    # --- PAGE 1 ---
    story.append(Paragraph("Apex Innovations Employee Operations & Policy Handbook", title_style))
    story.append(Paragraph("<b>Version:</b> 2024.3 | <b>Effective Date:</b> January 1, 2024 | <b>Human Resources Department</b>", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Workplace Arrangements & Working Hours", h2_style))
    story.append(Paragraph(
        "Apex Innovations operates under a flexible hybrid working framework. Standard office core collaboration hours are from "
        "<b>10:00 AM to 4:00 PM Eastern Standard Time (EST)</b>, Monday through Friday. All full-time employees are expected to be reachable and active during these hours.",
        body_style
    ))

    story.append(Paragraph("2. Hybrid Work Policy & Office Attendance", h2_style))
    story.append(Paragraph(
        "Employees assigned to hybrid status are required to work a minimum of <b>2 days per week on-site</b> at their designated regional office, "
        "with the remaining 3 days permitted as remote work from home. Remote work outside the country of employment is permitted for up to a maximum of <b>30 consecutive calendar days per year</b>, "
        "subject to prior written authorization from HR and IT compliance.",
        body_style
    ))

    story.append(PageBreak())

    # --- PAGE 2 ---
    story.append(Paragraph("3. Paid Time Off (PTO) & Leave Allocations", h2_style))
    story.append(Paragraph(
        "Full-time permanent employees accrue <b>25 business days of paid annual vacation</b> per calendar year, accrued on a semi-monthly basis. "
        "In addition, employees receive <b>10 days of paid medical/sick leave</b> annually, which does not require medical practitioner verification for absences of 2 days or fewer.",
        body_style
    ))

    story.append(Paragraph("4. Parental Leave Entitlements", h2_style))
    story.append(Paragraph(
        "New parents, whether through birth, adoption, or surrogacy, are entitled to <b>16 weeks of fully paid parental leave</b> for the primary caregiver, "
        "and <b>8 weeks of fully paid leave</b> for the secondary caregiver. This leave must be taken within the first 12 months following the qualifying event.",
        body_style
    ))

    story.append(Paragraph("5. PTO Request Protocol", h2_style))
    story.append(Paragraph(
        "Any scheduled PTO request exceeding 3 consecutive working days must be submitted through the internal HR portal at least <b>14 calendar days in advance</b>. "
        "A maximum of 5 unused vacation days may be rolled over into the subsequent calendar year, expiring on March 31.",
        body_style
    ))

    story.append(PageBreak())

    # --- PAGE 3 ---
    story.append(Paragraph("6. Expense Reimbursement Guidelines", h2_style))
    story.append(Paragraph(
        "Business-related expenses incurred on behalf of the company must be submitted via the Concur expense portal within <b>30 calendar days of purchase</b>. "
        "Itemized receipts are strictly mandatory for all expenditures exceeding <b>$25.00 USD</b>. Daily meal allowances during approved travel are capped at <b>$75.00 USD per diem</b>.",
        body_style
    ))

    story.append(Paragraph("7. Home Office & Equipment Stipend", h2_style))
    story.append(Paragraph(
        "To support ergonomic and productive remote working conditions, new full-time hires are provided a one-time home office equipment stipend of <b>$1,200.00 USD</b>, "
        "usable for monitors, ergonomic chairs, desks, and peripheral devices. In addition, an ongoing monthly remote connectivity subsidy of <b>$60.00 USD</b> is credited on monthly payroll.",
        body_style
    ))

    story.append(Paragraph("8. Information Security & Hardware Guidelines", h2_style))
    story.append(Paragraph(
        "Company-issued laptops are encrypted and monitored. Connecting personal USB flash drives or unapproved external mass storage devices to company hardware is strictly prohibited. "
        "Multi-Factor Authentication (MFA) via authenticator app or hardware token is mandatory across all enterprise cloud services.",
        body_style
    ))

    doc.build(story)
    print(f"Generated {filename}")

if __name__ == "__main__":
    create_ai_healthcare_pdf()
    create_company_policy_pdf()
