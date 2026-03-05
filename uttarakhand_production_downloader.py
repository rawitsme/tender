#!/usr/bin/env python3
"""
Uttarakhand Production Document Downloader
Production-ready implementation for downloading actual tender documents
"""

import requests
import re
import time
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import json
from datetime import datetime

class UttarakhandProductionDownloader:
    """Production downloader for Uttarakhand tender documents"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_production"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://uktenders.gov.in"
        self.session = requests.Session()
        
        # Professional headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def download_documents_for_tender(self, tender_id, source_id):
        """Download documents for a specific Uttarakhand tender"""
        print(f"🏔️  UTTARAKHAND DOCUMENT DOWNLOAD")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        result = {
            'tender_id': tender_id,
            'source_id': source_id,
            'source': 'UTTARAKHAND',
            'downloaded_files': [],
            'total_size': 0,
            'status': 'processing'
        }
        
        try:
            # Create tender-specific folder
            tender_folder = self.downloads_dir / f"UK_{source_id}_{tender_id[:8]}"
            tender_folder.mkdir(exist_ok=True)
            
            # Step 1: Access latest active tenders
            tenders_url = f"{self.base_url}/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
            
            print(f"   🔗 Accessing active tenders: {tenders_url}")
            
            response = self.session.get(tenders_url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Failed to access tenders page: HTTP {response.status_code}")
            
            print(f"   ✅ Active tenders loaded: {len(response.text):,} chars")
            
            # Save the tender listing page
            listing_file = tender_folder / "active_tenders_page.html"
            with open(listing_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Step 2: Parse tender listings to find our specific tender
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for tender entries in tables
            tender_found = False
            target_tender_links = []
            
            # Search through all tables for our tender
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        
                        row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                        
                        # Check if this row contains our source_id or similar tender info
                        if (source_id in row_text or 
                            any(part in row_text for part in source_id.split('_') if len(part) > 3)):
                            
                            print(f"   🎯 Found matching tender row: {row_text[:100]}...")
                            
                            # Extract links from this row
                            for cell in cells:
                                for link in cell.find_all('a', href=True):
                                    href = link.get('href')
                                    link_text = link.get_text(strip=True)
                                    
                                    if href and ('view' in link_text.lower() or 'detail' in link_text.lower()):
                                        full_url = urljoin(self.base_url, href)
                                        target_tender_links.append((full_url, link_text))
                            
                            tender_found = True
                            break
                
                if tender_found:
                    break
            
            # Step 3: If specific tender not found, try general document access
            if not target_tender_links:
                print(f"   ⚠️  Specific tender not found, trying general document access")
                
                # Try standard document pages
                standard_doc_urls = [
                    f"{self.base_url}/nicgep/app?page=StandardBiddingDocuments&service=page",
                    f"{self.base_url}/nicgep/app?page=WebAnnouncements&service=page"
                ]
                
                for doc_url in standard_doc_urls:
                    target_tender_links.append((doc_url, "Standard Documents"))
            
            # Step 4: Access tender detail pages and extract documents
            if target_tender_links:
                print(f"   🔗 Found {len(target_tender_links)} potential document sources")
                
                for i, (detail_url, link_text) in enumerate(target_tender_links, 1):
                    print(f"   📋 Accessing source {i}: {link_text}")
                    
                    documents = self.extract_documents_from_page(detail_url, tender_folder, f"source_{i}")
                    
                    if documents:
                        result['downloaded_files'].extend(documents)
                        result['total_size'] += sum(doc.get('size', 0) for doc in documents)
                        print(f"      ✅ Found {len(documents)} documents from this source")
                    else:
                        print(f"      ⚠️  No documents from this source")
            
            # Step 5: Create tender information file
            tender_info = {
                'tender_id': tender_id,
                'source_id': source_id,
                'portal': 'Uttarakhand Government e-Procurement',
                'access_url': tenders_url,
                'documents_found': len(result['downloaded_files']),
                'total_size_mb': result['total_size'] / (1024 * 1024),
                'download_timestamp': datetime.now().isoformat(),
                'status': 'completed' if result['downloaded_files'] else 'no_documents'
            }
            
            info_file = tender_folder / "TENDER_INFO.json"
            with open(info_file, 'w') as f:
                json.dump(tender_info, f, indent=2)
            
            # Update result status
            if result['downloaded_files']:
                result['status'] = 'completed'
                result['folder_path'] = str(tender_folder)
                print(f"   🎉 SUCCESS: Downloaded {len(result['downloaded_files'])} documents")
            else:
                result['status'] = 'no_documents'
                print(f"   ⚠️  No downloadable documents found")
            
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result
    
    def extract_documents_from_page(self, page_url, tender_folder, source_name):
        """Extract and download documents from a specific page"""
        print(f"      🌐 Loading: {page_url}")
        
        try:
            response = self.session.get(page_url, timeout=15)
            
            if response.status_code != 200:
                print(f"         ❌ HTTP {response.status_code}")
                return []
            
            if 'session has timed out' in response.text.lower():
                print(f"         ❌ Session timeout")
                return []
            
            print(f"         📄 Page loaded: {len(response.text):,} chars")
            
            # Save the page for analysis
            page_file = tender_folder / f"{source_name}_page.html"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Parse page for document links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            documents = []
            
            # Look for direct PDF links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                
                # Direct PDF links
                if '.pdf' in href.lower():
                    full_url = urljoin(page_url, href)
                    documents.append({
                        'url': full_url,
                        'text': link_text,
                        'type': 'direct_pdf',
                        'source': source_name
                    })
                
                # Document-related links
                elif (any(keyword in link_text.lower() for keyword in 
                         ['download', 'document', 'attachment', 'nit', 'boq', 'tender']) and
                      len(link_text) > 5):
                    
                    full_url = urljoin(page_url, href)
                    documents.append({
                        'url': full_url,
                        'text': link_text,
                        'type': 'document_link',
                        'source': source_name
                    })
            
            # Look for embedded documents or form submissions
            for form in soup.find_all('form'):
                action = form.get('action', '')
                if 'download' in action.lower() or 'document' in action.lower():
                    full_url = urljoin(page_url, action)
                    documents.append({
                        'url': full_url,
                        'text': 'Form Download',
                        'type': 'form_action', 
                        'source': source_name
                    })
            
            print(f"         🔗 Found {len(documents)} potential document links")
            
            # Download the documents
            downloaded = []
            for i, doc in enumerate(documents[:5], 1):  # Limit to 5 documents per source
                download_result = self.download_document(doc, tender_folder, f"{source_name}_doc_{i}")
                if download_result:
                    downloaded.append(download_result)
            
            return downloaded
            
        except Exception as e:
            print(f"         ❌ Page extraction failed: {e}")
            return []
    
    def download_document(self, doc_info, tender_folder, file_prefix):
        """Download a specific document"""
        print(f"         ⬇️  Downloading: {doc_info['text'][:40]}...")
        
        try:
            response = self.session.get(doc_info['url'], timeout=30)
            
            if response.status_code == 200:
                content = response.content
                
                # Validate document content
                is_valid_doc = (
                    len(content) > 1000 and (
                        content.startswith(b'%PDF') or  # PDF
                        content.startswith(b'PK') or   # Office docs
                        (b'<html' not in content[:500].lower() and 
                         b'<!doctype' not in content[:500].lower())
                    )
                )
                
                if is_valid_doc:
                    # Generate filename
                    filename = self.generate_document_filename(doc_info, content)
                    file_path = tender_folder / f"{file_prefix}_{filename}"
                    
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    print(f"            ✅ Downloaded: {filename} ({len(content):,} bytes)")
                    
                    return {
                        'filename': filename,
                        'size': len(content),
                        'path': str(file_path),
                        'url': doc_info['url'],
                        'type': self.detect_file_type(content),
                        'source': doc_info['source']
                    }
                else:
                    print(f"            ❌ Invalid document (HTML or too small)")
            else:
                print(f"            ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"            ❌ Download error: {e}")
        
        return None
    
    def generate_document_filename(self, doc_info, content):
        """Generate appropriate filename for document"""
        
        # Try to detect file type from content
        if content.startswith(b'%PDF'):
            ext = '.pdf'
        elif content.startswith(b'PK'):
            ext = '.docx'  # Could be docx, xlsx, etc.
        else:
            ext = '.pdf'   # Default assumption
        
        # Create base filename from text
        text = doc_info.get('text', 'document')
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        clean_text = '_'.join(clean_text.split()[:4])
        
        if not clean_text:
            clean_text = f"uttarakhand_doc_{int(time.time())}"
        
        return clean_text + ext
    
    def detect_file_type(self, content):
        """Detect file type from content"""
        if content.startswith(b'%PDF'):
            return 'PDF'
        elif content.startswith(b'PK'):
            return 'Office Document'
        else:
            return 'Unknown'

def test_uttarakhand_production():
    """Test the production downloader"""
    print("🚀 UTTARAKHAND PRODUCTION DOWNLOADER TEST")
    print("=" * 45)
    
    downloader = UttarakhandProductionDownloader()
    
    # Test with a sample tender ID from our database
    test_tender_id = "490e3361-24ba-4837-a533-3ffede026294"
    test_source_id = "2026_UKJS_92588_1"
    
    result = downloader.download_documents_for_tender(test_tender_id, test_source_id)
    
    print(f"\\n📊 TEST RESULTS:")
    print(f"   Status: {result['status']}")
    print(f"   Files Downloaded: {len(result.get('downloaded_files', []))}")
    print(f"   Total Size: {result.get('total_size', 0)/(1024*1024):.1f} MB")
    
    if result.get('downloaded_files'):
        print(f"   ✅ SUCCESS: Uttarakhand document download working!")
        print(f"   📁 Files saved in: {result.get('folder_path', 'Unknown')}")
        
        for doc in result['downloaded_files']:
            print(f"      📄 {doc['filename']} ({doc['size']:,} bytes) [{doc['type']}]")
        
        return True
    else:
        print(f"   ⚠️  No documents downloaded - {result.get('error', 'Unknown reason')}")
        return False

if __name__ == "__main__":
    success = test_uttarakhand_production()
    
    if success:
        print(f"\\n🎉 READY FOR PRODUCTION INTEGRATION!")
    else:
        print(f"\\n🔧 Needs further refinement")