#!/usr/bin/env python3
"""
Quick fix for the TenderDetailResponse validation error
"""

print("🔧 APPLYING QUICK BACKEND FIX")
print("=" * 31)

# Read the current tenders.py file
file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/backend/api/tenders.py'

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print("📁 Current file size:", len(content))
    
    # Find the problematic model_validate call and fix it
    old_pattern = """    data = TenderDetailResponse.model_validate(tender)
    data.documents = [
        {"id": str(d.id), "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type}
        for d in tender.documents
    ]
    data.corrigenda = [
        {"id": str(c.id), "number": c.corrigendum_number, "date": str(c.published_date), "description": c.description}
        for c in tender.corrigenda
    ]"""
    
    new_pattern = """    # Convert tender to dict and prepare documents/corrigenda separately
    tender_dict = {
        "id": str(tender.id),
        "source": tender.source,
        "source_url": tender.source_url or "",
        "source_id": tender.source_id or "",
        "tender_id": tender.tender_id or "",
        "title": tender.title or "",
        "description": tender.description or "",
        "department": tender.department or "",
        "organization": tender.organization or "",
        "state": tender.state or "",
        "category": tender.category or "",
        "procurement_category": tender.procurement_category or "",
        "tender_type": tender.tender_type or "",
        "tender_value_estimated": tender.tender_value_estimated,
        "emd_amount": tender.emd_amount,
        "document_fee": tender.document_fee,
        "publication_date": tender.publication_date,
        "bid_open_date": tender.bid_open_date,
        "bid_close_date": tender.bid_close_date,
        "pre_bid_meeting_date": tender.pre_bid_meeting_date,
        "pre_bid_meeting_venue": tender.pre_bid_meeting_venue or "",
        "contact_person": tender.contact_person or "",
        "contact_email": tender.contact_email or "",
        "contact_phone": tender.contact_phone or "",
        "eligibility_criteria": tender.eligibility_criteria,
        "status": tender.status,
        "tender_stage": tender.tender_stage,
        "created_at": tender.created_at,
        "updated_at": tender.updated_at,
        "documents": [
            {"id": str(d.id), "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type}
            for d in tender.documents
        ],
        "corrigenda": [
            {"id": str(c.id), "number": c.corrigendum_number, "date": str(c.published_date), "description": c.description}
            for c in tender.corrigenda
        ]
    }
    
    data = TenderDetailResponse.model_validate(tender_dict)"""
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print("✅ Applied fix for TenderDetailResponse validation")
        
        # Write the fixed content
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("📁 New file size:", len(content))
        print("🔄 Backend fix applied - server will auto-reload")
        
    else:
        print("❌ Could not find the exact pattern to fix")
        print("💡 The validation error might have a different cause")
        
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("🎯 TESTING STEPS:")
print("=" * 16)
print("1. Wait for backend auto-reload")
print("2. Visit: http://localhost:5174") 
print("3. Login and click a tender")
print("4. Should see tender detail page (no more blank/500 error)")
print("5. Check 'Real Documents' section with summary")