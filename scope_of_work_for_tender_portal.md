Key public references used while preparing this SoW: BidAssist product
pages & pricing (features, alerts, documents). (BidAssist) BidAssist
product comparison / AI features description. (BidAssist) Government
eProcurement / CPP Portal (eprocure.gov.in) as the central source for
central tenders. (Central Public Procurement Portal) GeM API
documentation and integration notes (GeM provides REST APIs). (Gem Help
Center) State eProcurement portal index (list of state portals / guide).
(Central Public Procurement Portal) Best-practice notes for tender
aggregation & validation. (GroupBWT)

1 --- Executive summary (what we will deliver) Build a SaaS platform
that: Aggregates tenders from ALL relevant public sources (Central CPPP,
GeM, all State/UT e-procurement portals, department websites / RSS / PDF
notices). Normalizes & deduplicates notices across sources into a single
searchable catalogue. Extracts structured data (NIT, deadline, BOQ,
eligibility, EMD, contact, corrigenda, tender results) using parsing +
OCR + ML. Turns raw tenders into actionable workflows for bidders:
alerts (email/SMS/WhatsApp/push), personalized tender recommendations,
team bid workspace, document download & management, reminders, and
analytics. Admin & commercial modules for subscriptions, per-document
paywalls, enterprise accounts and billing. APIs & integrations so
corporate customers can pull tender feeds into their ERP/CRM. This is
functionally similar to BidAssist (search, alerts, docs, AI-driven
summaries and BoQ extraction) but with a heavier emphasis on automated
data ingestion across very heterogeneous public sources. (BidAssist)

2 --- Sources to ingest (concrete list) Primary sources to crawl /
integrate (priority order): Central eProcurement / CPP Portal
(eprocure.gov.in / epublish) --- central notices, corrigenda, bid
results. (Official system). (Central Public Procurement Portal)
Government eMarketplace (GeM) --- use official REST APIs where
applicable for RFQs, reverse auctions, and orders. (Gem Help Center)
State & UT eProcurement Portals --- each State runs its own NIC / vendor
portal; harvest via connectors and crawlers. (List is published by
CPPP). (Central Public Procurement Portal) Sector / Department websites
(eg. Municipal corporations, Public Works Dept, PSUs, health institutes)
that publish PDFs / HTML posts but do not use eprocurement portals.
Other public tender aggregators, trade journals, newspapers for offline
tenders (as additional feed). Tender results / award announcements pages
(to capture award history and competitor intel). Each source will be
handled by an appropriate connector: API connector (preferred), RSS if
available, structured HTML parser, or site-specific crawler + PDF
scraper + OCR.

3 --- Functional scope (high level modules) A. Data ingestion &
processing Connectors GeM API connector (authenticated). (Gem Help
Center) CPPP / eProcure API or structured export connectors. State
portal connectors (one per state/major portal) with retry & rate-limit
handling. Generic website crawler for departments (sitemaps, RSS, HTML
scraping). Email ingest (if some departments send notices via email).
Document fetcher Auto-download attachments (PDF/DOC/XLSX) on
publication. Handle paywalls / protected doc download workflows (for
those that require registration). PDF parsing & OCR Structured field
extraction (NIT, issue date, bid close date/time, pre-bid meeting, EMD,
BoQ, eligibility, contact). Table / BOQ extraction (tabular PDFs) +
CSV/XLSX export. Normalization, deduplication & canonicalization
Normalize fields (dates in ISO, amounts). Fingerprint and dedupe
duplicates across multiple sources. NLP & enrichment Tender
classification (category / CPV codes / commodity tags).
Auto-summarization (short summary + important highlights) and keyword
extraction. Eligibility & pre-qualification flags (work experience,
turnover, financial criteria). BoQ/qty extraction and searchable unit
rates. Human-in-the-loop verification Interface for operators to
review/confirm auto-parsed tenders and correct parsing errors. B.
Search, filters & discovery (bidder UX) Global search with keyword,
advanced boolean, date range, geolocation, department, CPV/category,
value range. Saved searches & smart filters (industry verticals, states,
tender types). Personalized recommendations (ML-based: user profile,
past views, saved firms). Full-text search inside tender documents and
BOQs. Similar tenders suggestions and historical precedent. C. Alerts &
notifications Multi-channel alerts: email, in-app push, SMS, WhatsApp
(official APIs), and daily digest. (BidAssist style). (BidAssist)
Trigger types: new tender, corrigendum, extension, award result, bid
closing in X days. Enterprise notification rules (teams can subscribe by
state/department/category). D. Tender document & cost management
Document download management (tracking downloads per-user for
subscription billing). Per-document paywall options (single document
purchase vs subscription plans). Document repository: versioning,
corrigendum linking (original tender → corrigenda → final award). DSC /
eSigning integration (for future modules to prepare signed submissions).
E. Bid Management workspace (collaboration) Project board per tender
(tasks, deadlines, owner, attachments). Multi-user workspaces / roles
(bid manager, technical writer, finance reviewer). Checklists &
templates for common bid documents (cover letter, bank guarantee).
Reminders & calendar synced with Google/Outlook. Bid/no-bid scoring &
approval workflow. F. Analytics & market intelligence Dashboards:
tenders by state/department/category, value trends, win/loss rates.
Competitive intelligence: track which companies win which tenders
(awards). BOQ benchmarking (compare rates across tenders). Exportable
reports (PDF/CSV) and scheduled reports. G. Admin, billing & legal
Subscription management (multiple plans, trial, enterprise).
Per-document micropayments & invoices (GST compliant). User & role
management (multi-organization). Audit logs and usage metering. Support
& dispute workflows (document errors, data issues). H. APIs &
integrations REST API / webhooks for customers to consume filtered feeds
(JSON). Connectors: CRM (Salesforce), ERP, accounting, Slack/MS Teams,
SSO (SAML/OAuth).

