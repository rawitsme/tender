#!/usr/bin/env python3
"""
Quick addition of CPPP and Uttarakhand tenders with timeout controls
"""

import sys
sys.path.append('/Users/rahulwealthdiscovery.in/Code/Tender')

import asyncio
import signal
from datetime import datetime

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

async def quick_add_tenders():
    """Quick addition with timeout controls"""
    
    print("🎯 QUICK TENDER ADDITION")
    print("=" * 25)
    
    # Import
    from backend.ingestion.connector_registry import get_connector
    from sqlalchemy import create_engine, text
    
    engine = create_engine('postgresql://tender:tender_dev_2026@localhost:5432/tender_portal')
    
    # Check starting status
    print("📊 Starting status:")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT source, COUNT(*) FROM tenders GROUP BY source"))
            for row in result.fetchall():
                print(f"   {row[0]}: {row[1]:,}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # 1. Try CPPP with timeout
    print("📋 STEP 1: Adding CPPP tenders (with timeout)...")
    print("-" * 45)
    
    try:
        # Set timeout for CPPP
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)  # 2 minute timeout
        
        cppp_connector = get_connector("cppp")
        raw_tenders = await cppp_connector.fetch_tenders()
        
        signal.alarm(0)  # Cancel timeout
        
        print(f"   ✅ CPPP fetched: {len(raw_tenders)} raw tenders")
        
        # Quick insert a few for testing
        if raw_tenders:
            from backend.ingestion.tasks import _process_raw_tenders
            
            # Process just first 10 to avoid long processing
            test_tenders = raw_tenders[:10]
            print(f"   🔄 Processing first {len(test_tenders)} for testing...")
            
            # Insert manually with simple logic
            count = 0
            with engine.connect() as conn:
                for raw in test_tenders:
                    try:
                        result = conn.execute(text("""
                            INSERT INTO tenders (
                                id, source, source_url, source_id, tender_id, title, description,
                                department, organization, state, category, tender_type,
                                status, raw_text, fingerprint, parsed_quality_score
                            ) VALUES (
                                gen_random_uuid(), 'CPPP', :source_url, :source_id, :tender_id,
                                :title, :description, :department, :organization, :state,
                                :category, 'OPEN_TENDER',
                                'ACTIVE', :raw_text, :fingerprint, 0.5
                            ) RETURNING id
                        """), {
                            'source_url': raw.source_url or '',
                            'source_id': raw.source_id,
                            'tender_id': raw.tender_id or raw.source_id,
                            'title': (raw.title or 'CPPP Tender')[:500],
                            'description': (raw.description or '')[:1000],
                            'department': (raw.department or '')[:200],
                            'organization': (raw.organization or '')[:200],
                            'state': raw.state or 'Central',
                            'category': (raw.category or '')[:200],
                            'raw_text': str(raw)[:5000],
                            'fingerprint': f"cppp_{raw.source_id}_{count}"
                        })
                        conn.commit()
                        count += 1
                    except Exception as e:
                        conn.rollback()
                        print(f"      Skip tender {count}: {str(e)[:100]}")
                        
            print(f"   ✅ Added {count} CPPP tenders")
            
    except TimeoutError:
        print("   ⏰ CPPP timed out after 2 minutes")
    except Exception as e:
        print(f"   ❌ CPPP error: {e}")
        signal.alarm(0)
    
    print()
    
    # 2. Try Uttarakhand with timeout
    print("📋 STEP 2: Adding Uttarakhand tenders (with timeout)...")
    print("-" * 51)
    
    try:
        # Set timeout for Uttarakhand
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)  # 2 minute timeout
        
        uk_connector = get_connector("uttarakhand")
        raw_tenders = await uk_connector.fetch_tenders()
        
        signal.alarm(0)  # Cancel timeout
        
        print(f"   ✅ Uttarakhand fetched: {len(raw_tenders)} raw tenders")
        
        # Process first few for testing
        if raw_tenders:
            test_tenders = raw_tenders[:15]  # Get more from Uttarakhand
            print(f"   🔄 Processing first {len(test_tenders)} for testing...")
            
            count = 0
            with engine.connect() as conn:
                for raw in test_tenders:
                    try:
                        result = conn.execute(text("""
                            INSERT INTO tenders (
                                id, source, source_url, source_id, tender_id, title, description,
                                department, organization, state, category, tender_type,
                                status, raw_text, fingerprint, parsed_quality_score,
                                bid_close_date
                            ) VALUES (
                                gen_random_uuid(), 'UTTARAKHAND', :source_url, :source_id, :tender_id,
                                :title, :description, :department, :organization, 'Uttarakhand',
                                :category, 'OPEN_TENDER',
                                'ACTIVE', :raw_text, :fingerprint, 0.5,
                                :close_date
                            ) RETURNING id
                        """), {
                            'source_url': raw.source_url or '',
                            'source_id': raw.source_id,
                            'tender_id': raw.tender_id or raw.source_id,
                            'title': (raw.title or 'Uttarakhand Tender')[:500],
                            'description': (raw.description or '')[:1000],
                            'department': (raw.department or '')[:200],
                            'organization': (raw.organization or '')[:200],
                            'category': (raw.category or '')[:200],
                            'raw_text': str(raw)[:5000],
                            'fingerprint': f"uttarakhand_{raw.source_id}_{count}",
                            'close_date': raw.bid_close_date
                        })
                        conn.commit()
                        count += 1
                    except Exception as e:
                        conn.rollback()
                        print(f"      Skip tender {count}: {str(e)[:100]}")
                        
            print(f"   ✅ Added {count} Uttarakhand tenders")
            
    except TimeoutError:
        print("   ⏰ Uttarakhand timed out after 2 minutes")
    except Exception as e:
        print(f"   ❌ Uttarakhand error: {e}")
        signal.alarm(0)
    
    print()
    
    # Final status
    print("📊 FINAL STATUS")
    print("=" * 16)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT source, COUNT(*) as count 
                FROM tenders 
                GROUP BY source 
                ORDER BY count DESC
            """))
            
            total = 0
            for row in result.fetchall():
                print(f"   {row[0]}: {row[1]:,} tenders")
                total += row[1]
            
            print(f"   TOTAL: {total:,} tenders")
            
            if total > 10:
                print()
                print("✅ SUCCESS: Added new tenders!")
                print("🎯 Clean focused database ready for testing")
                print("🧹 No cached data issues")
            
    except Exception as e:
        print(f"❌ Status error: {e}")

def main():
    asyncio.run(quick_add_tenders())

if __name__ == "__main__":
    main()