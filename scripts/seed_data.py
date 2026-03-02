"""Seed the database with sample tenders for development."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.database import async_session, init_db
from backend.models.tender import Tender, TenderSource, TenderType, TenderStatus
from backend.models.user import User, Organization, Subscription, UserRole, SubscriptionPlan
from backend.services.auth_service import hash_password
from backend.services.dedup import generate_fingerprint

SAMPLE_TENDERS = [
    {
        "source": TenderSource.CPPP,
        "title": "Construction of 4-Lane Highway from NH-44 to Agra Bypass including ROBs and Underpasses",
        "department": "National Highways Authority of India",
        "state": "Central",
        "category": "Civil Construction",
        "tender_type": TenderType.OPEN_TENDER,
        "tender_value_estimated": Decimal("450000000"),
        "emd_amount": Decimal("9000000"),
        "document_fee": Decimal("50000"),
    },
    {
        "source": TenderSource.GEM,
        "title": "Supply of 5000 Desktop Computers with i7 Processor and 16GB RAM for Government Offices",
        "department": "Ministry of Electronics and IT",
        "state": "Central",
        "category": "IT Equipment",
        "tender_type": TenderType.RFQ,
        "tender_value_estimated": Decimal("25000000"),
        "emd_amount": Decimal("500000"),
    },
    {
        "source": TenderSource.UP,
        "title": "Construction of District Hospital Building at Prayagraj with 200 Bed Capacity",
        "department": "UP Public Works Department",
        "state": "Uttar Pradesh",
        "category": "Medical Infrastructure",
        "tender_type": TenderType.NIT,
        "tender_value_estimated": Decimal("180000000"),
        "emd_amount": Decimal("3600000"),
        "document_fee": Decimal("25000"),
    },
    {
        "source": TenderSource.MAHARASHTRA,
        "title": "Smart City Surveillance System Installation across Mumbai Municipal Corporation Area",
        "department": "Mumbai Municipal Corporation",
        "state": "Maharashtra",
        "category": "IT Infrastructure",
        "tender_type": TenderType.OPEN_TENDER,
        "tender_value_estimated": Decimal("120000000"),
        "emd_amount": Decimal("2400000"),
    },
    {
        "source": TenderSource.UTTARAKHAND,
        "title": "Repair and Maintenance of Char Dham Yatra Road from Rishikesh to Badrinath",
        "department": "Uttarakhand PWD",
        "state": "Uttarakhand",
        "category": "Road Maintenance",
        "tender_type": TenderType.NIT,
        "tender_value_estimated": Decimal("75000000"),
        "emd_amount": Decimal("1500000"),
        "document_fee": Decimal("10000"),
    },
    {
        "source": TenderSource.HARYANA,
        "title": "Installation of Solar Power Plant 10MW at Industrial Estate Gurugram",
        "department": "Haryana Renewable Energy Department",
        "state": "Haryana",
        "category": "Renewable Energy",
        "tender_type": TenderType.OPEN_TENDER,
        "tender_value_estimated": Decimal("350000000"),
        "emd_amount": Decimal("7000000"),
    },
    {
        "source": TenderSource.MP,
        "title": "Supply and Installation of Water Treatment Plant 50 MLD at Bhopal City",
        "department": "MP Urban Administration",
        "state": "Madhya Pradesh",
        "category": "Water Supply",
        "tender_type": TenderType.NIT,
        "tender_value_estimated": Decimal("220000000"),
        "emd_amount": Decimal("4400000"),
        "document_fee": Decimal("30000"),
    },
    {
        "source": TenderSource.CPPP,
        "title": "Annual Maintenance Contract for Railway Station Platforms and Buildings - Northern Railway",
        "department": "Indian Railways - Northern Zone",
        "state": "Central",
        "category": "Maintenance",
        "tender_type": TenderType.OPEN_TENDER,
        "tender_value_estimated": Decimal("55000000"),
        "emd_amount": Decimal("1100000"),
    },
    {
        "source": TenderSource.UP,
        "title": "Development of Industrial Park with Warehousing Facilities at Noida Special Economic Zone",
        "department": "UP Industrial Development Authority",
        "state": "Uttar Pradesh",
        "category": "Industrial Infrastructure",
        "tender_type": TenderType.RFP,
        "tender_value_estimated": Decimal("500000000"),
        "emd_amount": Decimal("10000000"),
    },
    {
        "source": TenderSource.GEM,
        "title": "Procurement of Medical Equipment including Ventilators and ECG Machines for AIIMS Network",
        "department": "Ministry of Health and Family Welfare",
        "state": "Central",
        "category": "Medical Equipment",
        "tender_type": TenderType.RFQ,
        "tender_value_estimated": Decimal("85000000"),
        "emd_amount": Decimal("1700000"),
    },
]


async def seed():
    await init_db()

    async with async_session() as db:
        # Create admin user
        admin = User(
            email="admin@tenderportal.in",
            hashed_password=hash_password("admin123"),
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
        db.add(admin)

        # Create demo user
        demo_org = Organization(name="Demo Corp")
        db.add(demo_org)
        await db.flush()

        demo_sub = Subscription(organization_id=demo_org.id, plan=SubscriptionPlan.PROFESSIONAL)
        db.add(demo_sub)

        demo_user = User(
            email="demo@example.com",
            hashed_password=hash_password("demo123"),
            full_name="Rahul Demo",
            role=UserRole.USER,
            organization_id=demo_org.id,
            preferred_states=["Uttar Pradesh", "Maharashtra"],
        )
        db.add(demo_user)

        # Create sample tenders
        now = datetime.now(timezone.utc)
        for i, data in enumerate(SAMPLE_TENDERS):
            fp = generate_fingerprint(
                f"SAMPLE-{i+1}",
                data["title"],
                data["department"],
                str(now + timedelta(days=10 + i * 3)),
            )
            tender = Tender(
                source=data["source"],
                source_url=f"https://example.gov.in/tender/{i+1}",
                source_id=f"SAMPLE-{i+1}",
                tender_id=f"NIT/{now.year}/{i+1:04d}",
                title=data["title"],
                description=f"Detailed description for: {data['title']}",
                department=data["department"],
                state=data["state"],
                category=data["category"],
                tender_type=data["tender_type"],
                tender_value_estimated=data.get("tender_value_estimated"),
                emd_amount=data.get("emd_amount"),
                document_fee=data.get("document_fee"),
                publication_date=now - timedelta(days=i * 2),
                bid_close_date=now + timedelta(days=10 + i * 3),
                status=TenderStatus.ACTIVE,
                fingerprint=fp,
                parsed_quality_score=0.85,
            )
            db.add(tender)

        await db.commit()
        print(f"✅ Seeded {len(SAMPLE_TENDERS)} tenders + 2 users (admin@tenderportal.in / demo@example.com)")


if __name__ == "__main__":
    asyncio.run(seed())