4 --- Data model: important fields to extract for each tender Minimum
canonical fields: source, source_url, source_id publication_date,
bid_open_date, bid_close_date (ISO datetime) tender_id / NIT number
department / organization, contact person, phone/email tender value /
estimate / EMD / bid document fee pre-bid meeting date/time & venue
tender type (Open/NIT/RFP/EOI/Auction) procurement category / CPV code /
commodity tags eligibility criteria (work experience, financial
turnover) --- parsed into structured fields BOQ (line items:
description, qty, unit, estimated rate) --- tabular extraction
corrigenda list (linking to original) award details (winning bidder,
value, date) if available

5 --- Non-functional requirements (NFRs) Scalability: support ingestion
of 25k+ daily notices and 100k+ daily fetches; horizontally scalable
microservices. (BidAssist states \~25k/day). (BidAssist) Availability:
99.9% for user-facing APIs; 99% for ingestion pipelines. Latency: new
tenders visible in the platform within X minutes of publication (target
configurable per source). Security: OWASP top-10 mitigation, TLS
everywhere, data-at-rest encryption, RBAC, audit logs. GDPR/Indian
privacy compliance as applicable (data retention policies). Backup & DR:
daily backups and 24--48 hour recovery RTO.

6 --- Technical architecture (recommended) Ingestion Layer (connectors)
--- workers for API pulls, RSS/pollers, site-specific scrapers, PDF
fetcher. Processing Layer --- document parser, OCR engine (Tesseract or
commercial like Abbyy if budget allows), NLP services for classification
& extraction (spaCy/transformer models), dedupe/fingerprint service.
Storage --- object store (S3) for documents; relational DB (Postgres)
for canonical records; search engine (Elasticsearch / OpenSearch) for
full-text & faceted search; data warehouse for analytics. Application
Layer --- microservices for search, alerts, billing, user management.
Front-end --- React (responsive), progressive web app + mobile apps
(optional). API Gateway --- public REST APIs and webhook endpoints.
Monitoring & Logging --- Prometheus/Grafana, ELK stack. CDN & Load
Balancer --- for static assets and global performance. Design the
architecture to allow rapid addition of new connectors for state portals
and department sites.

7 --- Quality, testing & accuracy expectations Parsing accuracy targets:
aim for ≥ 85% automatic field-extraction accuracy on well-structured
tenders, with human verification to reach 98% for mission-critical
fields (dates, EMD, deadlines). Deduplication correctness: false
positives \< 1%. Search relevance: measure click-through & relevance via
A/B tests. Regression tests: for each connector when source site design
changes. Reference: tender aggregation projects benefit from
human-in-loop verification to reach production accuracy. (GroupBWT)

8 --- Operational runbook & support On-call rota for ingestion
failures/connector breakages. Connector health dashboard (last
successful fetch, errors, item count). SLA for connector fix (e.g.,
severity 1: 4 hours, severity 2: 48 hours). Manual override tools for
operators to add/modify tenders. Customer support: ticketing, chat,
phone (enterprise).

