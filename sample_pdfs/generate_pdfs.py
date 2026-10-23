"""Generate four FICTIONAL supplier RFP responses (no real companies or data).

Procurement request: Meridian Manufacturing Ltd (fictional) needs a cloud Procurement &
Supplier Management Platform. Run:  python sample_pdfs/generate_pdfs.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).parent
REQ = "RFP-2026-017: Cloud Procurement & Supplier Management Platform for Meridian Manufacturing Ltd"

P = {}  # supplier -> dict of content

P["Apex Systems"] = dict(
    file="Apex_Systems_RFP_Response.pdf", tagline="Engineering-led, security-first delivery",
    summary=[
        "Apex Systems understands that Meridian Manufacturing needs one platform to manage sourcing events, "
        "supplier onboarding, contracts and spend analytics across 14 plants, replacing three disconnected tools.",
        "We propose a cloud-native platform built on a microservice architecture with a documented REST and "
        "event API, deployed on Kubernetes across two availability zones. Our design targets 99.95% availability "
        "and has been load tested to 5,000 concurrent users, five times Meridian's projected peak."],
    solution=[
        "<b>Architecture.</b> Stateless microservices behind an API gateway, PostgreSQL with synchronous replication, "
        "and a message bus for asynchronous workflows. Horizontal autoscaling is configured for the sourcing, "
        "supplier-portal and analytics services independently.",
        "<b>Integrations.</b> Certified connectors for SAP S/4HANA and Microsoft Dynamics 365, SSO through SAML 2.0 "
        "and OpenID Connect, and a bulk-import API for the legacy supplier master. Integration specifications are "
        "delivered in week 3 and tested in a dedicated sandbox before each release.",
        "<b>Scalability.</b> Capacity tests show linear scaling to 20 million line items with p95 page response "
        "under 1.2 seconds."],
    timeline=[
        "Delivery runs 9 months in four phases. Our delivery team is 11 people: a project manager, two architects, "
        "five engineers, a QA lead, a security engineer and a change-management consultant."],
    milestones=[["Milestone", "Month", "Deliverable"],
                ["Design sign-off", "2", "Architecture and integration specifications"],
                ["Core platform release", "5", "Sourcing, supplier portal, contracts"],
                ["Integration complete", "7", "SAP and Dynamics connectors in production-like test"],
                ["Go-live", "9", "Phased rollout to 14 plants"]],
    price=[["Item", "Cost (USD)"], ["Licence, years 1-3", "210,000"], ["Implementation services", "180,000"],
           ["Integration and migration", "60,000"], ["Training", "30,000"], ["Total (3 years)", "480,000"]],
    assumptions="Fixed price for the scope above. Excludes travel, third-party licences and changes after design "
                "sign-off, which are charged at USD 1,100 per day.",
    security=[
        "Apex holds ISO 27001 and SOC 2 Type II certifications (reports available under NDA). Data is encrypted at "
        "rest with AES-256 and in transit with TLS 1.3, with customer-managed keys optional.",
        "Role-based access control, mandatory MFA, immutable audit logs retained 7 years, annual third-party "
        "penetration tests and a GDPR-aligned data processing agreement with EU data residency.",
        "<b>Key risks.</b> Integration with the legacy ERP is the main technical risk; mitigated by an early "
        "proof-of-concept. A 9-month schedule leaves limited room for scope growth."],
    support=[
        "Business-hours support (08:00-18:00 CET) is included; 24x7 support is available at an extra USD 40,000 a year. "
        "Incident response targets are 4 hours for severity 1.",
        "Apex has delivered 6 comparable procurement platforms over 8 years. References are available on request."])

P["BrightPath Tech"] = dict(
    file="BrightPath_Tech_RFP_Response.pdf", tagline="Fast, affordable, simple",
    summary=[
        "BrightPath Tech offers Meridian a ready-to-use procurement platform at the lowest price in the market "
        "and can go live in 4 months.",
        "Our product is a multi-tenant web application that covers supplier onboarding, quotations and basic reports."],
    solution=[
        "<b>Solution.</b> A configurable multi-tenant web application hosted in a single cloud region. Standard "
        "workflows are included; custom workflows are possible but not detailed in this response.",
        "<b>Integrations.</b> We provide CSV import and export and a basic API. ERP connectors can be built "
        "if required."],
    timeline=[
        "We will complete the project in 4 months with a team of 4 (project lead, two developers, one tester). "
        "A detailed plan will be shared after contract signature."],
    milestones=[["Milestone", "Month", "Deliverable"],
                ["Kick-off", "1", "Configuration workshop"],
                ["Pilot", "3", "Pilot at one plant"],
                ["Go-live", "4", "All plants"]],
    price=[["Item", "Cost (USD)"], ["Licence, years 1-3", "120,000"], ["Implementation", "70,000"],
           ["Training", "20,000"], ["Total (3 years)", "210,000"]],
    assumptions="Price is indicative and based on a standard configuration. Integration work and data migration "
                "are not included.",
    security=[
        "BrightPath follows industry-standard security practices and encrypts data in transit. "
        "Formal certification is planned for next year. Details of access controls and audit logging "
        "can be provided later.",
        "<b>Risks.</b> The aggressive schedule and the small team are the main risks."],
    support=[
        "Email support is available on business days with a response within 2 business days. "
        "BrightPath was founded 2 years ago and has completed 3 projects, none yet in manufacturing."])

P["NexaWorks"] = dict(
    file="NexaWorks_RFP_Response.pdf", tagline="A plan you can hold us to",
    summary=[
        "NexaWorks proposes a balanced, low-risk programme for Meridian Manufacturing: a proven platform, a "
        "detailed delivery plan and a support model designed around plant operations.",
        "Our solution is a cloud platform with modular sourcing, supplier management and contract components "
        "that Meridian can switch on in stages."],
    solution=[
        "<b>Architecture.</b> Modular cloud application with a documented REST API, hosted in two regions with "
        "daily backups and a recovery time objective of 4 hours.",
        "<b>Integrations.</b> Standard connectors for SAP and Oracle ERP, SSO via SAML 2.0, and a "
        "data-migration toolkit. Interfaces are documented in the design phase."],
    timeline=[
        "The programme runs 6 months in five phases with a dedicated team of 9: programme manager, business analyst, "
        "three engineers, two testers, a trainer and a support lead. Weekly steering reports and a shared risk "
        "register are included. Each phase has entry and exit criteria and a named Meridian approver.",
        "<b>Risk plan.</b> Top five risks are tracked with owners and mitigations: data-quality in the supplier master, "
        "ERP interface delays, user adoption, plant availability for testing, and scope change. Contingency of "
        "two weeks is built into the schedule."],
    milestones=[["Milestone", "Week", "Deliverable"],
                ["Mobilisation", "2", "Project charter, RACI, risk register"],
                ["Design sign-off", "6", "Process and interface design"],
                ["Build complete", "14", "Configured platform, migrated test data"],
                ["User acceptance", "20", "UAT signed off by Meridian"],
                ["Go-live", "24", "Phased rollout, hypercare for 6 weeks"]],
    price=[["Item", "Cost (USD)"], ["Licence, years 1-3", "165,000"], ["Implementation services", "110,000"],
           ["Integration and migration", "45,000"], ["Training and hypercare", "20,000"],
           ["Total (3 years)", "340,000"]],
    assumptions="Fixed price. Includes up to 3 ERP interfaces and 250 users in year 1. Additional users are USD 220 "
                "per user per year. Travel is billed at cost.",
    security=[
        "NexaWorks is ISO 27001 certified. SOC 2 Type II is in progress, with the audit window closing in Q1. "
        "Data is encrypted at rest and in transit, access is role-based with MFA, and audit logs are retained "
        "for 3 years. GDPR data processing terms are provided."],
    support=[
        "24x7 support with a 1-hour response for severity 1 incidents is included in the licence. Meridian "
        "receives a named customer success manager, quarterly service reviews and a monthly release calendar.",
        "NexaWorks has 7 years in business and 14 comparable projects. Two references are listed: a European "
        "auto-parts group and a regional food manufacturer."])

P["Orbit Digital"] = dict(
    file="Orbit_Digital_RFP_Response.pdf", tagline="Fifteen years of procurement transformation",
    summary=[
        "Orbit Digital has delivered procurement platforms for 40+ enterprise clients over 15 years, including "
        "12 manufacturers similar to Meridian. We propose to bring that experience to this programme.",
        "Our platform covers sourcing, supplier management and contract lifecycle, delivered as a cloud service."],
    solution=[
        "<b>Solution.</b> A mature cloud platform with a broad feature set. Specific integrations with "
        "Meridian's systems will be defined during discovery and agreed with Meridian's IT team.",
        "<b>Technical approach.</b> The technical approach will be finalised after discovery. Orbit will work with "
        "Meridian to identify the best way to connect the platform to existing systems."],
    timeline=[
        "We expect the project to take 7 to 8 months, depending on the outcome of discovery. The team will be "
        "assembled from our delivery pool; named resources will be confirmed at contract."],
    milestones=[["Milestone", "Month", "Deliverable"],
                ["Discovery", "2", "Findings and recommended approach"],
                ["Implementation", "3-7", "To be agreed"],
                ["Go-live", "8", "Rollout"]],
    price=[["Item", "Cost (USD)"], ["Licence, years 1-3", "190,000"], ["Implementation services", "130,000"],
           ["Training", "40,000"], ["Total (3 years)", "360,000"]],
    assumptions="Price assumes a typical integration scope. The final price will be confirmed after discovery.",
    security=[
        "Orbit is SOC 2 Type II compliant and encrypts data in transit and at rest. Security policies are "
        "reviewed annually. Penetration test summaries are available on request."],
    support=[
        "Orbit has delivered procurement platforms for 40+ clients over 15 years, including 12 manufacturers. "
        "Support is available 24x7 for severity 1 issues with a 2-hour response and an account director.",
        "<b>References.</b> Four client references are provided: Northfield Steel, Kestrel Packaging, "
        "Almeda Foods and Vantor Automotive, each with a named contact and a project summary."])


def build(name, c):
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=4,
                       textColor=colors.HexColor("#1F3A5F"))
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=11, leading=16, spaceAfter=5)
    title = ParagraphStyle("t", parent=ss["Title"], fontSize=20, spaceAfter=2)
    sub = ParagraphStyle("s", parent=ss["BodyText"], fontSize=9, textColor=colors.grey)

    def table(data, widths):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 10),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    s = [Paragraph(f"{name}", title), Paragraph(c["tagline"], sub),
         Paragraph(f"Response to {REQ}. FICTIONAL document for training use.", sub), Spacer(1, 6)]
    s.append(Paragraph("1. Executive Summary and Understanding of the Requirement", h))
    s += [Paragraph(t, body) for t in c["summary"]]
    s.append(Paragraph("2. Proposed Solution and Approach", h))
    s += [Paragraph(t, body) for t in c["solution"]]
    s.append(Paragraph("3. Timeline, Team and Milestones", h))
    s += [Paragraph(t, body) for t in c["timeline"]]
    s += [Spacer(1, 4), table(c["milestones"], [5 * cm, 2 * cm, 9.5 * cm])]
    s.append(PageBreak())
    s.append(Paragraph("4. Price and Assumptions", h))
    s += [table(c["price"], [9 * cm, 4 * cm]), Spacer(1, 4),
          Paragraph(f"<b>Assumptions:</b> {c['assumptions']}", body)]
    s.append(Paragraph("5. Security, Compliance and Risk Controls", h))
    s += [Paragraph(t, body) for t in c["security"]]
    s.append(Paragraph("6. Support Model, Experience and References", h))
    s += [Paragraph(t, body) for t in c["support"]]
    doc = SimpleDocTemplate(str(OUT / c["file"]), pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                            topMargin=2.2 * cm, bottomMargin=2.2 * cm, title=f"{name} - RFP Response",
                            author=name)
    doc.build(s)


if __name__ == "__main__":
    for n, c in P.items():
        build(n, c)
        print("wrote", c["file"])
