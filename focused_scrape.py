#!/usr/bin/env python3
"""
Focused Scraping: Clean database with specific tender counts
- 50 GEM tenders
- 50 CPPP tenders  
- All active Uttarakhand tenders
"""

import sys
import os
sys.path.append('/Users/rahulwealthdiscovery.in/Code/Tender')

import asyncio
import time
from datetime import datetime

async def focused_scrape():
    """Run focused scraping for specific tender counts"""
    
    print("🎯 FOCUSED SCRAPING - Clean Database")
    print("=" * 45)
    print("Target:")
    print("  • 50 GEM tenders")
    print("  • 50 CPPP tenders")
    print("  • All active Uttarakhand tenders")
    print()
    
    # Import existing task function
    from backend.ingestion.tasks import _run_connector_async
    
    results = {}
    
    # 1. GEM Tenders (50)
    print("📋 STEP 1: Scraping GEM tenders...")
    print("-" * 35)
    
    try:
        gem_result = await _run_connector_async("gem")
        results["gem"] = gem_result
        
        if gem_result.get("new", 0) > 0:
            print(f"   ✅ GEM: {gem_result['new']} new tenders added")
            print(f"   📊 Total fetched: {gem_result['fetched']}")
        else:
            print(f"   ⚠️  GEM: {gem_result.get('fetched', 0)} fetched, {gem_result.get('duplicate', 0)} duplicates")
            
    except Exception as e:
        print(f"   ❌ GEM exception: {e}")
        results["gem"] = {"error": str(e)}
    
    print()
    
    # 2. CPPP Tenders (50) 
    print("📋 STEP 2: Scraping CPPP tenders...")
    print("-" * 36)
    
    try:
        cppp_result = await _run_connector_async("cppp")
        results["cppp"] = cppp_result
        
        if cppp_result.get("new", 0) > 0:
            print(f"   ✅ CPPP: {cppp_result['new']} new tenders added")
            print(f"   📊 Total fetched: {cppp_result['fetched']}")
        else:
            print(f"   ⚠️  CPPP: {cppp_result.get('fetched', 0)} fetched, {cppp_result.get('duplicate', 0)} duplicates")
            
    except Exception as e:
        print(f"   ❌ CPPP exception: {e}")
        results["cppp"] = {"error": str(e)}
    
    print()
    
    # 3. Uttarakhand Active Tenders (All Active)
    print("📋 STEP 3: Scraping Uttarakhand tenders...")
    print("-" * 40)
    
    try:
        uk_result = await _run_connector_async("uttarakhand")
        results["uttarakhand"] = uk_result
        
        if uk_result.get("new", 0) > 0:
            print(f"   ✅ Uttarakhand: {uk_result['new']} new tenders added")
            print(f"   📊 Total fetched: {uk_result['fetched']}")
        else:
            print(f"   ⚠️  Uttarakhand: {uk_result.get('fetched', 0)} fetched, {uk_result.get('duplicate', 0)} duplicates")
            
    except Exception as e:
        print(f"   ❌ Uttarakhand exception: {e}")
        results["uttarakhand"] = {"error": str(e)}
    
    print()
    
    # Final summary
    print("📊 FINAL SUMMARY")
    print("=" * 18)
    
    try:
        from sqlalchemy import create_engine, text
        
        engine = create_engine('postgresql://tender:tender_dev_2026@localhost:5432/tender_portal')
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT source, COUNT(*) as count 
                FROM tenders 
                GROUP BY source 
                ORDER BY count DESC
            """))
            
            total_new = 0
            for row in result.fetchall():
                print(f"   {row[0].upper()}: {row[1]:,} tenders")
                total_new += row[1]
            
            print(f"   TOTAL: {total_new:,} tenders")
            
            if total_new > 0:
                print()
                print("✅ FOCUSED SCRAPING COMPLETE!")
                print("🎯 Database now contains only requested tenders")
                print("🧹 All old/stale data removed")
                
                # Show results breakdown  
                print()
                print("📋 RESULTS BREAKDOWN:")
                for source, result in results.items():
                    if "error" in result:
                        print(f"   {source.upper()}: ❌ {result['error']}")
                    else:
                        print(f"   {source.upper()}: ✅ {result.get('new', 0)} new, {result.get('duplicate', 0)} duplicates")
                        
            else:
                print()
                print("⚠️  No tenders were added - check scraping issues")
                
    except Exception as e:
        print(f"❌ Summary error: {e}")

def main():
    """Run the focused scraping"""
    asyncio.run(focused_scrape())

if __name__ == "__main__":
    main()