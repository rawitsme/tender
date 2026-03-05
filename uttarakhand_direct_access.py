#!/usr/bin/env python3
"""
Uttarakhand Direct Access - No Login Required
Downloads documents from Uttarakhand portal using fresh sessions
"""

import requests
import re
import time
from bs4 import BeautifulSoup
from pathlib import Path
import json

class UttarakhandDirectAccess:
    """Access Uttarakhand documents without login - session-based approach"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_direct"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://uktenders.gov.in"
        self.session = requests.Session()
        
        # Set proper headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_fresh_session(self):
        """Get a fresh session from the main portal"""
        print("🔄 Getting fresh session from Uttarakhand portal...")
        
        try:
            # Start from main page to get fresh session
            response = self.session.get(self.base_url, timeout=15)
            
            if response.status_code == 200:
                print(f"   ✅ Main page loaded: {len(response.text):,} chars")
                
                # Look for tender listing or navigation links
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find links that might lead to tender listings
                tender_links = []
                
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    text = link.get_text().strip().lower()
                    
                    # Look for tender-related navigation
                    if any(keyword in text for keyword in ['tender', 'active', 'latest', 'current']):
                        if href.startswith('/') or href.startswith('http'):
                            full_url = href if href.startswith('http') else self.base_url + href
                            tender_links.append((full_url, text))
                
                if tender_links:
                    print(f"   🔗 Found {len(tender_links)} potential tender links:")
                    for url, text in tender_links[:3]:
                        print(f"      • {text}: {url}")
                    
                    return tender_links[0][0]  # Return the first promising link
                else:
                    print("   ⚠️  No tender navigation links found on main page")
                    
                    # Try common tender listing paths
                    common_paths = [
                        '/nicgep/app?component=$DirectLink&page=FrontEndLatestActiveTenders',
                        '/nicgep/app?page=FrontEndLatestActiveTenders', 
                        '/tenders',
                        '/active-tenders',
                        '/current-tenders'
                    ]
                    
                    for path in common_paths:
                        test_url = self.base_url + path
                        print(f"   🧪 Trying: {path}")
                        
                        test_resp = self.session.get(test_url, timeout=10)
                        if test_resp.status_code == 200 and 'session has timed out' not in test_resp.text.lower():
                            print(f"      ✅ Working path found!")
                            return test_url
                        else:
                            print(f"      ❌ HTTP {test_resp.status_code}")
            else:
                print(f"   ❌ Main page failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Session creation failed: {e}")
        
        return None
    
    def find_tender_documents(self, tender_listing_url, source_id=None):
        """Find documents for a specific tender"""
        print(f"🔍 Searching for tender documents...")
        print(f"   Listing URL: {tender_listing_url}")
        print(f"   Source ID: {source_id}")
        
        try:
            # Access the tender listing page
            response = self.session.get(tender_listing_url, timeout=15)
            
            if response.status_code == 200:
                print(f"   ✅ Tender listing loaded: {len(response.text):,} chars")
                
                # Save the page for analysis
                listing_file = self.downloads_dir / "tender_listing.html"
                with open(listing_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"   💾 Saved listing to: {listing_file}")
                
                # Parse the page to look for tender links
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for tender detail links
                tender_detail_links = []
                
                # Common patterns for tender detail links
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    text = link.get_text().strip()
                    
                    # Look for links that seem to lead to tender details
                    if (('tender' in href.lower() or 'detail' in href.lower() or 
                         'view' in href.lower()) and len(text) > 10):
                        
                        full_url = href if href.startswith('http') else self.base_url + href
                        tender_detail_links.append((full_url, text[:60] + '...'))
                
                print(f"   🔗 Found {len(tender_detail_links)} tender detail links")
                
                if tender_detail_links:
                    # Try the first few tender detail pages
                    for i, (detail_url, title) in enumerate(tender_detail_links[:3], 1):
                        print(f"\\n   📋 Testing tender {i}: {title}")
                        documents = self.extract_documents_from_tender_page(detail_url, f"tender_{i}")
                        
                        if documents:
                            print(f"      ✅ Found {len(documents)} documents!")
                            return documents
                        else:
                            print(f"      ❌ No documents found")
                
                print("   ⚠️  No documents found in any tender pages")
                
            else:
                print(f"   ❌ Listing page failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Document search failed: {e}")
        
        return []
    
    def extract_documents_from_tender_page(self, tender_url, tender_name):
        """Extract document links from a specific tender page"""
        print(f"      🌐 Accessing: {tender_url}")
        
        try:
            response = self.session.get(tender_url, timeout=15)
            
            if response.status_code == 200 and 'session has timed out' not in response.text.lower():
                print(f"         📄 Page loaded: {len(response.text):,} chars")
                
                # Save the tender page
                page_file = self.downloads_dir / f"{tender_name}_page.html"
                with open(page_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Look for document download links
                soup = BeautifulSoup(response.text, 'html.parser')
                
                documents = []
                
                # Find all links that might be documents
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    text = link.get_text().strip().lower()
                    
                    # Look for document-like links
                    if (('.pdf' in href.lower() or '.doc' in href.lower() or 
                         'download' in href.lower() or 'attachment' in href.lower()) or
                        ('download' in text or 'attachment' in text or 'document' in text or
                         'nit' in text or 'boq' in text)):
                        
                        full_url = href if href.startswith('http') else self.base_url + href
                        
                        documents.append({
                            'url': full_url,
                            'text': link.get_text().strip(),
                            'filename': self.generate_filename(href, text)
                        })
                
                if documents:
                    print(f"         🔥 Found {len(documents)} potential documents:")
                    for doc in documents:
                        print(f"            📄 {doc['text'][:40]}: {doc['filename']}")
                
                return documents
                
            else:
                print(f"         ❌ Failed or session timeout: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"         ❌ Page extraction failed: {e}")
        
        return []
    
    def generate_filename(self, url, text):
        """Generate a meaningful filename for downloads"""
        # Try to extract filename from URL
        if '.pdf' in url.lower():
            parts = url.split('/')
            for part in reversed(parts):
                if '.pdf' in part.lower():
                    return part
        
        # Generate from text
        if text:
            clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
            clean_text = '_'.join(clean_text.split()[:5])
            return f"{clean_text}.pdf"
        
        # Default filename
        return f"uttarakhand_document_{int(time.time())}.pdf"
    
    def download_document(self, doc_info, tender_name):
        """Download a specific document"""
        print(f"         ⬇️  Downloading: {doc_info['filename']}")
        
        try:
            response = self.session.get(doc_info['url'], timeout=30)
            
            if response.status_code == 200:
                content = response.content
                
                # Verify it's actually a document (not HTML error)
                if len(content) > 1000 and (content.startswith(b'%PDF') or 
                                          content.startswith(b'PK') or  # DOC/DOCX
                                          b'<html' not in content[:500].lower()):
                    
                    file_path = self.downloads_dir / f"{tender_name}_{doc_info['filename']}"
                    
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    print(f"            ✅ Downloaded: {file_path.name} ({len(content):,} bytes)")
                    return str(file_path)
                else:
                    print(f"            ❌ Invalid document (HTML response or too small)")
            else:
                print(f"            ❌ Download failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"            ❌ Download error: {e}")
        
        return None
    
    def test_direct_access(self):
        """Test direct access to Uttarakhand documents"""
        print("🚀 TESTING UTTARAKHAND DIRECT ACCESS")
        print("=" * 45)
        
        # Step 1: Get fresh session
        listing_url = self.get_fresh_session()
        
        if listing_url:
            print(f"\\n✅ Fresh session obtained")
            
            # Step 2: Find tender documents
            documents = self.find_tender_documents(listing_url)
            
            if documents:
                print(f"\\n🎉 SUCCESS: Found {len(documents)} documents!")
                
                # Step 3: Try to download them
                downloaded_files = []
                for i, doc in enumerate(documents[:3], 1):  # Try first 3
                    file_path = self.download_document(doc, f"test_tender_{i}")
                    if file_path:
                        downloaded_files.append(file_path)
                
                print(f"\\n📊 RESULTS:")
                print(f"   Documents found: {len(documents)}")
                print(f"   Successfully downloaded: {len(downloaded_files)}")
                
                if downloaded_files:
                    print(f"   Files saved in: {self.downloads_dir}")
                    return True
            else:
                print(f"\\n⚠️  No documents found - may need different approach")
        else:
            print(f"\\n❌ Could not establish session with portal")
        
        return False

def main():
    """Test Uttarakhand direct access"""
    downloader = UttarakhandDirectAccess()
    success = downloader.test_direct_access()
    
    if success:
        print(f"\\n🎉 UTTARAKHAND DIRECT ACCESS: SUCCESS!")
        print(f"Documents downloaded without login required")
    else:
        print(f"\\n🔧 NEEDS REFINEMENT: Portal structure analysis required")

if __name__ == "__main__":
    main()