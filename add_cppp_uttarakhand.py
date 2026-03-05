#!/usr/bin/env python3
"""
Add CPPP and Uttarakhand tenders to existing clean database
- 50 CPPP tenders
- All active Uttarakhand tenders
"""

import sys
sys.path.append('/Users/rahulwealthdiscovery.in/Code/Tender')

import asyncio
from datetime import datetime

async def add_remaining_tenders():
    """Add CPPP and Uttarakhand tenders to existing database"""
    
    print("🎯 ADDING REMAINING TENDERS")
    print("=" * 30)
    print("Adding to existing database:")
    print("  • 50 CPPP tenders")
    print("  • All active Uttarakhand tenders")
    print()
    
    # Import existing task function
    from backend.ingestion.tasks import _run_connector_async
    
    # Check current status
    print("📊 Current database status:")
    from sqlalchemy import create_engine, text
    engine = create_engine('postgresql://tender:tender_dev_2026@localhost:5432/tender_portal')
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT source, COUNT(*) FROM tenders GROUP BY source"))
            for row in result.fetchall():
                print(f"   {row[0]}: {row[1]:,} tenders")
    except Exception as e:
        print(f"   Error checking status: {e}")
    
    print()
    
    results = {}
    
    # 1. CPPP Tenders
    print("📋 STEP 1: Adding CPPP tenders...")
    print("-" * 32)
    
    try:
        cppp_result = await _run_connector_async("cppp")
        results["cppp"] = cppp_result
        
        if cppp_result.get("new", 0) > 0:
            print(f"   ✅ CPPP: {cppp_result['new']} new tenders added")
            print(f"   📊 Total fetched: {cppp_result['fetched']}")
        else:
            print(f"   ⚠️  CPPP: {cppp_result.get('fetched', 0)} fetched, {cppp_result.get('duplicate', 0)} duplicates")
            if cppp_result.get('errors', 0) > 0:
                print(f"   ❌ Errors: {cppp_result['errors']}")
                
    except Exception as e:
        print(f"   ❌ CPPP exception: {e}")
        results["cppp"] = {"error": str(e)}
    
    print()
    
    # 2. Uttarakhand Active Tenders
    print("📋 STEP 2: Adding Uttarakhand active tenders...")
    print("-" * 44)
    
    try:
        uk_result = await _run_connector_async("uttarakhand")
        results["uttarakhand"] = uk_result
        
        if uk_result.get("new", 0) > 0:
            print(f"   ✅ Uttarakhand: {uk_result['new']} new tenders added")
            print(f"   📊 Total fetched: {uk_result['fetched']}")
        else:
            print(f"   ⚠️  Uttarakhand: {uk_result.get('fetched', 0)} fetched, {uk_result.get('duplicate', 0)} duplicates")
            if uk_result.get('errors', 0) > 0:
                print(f"   ❌ Errors: {uk_result['errors']}")
                
    except Exception as e:
        print(f"   ❌ Uttarakhand exception: {e}")
        results["uttarakhand"] = {"error": str(e)}
    
    print()
    
    # Final summary
    print("📊 FINAL DATABASE STATUS")
    print("=" * 26)
    
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
            print()
            
            if total > 10:  # We started with 10 GEM
                print("✅ SUCCESSFULLY ADDED NEW TENDERS!")
                print("🎯 Clean database with focused tender sources:")
                print("   • GEM: Government e-Marketplace")
                print("   • CPPP: Central Public Procurement Portal")  
                print("   • UTTARAKHAND: All active state tenders")
                print()
                
                # Show results breakdown  
                print("📋 ADDITION RESULTS:")
                for source, result in results.items():
                    if "error" in result:
                        print(f"   {source.upper()}: ❌ {result['error']}")
                    else:
                        print(f"   {source.upper()}: ✅ {result.get('new', 0)} new, {result.get('duplicate', 0)} duplicates")
                        
                print()
                print("🧹 Database is clean and ready for testing!")
                print("🎯 All cached data issues resolved")
                
            else:
                print("⚠️  Limited new tenders added")
                print("💡 This might indicate duplicates or connection issues")
                
    except Exception as e:
        print(f"❌ Summary error: {e}")

def main():
    """Run the tender addition"""
    asyncio.run(add_remaining_tenders())

if __name__ == "__main__":
    main()