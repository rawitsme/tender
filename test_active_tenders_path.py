#!/usr/bin/env python3
"""
Quick test: Active Tenders path to find real tender downloads
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

# Create test folder
test_dir = Path("storage/documents/active_tenders_test")
test_dir.mkdir(parents=True, exist_ok=True)

print("🚀 TESTING ACTIVE TENDERS PATH")
print("=" * 35)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

base_url = "https://uktenders.gov.in"

try:
    # Access Active Tenders directly
    active_tenders_url = f"{base_url}/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    
    print(f"📋 Accessing: {active_tenders_url}")
    
    response = session.get(active_tenders_url, timeout=15)
    
    if response.status_code == 200:
        print(f"✅ Active Tenders page loaded: {len(response.text):,} chars")
        
        # Save the page
        active_page_file = test_dir / "active_tenders_page.html"
        with open(active_page_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print("\n🔍 ANALYZING ACTIVE TENDERS PAGE:")
        
        # Look for actual tender entries in tables
        tender_count = 0
        real_tender_links = []
        
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            
            if len(rows) > 5:  # Substantial table
                print(f"   📊 Found table with {len(rows)} rows")
                
                for row in rows[1:6]:  # Skip header, check first 5 data rows
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 3:
                        row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                        
                        # Look for actual tender indicators
                        if (len(row_text) > 50 and 
                            any(keyword in row_text.lower() for keyword in 
                                ['tender', 'work', 'supply', 'construction', 'maintenance', 'procurement']) and
                            any(indicator in row_text for indicator in ['2026', '2025', '2024', 'Rs', '₹'])):
                            
                            tender_count += 1
                            print(f"      🎯 Tender {tender_count}: {row_text[:80]}...")
                            
                            # Look for clickable links in this row
                            for cell in cells:
                                for link in cell.find_all('a', href=True):
                                    link_text = link.get_text(strip=True)
                                    href = link.get('href')
                                    
                                    if (len(link_text) > 20 and 
                                        ('view' in link_text.lower() or 'detail' in link_text.lower() or
                                         'tender' in href.lower())):
                                        
                                        full_url = urljoin(active_tenders_url, href)
                                        real_tender_links.append({
                                            'title': link_text,
                                            'url': full_url
                                        })
                                        print(f"         🔗 Link: {link_text[:40]}... -> {href}")
                                        break
                            
                            if tender_count >= 3:  # Found enough examples
                                break
        
        print(f"\n📊 SUMMARY:")
        print(f"   Real tenders found: {tender_count}")
        print(f"   Clickable links: {len(real_tender_links)}")
        
        if real_tender_links:
            print(f"\n🧪 TESTING FIRST TENDER LINK:")
            test_tender = real_tender_links[0]
            print(f"   Title: {test_tender['title']}")
            print(f"   URL: {test_tender['url']}")
            
            # Access the first tender detail page
            try:
                detail_response = session.get(test_tender['url'], timeout=15)
                
                if detail_response.status_code == 200:
                    print(f"   ✅ Tender detail loaded: {len(detail_response.text):,} chars")
                    
                    # Save detail page
                    detail_file = test_dir / "sample_tender_detail.html"
                    with open(detail_file, 'w', encoding='utf-8') as f:
                        f.write(detail_response.text)
                    
                    # Look for download options
                    detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                    
                    download_options = []
                    for element in detail_soup.find_all(['a', 'button', 'input'], href=True):
                        text = element.get_text(strip=True).lower()
                        href = element.get('href', '')
                        
                        if (any(keyword in text for keyword in ['download', 'zip', 'document', 'attachment', 'file']) or
                            any(keyword in href.lower() for keyword in ['download', 'document', 'file'])):
                            
                            download_options.append({
                                'text': element.get_text(strip=True),
                                'href': href
                            })
                    
                    print(f"   📥 Download options found: {len(download_options)}")
                    
                    if download_options:
                        for i, option in enumerate(download_options, 1):
                            print(f"      {i}. {option['text']} -> {option['href']}")
                        
                        # Test first download option
                        first_download = download_options[0]
                        download_url = urljoin(test_tender['url'], first_download['href'])
                        
                        print(f"\\n🎯 TESTING DOWNLOAD: {first_download['text']}")
                        print(f"   URL: {download_url}")
                        
                        try:
                            download_response = session.get(download_url, timeout=15)
                            
                            if download_response.status_code == 200:
                                print(f"   📄 Download page loaded: {len(download_response.text):,} chars")
                                
                                # Save download page
                                download_file = test_dir / "download_page.html"
                                with open(download_file, 'w', encoding='utf-8') as f:
                                    f.write(download_response.text)
                                
                                # Check for CAPTCHA
                                download_soup = BeautifulSoup(download_response.text, 'html.parser')
                                
                                captcha_found = False
                                for img in download_soup.find_all('img'):
                                    src = img.get('src', '')
                                    alt = img.get('alt', '').lower()
                                    
                                    if (any(keyword in src.lower() for keyword in ['captcha', 'verification']) or
                                        any(keyword in alt for keyword in ['captcha', 'verification'])):
                                        
                                        captcha_found = True
                                        print(f"   🤖 CAPTCHA FOUND: {src}")
                                        break
                                
                                if captcha_found:
                                    print(f"   🎉 SUCCESS: Found CAPTCHA-protected download!")
                                    print(f"   ✅ This is the real tender download path Rahul described!")
                                else:
                                    print(f"   ⚠️  No CAPTCHA found - might be direct download or different page")
                                    
                                    # Check if it's a ZIP file
                                    content_type = download_response.headers.get('content-type', '').lower()
                                    if 'zip' in content_type:
                                        print(f"   📦 Direct ZIP download detected!")
                            else:
                                print(f"   ❌ Download page failed: HTTP {download_response.status_code}")
                        
                        except Exception as e:
                            print(f"   ❌ Download test failed: {e}")
                    
                    else:
                        print(f"   ⚠️  No download options found on tender detail page")
                else:
                    print(f"   ❌ Tender detail failed: HTTP {detail_response.status_code}")
            
            except Exception as e:
                print(f"   ❌ Tender detail test failed: {e}")
        
        else:
            print(f"   ⚠️  No real tender links found in Active Tenders")
    
    else:
        print(f"❌ Active Tenders page failed: HTTP {response.status_code}")

except Exception as e:
    print(f"❌ Test failed: {e}")

print(f"\n📁 TEST FILES SAVED:")
for file in test_dir.iterdir():
    print(f"   📄 {file.name} ({file.stat().st_size:,} bytes)")

print(f"\n💡 CONCLUSION:")
print(f"If CAPTCHA was found, the exact navigation is working!")
print(f"If not, we may need to try different tender types or search parameters.")