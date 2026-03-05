#!/usr/bin/env python3
"""
Uttarakhand Targeted Access - Navigate to actual tender listings
Since Rahul confirmed no login required, let's find the right navigation path
"""

import requests
import re
import time
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, parse_qs, urlparse

class UttarakhandTargetedAccess:
    """Navigate Uttarakhand portal to find actual tender documents"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_targeted"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://uktenders.gov.in"
        self.session = requests.Session()
        
        # Set proper headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })
    
    def explore_portal_navigation(self):
        """Systematically explore the portal to find tender listings"""
        print("🗺️  EXPLORING UTTARAKHAND PORTAL NAVIGATION")
        print("=" * 50)
        
        try:
            # Start from main page
            response = self.session.get(self.base_url, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ Main page failed: HTTP {response.status_code}")
                return None
            
            print(f"✅ Main portal loaded: {len(response.text):,} characters")
            
            # Save main page for analysis
            main_page_file = self.downloads_dir / "main_page.html"
            with open(main_page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for navigation links systematically
            navigation_links = []
            
            # Find all links and classify them
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text().strip()
                
                # Skip empty or irrelevant links
                if not text or len(text) < 3:
                    continue
                
                # Look for tender-related navigation
                keywords = ['tender', 'active', 'current', 'latest', 'bid', 'notice', 'rfp', 'quotation']
                if any(keyword in text.lower() for keyword in keywords):
                    full_url = urljoin(self.base_url, href)
                    navigation_links.append((full_url, text, 'tender_related'))
                
                # Look for general navigation that might lead to tenders
                nav_keywords = ['search', 'view', 'browse', 'list', 'department', 'category']
                if any(keyword in text.lower() for keyword in nav_keywords):
                    full_url = urljoin(self.base_url, href)
                    navigation_links.append((full_url, text, 'navigation'))
            
            print(f"🔗 Found {len(navigation_links)} navigation links")
            
            # Categorize and prioritize links
            tender_links = [link for link in navigation_links if link[2] == 'tender_related']
            nav_links = [link for link in navigation_links if link[2] == 'navigation']
            
            print(f"   📋 Tender-related: {len(tender_links)}")
            print(f"   🧭 Navigation: {len(nav_links)}")
            
            # Try tender-related links first
            for i, (url, text, category) in enumerate(tender_links[:5], 1):
                print(f"\\n🎯 Testing tender link {i}: {text[:50]}")
                print(f"   URL: {url}")
                
                result = self.test_tender_access(url, f"tender_nav_{i}")
                if result and result.get('has_tenders'):
                    print(f"   ✅ SUCCESS: Found actual tender listings!")
                    return result
                else:
                    print(f"   ❌ No tender content found")
            
            # If no tender links worked, try navigation links
            for i, (url, text, category) in enumerate(nav_links[:3], 1):
                print(f"\\n🧭 Testing navigation link {i}: {text[:50]}")
                print(f"   URL: {url}")
                
                result = self.test_tender_access(url, f"nav_{i}")
                if result and result.get('has_tenders'):
                    print(f"   ✅ SUCCESS: Found tender content through navigation!")
                    return result
            
            # Try direct URL patterns common in NIC portals
            print(f"\\n🎯 Trying common NIC tender listing patterns...")
            
            direct_patterns = [
                "/nicgep/app?page=ActiveTenders&service=page",
                "/nicgep/app?page=FrontEndActiveTenders&service=page", 
                "/nicgep/app?page=TenderSearch&service=page",
                "/nicgep/app?page=BrowseTenders&service=page",
                "/nicgep/app?component=DirectLink&page=ActiveTenders",
                "/active-tenders",
                "/current-tenders"
            ]
            
            for i, pattern in enumerate(direct_patterns, 1):
                url = self.base_url + pattern
                print(f"\\n🧪 Testing pattern {i}: {pattern}")
                
                result = self.test_tender_access(url, f"pattern_{i}")
                if result and result.get('has_tenders'):
                    print(f"   🎉 SUCCESS: Found tenders with pattern {i}!")
                    return result
            
            print(f"\\n⚠️  No tender listings found through standard navigation")
            return None
            
        except Exception as e:
            print(f"❌ Portal exploration failed: {e}")
            return None
    
    def test_tender_access(self, url, test_name):
        """Test if a URL leads to actual tender listings"""
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return {'status': 'failed', 'code': response.status_code}
            
            content = response.text
            
            # Check for session timeout
            if 'session has timed out' in content.lower():
                return {'status': 'session_timeout'}
            
            # Save the page
            page_file = self.downloads_dir / f"{test_name}_page.html"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Analyze content for tender indicators
            analysis = self.analyze_tender_content(content)
            
            print(f"      📊 Analysis: {analysis['tender_score']} tender indicators")
            
            if analysis['tender_score'] >= 3:  # Threshold for "looks like tender content"
                return {
                    'status': 'success',
                    'has_tenders': True,
                    'url': url,
                    'analysis': analysis,
                    'page_file': str(page_file)
                }
            else:
                return {
                    'status': 'no_tenders',
                    'has_tenders': False,
                    'analysis': analysis
                }
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def analyze_tender_content(self, content):
        """Analyze page content to detect if it contains actual tenders"""
        
        # Tender indicators with different weights
        indicators = {
            'tender no': 3,
            'tender id': 3,
            'tender title': 3,
            'bid submission': 2,
            'last date': 2,
            'opening date': 2,
            'tender value': 2,
            'department': 1,
            'organization': 1,
            'download': 1,
            'view details': 2,
            'bid document': 2,
            'technical bid': 2,
            'financial bid': 2,
            'emd': 1,
            'earnest money': 1,
            'pre-qualification': 1,
            'corrigendum': 1,
            'amendment': 1
        }
        
        content_lower = content.lower()
        score = 0
        found_indicators = []
        
        for indicator, weight in indicators.items():
            count = content_lower.count(indicator)
            if count > 0:
                score += weight * min(count, 3)  # Cap contribution per indicator
                found_indicators.append((indicator, count))
        
        # Look for tender number patterns
        tender_patterns = [
            r'tender.*?no.*?[:\s]*([a-zA-Z0-9\-/]+)',
            r'tender.*?id.*?[:\s]*([a-zA-Z0-9\-/]+)',
            r'reference.*?no.*?[:\s]*([a-zA-Z0-9\-/]+)'
        ]
        
        tender_numbers = []
        for pattern in tender_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tender_numbers.extend(matches[:5])  # Limit to avoid spam
        
        # Boost score if we found actual tender numbers
        if tender_numbers:
            score += len(tender_numbers) * 2
        
        return {
            'tender_score': score,
            'found_indicators': found_indicators,
            'tender_numbers': tender_numbers,
            'content_size': len(content),
            'has_forms': '<form' in content_lower,
            'has_tables': '<table' in content_lower
        }
    
    def extract_tender_details(self, successful_result):
        """Extract actual tender details from a successful page"""
        print(f"\\n📋 EXTRACTING TENDER DETAILS")
        print("=" * 30)
        
        try:
            page_file = successful_result['page_file']
            with open(page_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for tender listing tables or structured data
            tenders = []
            
            # Check for table-based tender listings
            tables = soup.find_all('table')
            print(f"🔍 Found {len(tables)} tables to analyze")
            
            for i, table in enumerate(tables, 1):
                rows = table.find_all('tr')
                print(f"   Table {i}: {len(rows)} rows")
                
                # Look for rows that might contain tender info
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:  # Minimum for meaningful tender data
                        
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        row_text = ' '.join(cell_texts).lower()
                        
                        # Check if this row looks like tender data
                        if (any(word in row_text for word in ['tender', 'bid', 'quotation', 'rfp']) and
                            any(word in row_text for word in ['date', 'value', 'department', 'organization'])):
                            
                            # Look for document links in this row
                            doc_links = []
                            for cell in cells:
                                for link in cell.find_all('a', href=True):
                                    href = link.get('href')
                                    link_text = link.get_text(strip=True)
                                    
                                    if ('view' in link_text.lower() or 'download' in link_text.lower() or
                                        'detail' in link_text.lower()):
                                        full_url = urljoin(successful_result['url'], href)
                                        doc_links.append((full_url, link_text))
                            
                            if doc_links:
                                tender_info = {
                                    'row_index': row_idx,
                                    'table_index': i,
                                    'cells': cell_texts,
                                    'document_links': doc_links
                                }
                                tenders.append(tender_info)
                                print(f"      ✅ Tender found in table {i}, row {row_idx}")
                                print(f"         Links: {len(doc_links)}")
            
            if tenders:
                print(f"\\n🎉 FOUND {len(tenders)} TENDERS WITH DOCUMENT LINKS!")
                
                # Try to download from first tender
                test_tender = tenders[0]
                print(f"\\n🧪 Testing document download from first tender:")
                
                for link_url, link_text in test_tender['document_links'][:2]:
                    print(f"   📄 Trying: {link_text} -> {link_url}")
                    
                    result = self.attempt_document_download(link_url, link_text)
                    if result:
                        print(f"      ✅ SUCCESS: Downloaded {result}")
                        return True
                    else:
                        print(f"      ❌ Download failed")
                
                return {'tenders': tenders, 'status': 'found_tenders'}
            else:
                print(f"   ❌ No structured tender data found")
                return None
                
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return None
    
    def attempt_document_download(self, doc_url, doc_name):
        """Try to download a document from URL"""
        try:
            response = self.session.get(doc_url, timeout=30)
            
            if response.status_code == 200:
                content = response.content
                
                # Check if it's a real document
                if (len(content) > 1000 and 
                    (content.startswith(b'%PDF') or  # PDF
                     content.startswith(b'PK') or   # Office docs
                     b'<html' not in content[:500].lower())):  # Not HTML
                    
                    # Generate filename
                    filename = re.sub(r'[^a-zA-Z0-9\s]', '', doc_name)
                    filename = '_'.join(filename.split()[:5]) + '.pdf'
                    
                    file_path = self.downloads_dir / filename
                    
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    return str(file_path)
            
            return None
            
        except Exception as e:
            print(f"      Download error: {e}")
            return None
    
    def run_targeted_test(self):
        """Run the complete targeted access test"""
        print("🚀 UTTARAKHAND TARGETED ACCESS TEST")
        print("=" * 40)
        
        # Step 1: Find tender listings
        result = self.explore_portal_navigation()
        
        if result and result.get('has_tenders'):
            print(f"\\n🎯 Found tender content at: {result['url']}")
            
            # Step 2: Extract tender details
            extraction_result = self.extract_tender_details(result)
            
            if extraction_result:
                print(f"\\n🎉 UTTARAKHAND ACCESS: SUCCESS!")
                print(f"Portal structure identified and document access confirmed")
                return True
            else:
                print(f"\\n🔧 Need to refine document extraction logic")
        else:
            print(f"\\n❌ Could not locate tender listings")
            print(f"Portal might require different navigation approach")
        
        return False

def main():
    """Test targeted Uttarakhand access"""
    downloader = UttarakhandTargetedAccess()
    success = downloader.run_targeted_test()
    
    if success:
        print(f"\\n✅ Ready to implement in production system!")
    else:
        print(f"\\n🔧 Needs further portal analysis")

if __name__ == "__main__":
    main()