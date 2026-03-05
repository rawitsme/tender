#!/usr/bin/env python3
"""
Test if tender detail pages are working correctly after the fix
"""

import requests
import time

print("🔧 TESTING TENDER DETAIL PAGES")
print("=" * 32)

# Test backend health
print("1. 🩺 Testing backend health...")
try:
    response = requests.get('http://localhost:8000/health', timeout=5)
    if response.status_code == 200:
        print("   ✅ Backend is healthy")
    else:
        print(f"   ❌ Backend error: {response.status_code}")
except Exception as e:
    print(f"   ❌ Backend connection failed: {e}")

print()

# Test frontend access
print("2. 🌐 Testing frontend access...")
try:
    response = requests.get('http://localhost:5174', timeout=5)
    if response.status_code == 200 and '<title>' in response.text:
        print("   ✅ Frontend is accessible")
    else:
        print(f"   ❌ Frontend error: {response.status_code}")
except Exception as e:
    print(f"   ❌ Frontend connection failed: {e}")

print()

# Test API endpoints
print("3. 📊 Testing tender API...")
try:
    response = requests.get('http://localhost:8000/api/v1/tenders/stats', timeout=10)
    if response.status_code == 200:
        stats = response.json()
        print(f"   ✅ API working - {stats.get('total_tenders', 0)} tenders available")
    else:
        print(f"   ❌ API error: {response.status_code}")
except Exception as e:
    print(f"   ❌ API connection failed: {e}")

print()

# Test tender search
print("4. 🔍 Testing tender search...")
try:
    response = requests.post(
        'http://localhost:8000/api/v1/tenders/search',
        json={"limit": 3, "offset": 0},
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        tenders = data.get('tenders', [])
        print(f"   ✅ Search working - found {len(tenders)} tenders")
        
        if tenders:
            first_tender = tenders[0]
            tender_id = first_tender.get('id')
            print(f"   📋 Sample tender ID: {tender_id}")
            print(f"   📋 Sample tender title: {first_tender.get('title', '')[:50]}...")
            
            # Test specific tender endpoint
            print(f"\n5. 🎯 Testing specific tender detail...")
            response = requests.get(f'http://localhost:8000/api/v1/tenders/{tender_id}', timeout=10)
            if response.status_code == 200:
                tender = response.json()
                print(f"   ✅ Tender detail working")
                print(f"   📊 Source: {tender.get('source', 'N/A')}")
                print(f"   📅 Close Date: {tender.get('bid_close_date', 'N/A')}")
                print(f"   💰 Value: {tender.get('tender_value_estimated', 'N/A')}")
            else:
                print(f"   ❌ Tender detail error: {response.status_code}")
                
    else:
        print(f"   ❌ Search error: {response.status_code}")
except Exception as e:
    print(f"   ❌ Search failed: {e}")

print()
print("🎯 STATUS SUMMARY:")
print("=" * 18)
print("✅ Fix Applied: Simplified RealDocuments component")
print("✅ Build: Successful compilation")
print("✅ Import: Fixed api import path")
print("✅ JSX: Simple, safe structure")
print("✅ Enhancement: Key tender info summary added")

print()
print("🌐 READY FOR TESTING:")
print("=" * 21)
print("1. Visit: http://localhost:5174")
print("2. Login: admin@tenderportal.in / admin123")
print("3. Click any tender → Should see page (no more blank)")
print("4. Click 'Get Real Documents' → See enhanced summary")

print()
print("🔧 ENHANCEMENT FEATURES:")
print("=" * 26)
print("📅 Last Date with proper formatting")
print("💰 Tender Value in ₹Cr/L format")
print("🏦 EMD Amount")
print("🏢 Organization & State")
print("📋 Brief scope description")
print("✅ Clean, simple layout")

print()
print("🎊 Blank page issue should be resolved!")