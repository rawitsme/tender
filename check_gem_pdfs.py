#!/usr/bin/env python3

print('🔍 EXAMINING THE 5 GEM TENDERS WITH PDF MENTIONS')
print('=' * 55)

import psycopg2
import re

conn = psycopg2.connect('postgresql://tender:tender_dev_2026@localhost:5432/tender_portal')
cur = conn.cursor()

cur.execute("""
    SELECT id, source_id, title, raw_text
    FROM tenders 
    WHERE source = 'GEM' AND raw_text ILIKE '%pdf%'
    ORDER BY LENGTH(raw_text) DESC
""")

results = cur.fetchall()
print(f'Found {len(results)} GEM tenders mentioning PDF\n')

for i, (tender_id, source_id, title, raw_text) in enumerate(results, 1):
    print(f'📋 GEM EXAMPLE {i}:')
    print(f'   Title: {title[:70]}...')
    print(f'   Source ID: {source_id}')
    print(f'   Tender ID: {tender_id}')
    
    # Find the PDF mentions and surrounding context
    lines = raw_text.split('\n')
    pdf_lines = [line.strip() for line in lines if 'pdf' in line.lower() and len(line.strip()) > 5]
    
    if pdf_lines:
        print(f'   📄 Lines mentioning PDF:')
        for j, line in enumerate(pdf_lines[:3], 1):  # First 3 lines
            print(f'      {j}. {line[:120]}...' if len(line) > 120 else f'      {j}. {line}')
    
    # Check if there are any URLs at all in this tender
    url_pattern = r'https?://[^\s<>"\'`\[\]()]+'
    urls = re.findall(url_pattern, raw_text)
    
    if urls:
        print(f'   🌐 URLs found: {len(urls)}')
        for url in urls[:2]:  # First 2 URLs
            print(f'      • {url}')
    else:
        print(f'   ❌ No URLs found')
    
    print()

conn.close()

print('🎯 REALITY CHECK:')
print('=' * 30)
print('• Very few tenders have direct document URLs')
print('• Government portals keep documents behind authentication')  
print('• Need active scraping with login to get actual PDFs')
print('• Session URLs expire quickly')
print('\n📋 SOLUTION APPROACH:')
print('• Use Selenium with proper authentication')
print('• Implement portal-specific login flows')  
print('• Download documents in real-time when user clicks "Get Details"')
print('• Cache downloaded documents for future access')