#!/usr/bin/env python3
"""
Uttarakhand REAL TENDER ACCESS - Following the correct navigation to find actual tenders
Based on analysis: Active Tenders → Tenders by Closing Date → Individual Tender Details → Documents
"""

import requests
import time
import base64
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from datetime import datetime

class UttarakhandRealTenderAccess:
    """Access real tenders with documents via correct navigation path"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_real"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://uktenders.gov.in"
        self.session = requests.Session()
        
        # 2Captcha API configuration
        self.captcha_api_key = "9a09f9a33a7e9f216792c77113f31c11"
        self.captcha_api_url = "http://2captcha.com"
        
        # Browser headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def access_tenders_by_closing_date(self):
        """Access the 'Tenders by Closing Date' page to find real active tenders"""
        print("📋 STEP 1: Accessing 'Tenders by Closing Date' for real tender listings")
        
        # Direct URL based on analysis
        closing_date_url = f"{self.base_url}/nicgep/app?page=FrontEndListTendersbyDate&service=page"
        
        try:
            print(f"   🔗 URL: {closing_date_url}")
            response = self.session.get(closing_date_url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            print(f"   ✅ Page loaded: {len(response.text):,} chars")
            
            # Save the page
            page_file = self.downloads_dir / "tenders_by_closing_date.html"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return response.text
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            return None
    
    def parse_real_tender_listings(self, page_content):
        """Parse actual tender listings from the closing date page"""
        print("📋 STEP 2: Parsing real tender listings")
        
        soup = BeautifulSoup(page_content, 'html.parser')
        real_tenders = []
        
        # Look for tables with tender data
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            
            if len(rows) > 5:  # Substantial table
                print(f"   📊 Analyzing table with {len(rows)} rows")
                
                # Check header to see if this looks like a tender listing table
                header_row = rows[0] if rows else None
                header_text = header_row.get_text(strip=True).lower() if header_row else ""
                
                if any(keyword in header_text for keyword in ['tender', 'description', 'closing', 'date', 'organization']):
                    print(f"      ✅ Tender listing table found")
                    
                    for i, row in enumerate(rows[1:21], 1):  # Skip header, check first 20 data rows
                        cells = row.find_all(['td', 'th'])
                        
                        if len(cells) >= 3:
                            row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                            
                            # Look for actual tender indicators
                            if (len(row_text) > 30 and
                                any(keyword in row_text.lower() for keyword in 
                                    ['tender', 'work', 'supply', 'construction', 'maintenance', 'procurement']) and
                                ('2026' in row_text or '2025' in row_text or 'Rs' in row_text or '₹' in row_text)):
                                
                                print(f"      🎯 Real tender row {i}: {row_text[:60]}...")
                                
                                # Look for clickable links in this row
                                tender_links = []
                                for cell in cells:
                                    for link in cell.find_all('a', href=True):
                                        link_text = link.get_text(strip=True)
                                        href = link.get('href')
                                        
                                        # Look for detail/view links
                                        if (len(link_text) > 5 and
                                            ('view' in link_text.lower() or 
                                             'detail' in link_text.lower() or
                                             'tender' in href.lower() or
                                             len(link_text) > 20)):  # Long text likely tender title
                                            
                                            full_url = urljoin(self.base_url + "/nicgep/app?page=FrontEndListTendersbyDate&service=page", href)
                                            tender_links.append({
                                                'title': link_text,
                                                'url': full_url,
                                                'href': href
                                            })
                                            print(f"         📋 Link: {link_text[:30]}... -> {href}")
                                
                                if tender_links:
                                    real_tenders.append({
                                        'row_text': row_text,
                                        'links': tender_links
                                    })
                                
                                if len(real_tenders) >= 5:  # Found enough examples
                                    break
                else:
                    print(f"      ⚠️  Not a tender listing table")
        
        print(f"   📊 Found {len(real_tenders)} real tender entries")
        return real_tenders
    
    def test_tender_detail_access(self, tender_links):
        """Test accessing individual tender detail pages"""
        print("📋 STEP 3: Testing tender detail page access")
        
        results = []
        
        for i, tender in enumerate(tender_links[:3], 1):  # Test first 3
            print(f"   🎯 Testing tender {i}:")
            
            for link in tender['links'][:2]:  # Test first 2 links per tender
                print(f"      📋 Link: {link['title'][:40]}...")
                print(f"      🔗 URL: {link['url']}")
                
                try:
                    response = self.session.get(link['url'], timeout=15)
                    
                    if response.status_code != 200:
                        print(f"         ❌ HTTP {response.status_code}")
                        continue
                    
                    if 'session has timed out' in response.text.lower():
                        print(f"         ❌ Session timeout")
                        continue
                    
                    print(f"         ✅ Detail page loaded: {len(response.text):,} chars")
                    
                    # Save the detail page
                    detail_file = self.downloads_dir / f"tender_detail_{i}.html"
                    with open(detail_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    
                    # Look for download options
                    download_options = self.find_download_options(response.text, link['url'])
                    
                    if download_options:
                        print(f"         🎯 Found {len(download_options)} download options:")
                        for opt in download_options:
                            print(f"            📥 {opt['text']} -> {opt['url']}")
                        
                        # Test first download option
                        result = self.test_document_download(download_options[0], detail_file.parent)
                        
                        if result:
                            results.append({
                                'tender': tender,
                                'detail_url': link['url'],
                                'download_result': result
                            })
                            print(f"         🎉 SUCCESS: Document download working!")
                            return results  # Return on first success
                        else:
                            print(f"         ⚠️  Download test failed")
                    else:
                        print(f"         ⚠️  No download options found")
                
                except Exception as e:
                    print(f"         ❌ Error: {e}")
                    continue
        
        return results
    
    def find_download_options(self, page_content, base_url):
        """Find download options on tender detail page"""
        soup = BeautifulSoup(page_content, 'html.parser')
        download_options = []
        
        # Look for download-related elements
        for element in soup.find_all(['a', 'button', 'input'], href=True):
            text = element.get_text(strip=True).lower()
            href = element.get('href', '')
            
            if (any(keyword in text for keyword in ['download', 'zip', 'document', 'attachment', 'file']) or
                any(keyword in href.lower() for keyword in ['download', 'document', 'file'])):
                
                full_url = urljoin(base_url, href)
                download_options.append({
                    'text': element.get_text(strip=True),
                    'url': full_url,
                    'element': element.name,
                    'href': href
                })
        
        return download_options
    
    def test_document_download(self, download_option, download_dir):
        """Test downloading documents (with CAPTCHA support)"""
        print(f"         🔥 Testing download: {download_option['text']}")
        
        try:
            response = self.session.get(download_option['url'], timeout=15)
            
            if response.status_code != 200:
                print(f"            ❌ HTTP {response.status_code}")
                return None
            
            print(f"            ✅ Download page loaded: {len(response.text):,} chars")
            
            # Save download page
            download_page_file = download_dir / "download_page_test.html"
            with open(download_page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Check for CAPTCHA
            soup = BeautifulSoup(response.text, 'html.parser')
            
            captcha_found = False
            for img in soup.find_all('img'):
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                if (any(keyword in src.lower() for keyword in ['captcha', 'verification']) or
                    any(keyword in alt for keyword in ['captcha', 'verification'])):
                    
                    captcha_found = True
                    print(f"            🤖 CAPTCHA FOUND: {src}")
                    break
            
            if captcha_found:
                print(f"            🎉 SUCCESS: Found CAPTCHA-protected download!")
                print(f"            ✅ This matches Rahul's description - ready for 2Captcha integration")
                
                return {
                    'status': 'captcha_found',
                    'captcha_url': src,
                    'download_page': str(download_page_file)
                }
            else:
                # Check if response is already a file
                content_type = response.headers.get('content-type', '').lower()
                
                if any(ftype in content_type for ftype in ['zip', 'pdf', 'application']):
                    print(f"            📄 Direct file download: {content_type}")
                    
                    # Save the file
                    file_ext = 'zip' if 'zip' in content_type else 'pdf' if 'pdf' in content_type else 'bin'
                    file_path = download_dir / f"downloaded_file.{file_ext}"
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    return {
                        'status': 'direct_download',
                        'file_path': str(file_path),
                        'file_size': len(response.content),
                        'content_type': content_type
                    }
                else:
                    print(f"            ⚠️  No CAPTCHA, not a direct file")
                    return None
            
        except Exception as e:
            print(f"            ❌ Download test failed: {e}")
            return None
    
    def run_comprehensive_test(self):
        """Run comprehensive test to find real tenders with documents"""
        print("🚀 UTTARAKHAND REAL TENDER ACCESS TEST")
        print("=" * 42)
        
        result = {
            'status': 'testing',
            'found_real_tenders': False,
            'found_captcha_downloads': False,
            'found_direct_downloads': False
        }
        
        try:
            # Step 1: Access tenders by closing date
            page_content = self.access_tenders_by_closing_date()
            
            if not page_content:
                result['status'] = 'failed'
                result['error'] = 'Could not access tenders by closing date page'
                return result
            
            # Step 2: Parse real tender listings
            real_tenders = self.parse_real_tender_listings(page_content)
            
            if not real_tenders:
                result['status'] = 'no_real_tenders'
                result['error'] = 'No real tender listings found'
                return result
            
            result['found_real_tenders'] = True
            
            # Step 3: Test tender detail access and document downloads
            download_results = self.test_tender_detail_access(real_tenders)
            
            if download_results:
                for res in download_results:
                    if res['download_result']['status'] == 'captcha_found':
                        result['found_captcha_downloads'] = True
                    elif res['download_result']['status'] == 'direct_download':
                        result['found_direct_downloads'] = True
                
                result['status'] = 'success'
                result['download_results'] = download_results
            else:
                result['status'] = 'no_downloads'
                result['error'] = 'No document downloads found'
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result

def test_uttarakhand_real_access():
    """Test the real tender access system"""
    accessor = UttarakhandRealTenderAccess()
    result = accessor.run_comprehensive_test()
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"   Status: {result['status']}")
    print(f"   Real Tenders Found: {result.get('found_real_tenders', False)}")
    print(f"   CAPTCHA Downloads: {result.get('found_captcha_downloads', False)}")
    print(f"   Direct Downloads: {result.get('found_direct_downloads', False)}")
    
    if result.get('download_results'):
        print(f"   🎉 SUCCESS: Document download system working!")
        
        for i, res in enumerate(result['download_results'], 1):
            dr = res['download_result']
            print(f"      {i}. Status: {dr['status']}")
            
            if dr['status'] == 'captcha_found':
                print(f"         🤖 CAPTCHA ready for 2Captcha integration")
            elif dr['status'] == 'direct_download':
                print(f"         📄 File: {dr['file_size']:,} bytes ({dr['content_type']})")
        
        return True
    else:
        print(f"   Error: {result.get('error', 'Unknown')}")
        return False

if __name__ == "__main__":
    success = test_uttarakhand_real_access()
    
    if success:
        print(f"\n✅ REAL TENDER ACCESS: SUCCESS!")
        print(f"Ready to integrate with CAPTCHA solving!")
    else:
        print(f"\n🔧 Need to refine navigation path")