9 --- Deliverables (phased) Phase 1 --- MVP (8--12 weeks) Connectors:
CPPP central + GeM API + top 5 State portals. (Central Public
Procurement Portal) Core ingestion pipeline, PDF fetcher & OCR. Basic
parsing for key fields + deduplication. Search and saved searches.
Alerts by email and in-app. Admin portal and subscription management.
REST API for push/outbound feeds. Phase 2 --- Core features (12 more
weeks) All state connectors added (remaining). Advanced BOQ extraction,
full-text search, AI summarization. Multi-channel alerts (SMS,
WhatsApp), team workspaces, bid board. Billing / per-document
micropayment module. Phase 3 --- Scale & polish (ongoing) Analytics
dashboards, competitor tracking, mobile apps, 3rd party integrations,
enterprise SSO. (Timelines are indicative --- actual durations depend on
team size & budget.)

10 --- Team composition & roles (recommended) Product Manager (1) ---
scope, prioritization, client demos. Backend Engineers (2--3) ---
ingestion, APIs, DB. Frontend Engineers (2) --- web UI + dashboards.
ML/NLP Engineer (1--2) --- parsing, classification, BOQ extraction. QA
Engineer (1) --- automated tests, regression. DevOps (1) --- infra,
monitoring, CI/CD. Data Ops / Operators (1--2) --- human verification &
connector maintenance. Designer (part-time) --- UX for bid flow.
Customer Success / Support (1) --- onboarding enterprise customers.

11 --- Acceptance criteria & KPIs Coverage KPI: \>= 95% of tenders
published on integrated sources appear in system within 60 min. Quality
KPI: parsing accuracy \>= 90% for critical fields (closing date, tender
id, value). Uptime: 99.9% for user-facing APIs. User-engagement: X saved
searches / active users on monthly basis (define per client).
Time-to-market: MVP in 8--12 weeks (for experienced team).

12 --- Cost drivers & licensing Major cost drivers: Team headcount and
duration. OCR & extraction licensing (open-source OCR vs paid engines).
WhatsApp/SMS costs (per-message). Cloud hosting & storage (documents can
be large). Third-party data sources that may require paid access or
registration. Ongoing maintenance for broken connectors (site
redesigns).

13 --- Legal & compliance considerations Respect the terms of service
for each source: some sites disallow automated scraping --- prefer API
use & partnership agreements (e.g., GeM offers APIs). (Gem Help Center)
Data retention, privacy and user consent for outbound messages
(SMS/WhatsApp). Provide takedown / dispute workflow if a department
complains about content. Tax compliance for subscriptions / invoices
(GST).

14 --- Suggested SLAs & operational metrics for customers New tender
delivery SLA: within 1 hour for central/GeM sources, within 6 hours for
department sites (configurable). Data-correction SLA: respond to data
correction ticket within 24 hours. Connector outage notification: alert
customers if a major source stops updating.

15 --- Sample acceptance test cases (examples) Upload a tender PDF with
a complex BOQ --- verify BOQ items parsed into structured rows with
units & quantities. Publish same tender on two sources --- verify
deduplication and single canonical record referencing both sources.
Create saved search → verify email & WhatsApp alerts triggered for
matching new tenders. Enterprise user: create workspace, add users,
assign bid tasks & remind 3 days before close.

16 --- Next steps I can take for you (I already did public research) I
made the SoW using public pages and docs. If you want me to go deeper
and produce: (A) A line-item technical RFP (detailed API spec, DB
schema, acceptance tests), or (B) A cost estimate (T&M and fixed-price
options), or (C) A competitor feature-mapping matrix (BidAssist vs
TenderTiger vs TenderTiger Neo vs TenderNxt etc.) with screenshots and
product-parity table --- I can do any of those right now. If you want
exact feature parity with your current BidAssist subscription (match
their UI behavior, alert wording, exact BoQ extraction examples), you
can optionally provide the BidAssist account credentials --- I can log
in and extract exact feature/UX details and produce a feature-by-feature
parity report and a prioritized dev backlog. (If you provide
credentials, mark them private --- I will use them only to review the
product UI & documents for this task.)

Short prioritized checklist you can hand to devs tomorrow Build
connectors for CPPP & GeM (use APIs where available). (Central Public
Procurement Portal) Implement robust PDF downloader + OCR + field
extractor. Implement Elasticsearch-driven search + saved searches +
alerts (email). Admin console for subscriptions & per-document billing.
Human verification UI to improve parsing accuracy. Add WhatsApp & SMS
alerting and team workspaces. Add state connectors in waves, monitoring
connector health.
