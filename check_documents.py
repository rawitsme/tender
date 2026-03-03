#!/usr/bin/env python3

print('🔍 ANALYZING ACTUAL DOCUMENT URLs IN DATABASE')
print('=' * 55)

import psycopg2
import re

conn = psycopg2.connect('postgresql://tender:tender_dev_2026@localhost:5432/tender_portal')
cur = conn.cursor()

# Check for any document URLs or references in raw_text
cur.execute("""
    SELECT source, COUNT(*) as total_tenders,
           COUNT(CASE WHEN raw_text ILIKE '%pdf%' THEN 1 END) as mentions_pdf,
           COUNT(CASE WHEN raw_text ILIKE '%download%' THEN 1 END) as mentions_download,
           COUNT(CASE WHEN raw_text ILIKE '%document%' THEN 1 END) as mentions_document,
           COUNT(CASE WHEN raw_text ILIKE '%http%' THEN 1 END) as mentions_http
    FROM tenders 
    GROUP BY source
    ORDER BY total_tenders DESC
""")

print('📊 DOCUMENT REFERENCES BY SOURCE:')
print('Source      | Total | PDF | Download | Document | HTTP')
print('-' * 60)
for source, total, pdf_count, download_count, doc_count, http_count in cur.fetchall():
    print(f'{source:<10} | {total:>5} | {pdf_count:>3} | {download_count:>8} | {doc_count:>8} | {http_count:>4}')

print()

# Look for specific examples with potential document URLs
cur.execute("""
    SELECT id, source, source_id, title, raw_text
    FROM tenders 
    WHERE raw_text ILIKE '%http%' 
    AND LENGTH(raw_text) > 500
    ORDER BY LENGTH(raw_text) DESC
    LIMIT 3
""")

print('🔍 EXAMPLES WITH HTTP URLs:')
print('=' * 40)

results = cur.fetchall()
for i, (tender_id, source, source_id, title, raw_text) in enumerate(results, 1):
    print(f'\n📋 EXAMPLE {i} - {source.upper()} Portal:')
    print(f'   Title: {title[:60]}...')
    print(f'   Source ID: {source_id}')
    print(f'   Tender ID: {tender_id}')
    
    # Extract all HTTP URLs
    http_pattern = r'https?://[^\s<>"\'`\[\](){}]+'
    urls = re.findall(http_pattern, raw_text, re.IGNORECASE)
    
    if urls:
        print(f'   🌐 FOUND {len(urls)} HTTP URLs:')
        for j, url in enumerate(urls[:5], 1):  # Show first 5
            # Check if it looks like a document
            is_doc = any(ext in url.lower() for ext in ['.pdf', '.doc', '.xls', 'download', 'attachment'])
            doc_indicator = ' 📄 [DOCUMENT]' if is_doc else ''
            print(f'      {j}. {url}{doc_indicator}')
            
        if len(urls) > 5:
            print(f'      ... and {len(urls) - 5} more URLs')
    else:
        print('   ❌ No HTTP URLs found')
        # Show sample content
        sample = raw_text[:300].replace('\n', ' ')
        print(f'   📝 Sample: {sample}...')

print()

# Check for PDF-specific mentions
cur.execute("""
    SELECT source, source_id, title, raw_text
    FROM tenders 
    WHERE raw_text ILIKE '%.pdf%' 
    ORDER BY LENGTH(raw_text) DESC
    LIMIT 2
""")

print('📄 EXAMPLES MENTIONING PDF FILES:')
print('=' * 40)

pdf_results = cur.fetchall()
for source, source_id, title, raw_text in pdf_results:
    print(f'\n📋 {source.upper()} - {title[:50]}...')
    
    # Find PDF mentions
    pdf_pattern = r'[^\s<>"\'`]*\.pdf[^\s<>"\'`]*'
    pdf_matches = re.findall(pdf_pattern, raw_text, re.IGNORECASE)
    
    if pdf_matches:
        print(f'   📄 PDF references found:')
        for pdf in pdf_matches[:3]:
            print(f'      • {pdf}')
    
conn.close()

print('\n🎯 ANALYSIS COMPLETE')
print('=' * 30)
print('Now checking if any URLs are accessible...')