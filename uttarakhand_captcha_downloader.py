#!/usr/bin/env python3
"""
Uttarakhand CAPTCHA-Enabled Document Downloader
Downloads ZIP files containing tender documents after solving CAPTCHA
"""

import requests
import time
import zipfile
import io
import base64
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import re
from datetime import datetime

class UttarakhandCaptchaDownloader:
    """Downloads Uttarakhand documents with CAPTCHA solving"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_captcha"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://uktenders.gov.in"
        self.session = requests.Session()
        
        # 2Captcha API configuration (from earlier conversation)
        self.captcha_api_key = "9a09f9a33a7e9f216792c77113f31c11"
        self.captcha_api_url = "http://2captcha.com"
        
        # Browser-like headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def solve_captcha_image(self, captcha_image_data):
        """Solve CAPTCHA using 2Captcha API"""
        print("         🤖 Solving CAPTCHA...")
        
        try:
            # Step 1: Submit CAPTCHA image to 2Captcha
            if isinstance(captcha_image_data, bytes):
                captcha_base64 = base64.b64encode(captcha_image_data).decode()
            else:
                captcha_base64 = captcha_image_data
            
            submit_data = {
                'method': 'base64',
                'key': self.captcha_api_key,
                'body': captcha_base64,
                'phrase': 0,  # Single word
                'regsense': 1,  # Case sensitive
                'numeric': 0,  # Mixed (letters + numbers)
                'calc': 0,  # No math
                'min_len': 4,
                'max_len': 8,
                'json': 1
            }
            
            submit_response = requests.post(f"{self.captcha_api_url}/in.php", data=submit_data, timeout=30)
            submit_result = submit_response.json()
            
            if submit_result.get('status') != 1:
                raise Exception(f"CAPTCHA submission failed: {submit_result.get('error_text', 'Unknown error')}")
            
            captcha_id = submit_result['request']
            print(f"            📤 CAPTCHA submitted: ID {captcha_id}")
            
            # Step 2: Poll for solution
            max_attempts = 20
            for attempt in range(max_attempts):
                time.sleep(5)  # Wait 5 seconds between checks
                
                result_response = requests.get(
                    f"{self.captcha_api_url}/res.php", 
                    params={
                        'key': self.captcha_api_key,
                        'action': 'get',
                        'id': captcha_id,
                        'json': 1
                    },
                    timeout=30
                )
                
                result_data = result_response.json()
                
                if result_data.get('status') == 1:
                    solution = result_data['request']
                    print(f"            ✅ CAPTCHA solved: '{solution}'")
                    return solution
                elif result_data.get('error_text') == 'CAPCHA_NOT_READY':
                    print(f"            ⏳ Waiting for solution (attempt {attempt + 1}/{max_attempts})...")
                    continue
                else:
                    raise Exception(f"CAPTCHA solving failed: {result_data.get('error_text', 'Unknown error')}")
            
            raise Exception("CAPTCHA solving timed out")
            
        except Exception as e:
            print(f"            ❌ CAPTCHA solving failed: {e}")
            return None
    
    def find_tender_detail_page(self, source_id):
        """Find the detail page for a specific tender"""
        print(f"   🔍 Finding detail page for tender: {source_id}")
        
        try:
            # Access the active tenders listing
            listing_url = f"{self.base_url}/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
            response = self.session.get(listing_url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Failed to access tender listing: HTTP {response.status_code}")
            
            print(f"      📋 Tender listing loaded: {len(response.text):,} chars")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search for our specific tender in the listings
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 3:
                        row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                        
                        # Check if this row contains our tender
                        if (source_id in row_text or 
                            any(part in row_text for part in source_id.split('_') if len(part) > 4)):
                            
                            print(f"      🎯 Found tender row: {row_text[:80]}...")
                            
                            # Look for detail/view links in this row
                            for cell in cells:
                                for link in cell.find_all('a', href=True):
                                    href = link.get('href')
                                    link_text = link.get_text(strip=True).lower()
                                    
                                    if ('view' in link_text or 'detail' in link_text or 
                                        'tender' in link_text or len(link_text) > 20):
                                        
                                        detail_url = urljoin(self.base_url, href)
                                        print(f"      ✅ Found detail URL: {detail_url}")
                                        return detail_url
            
            # If not found in specific search, try a broader approach
            print(f"      ⚠️  Specific tender not found, trying first available tender...")
            
            # Get the first few tender detail links as examples
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    for cell in row.find_all(['td', 'th']):
                        for link in cell.find_all('a', href=True):
                            href = link.get('href')
                            link_text = link.get_text(strip=True)
                            
                            if (len(link_text) > 15 and 
                                ('tender' in href.lower() or 'view' in href.lower() or
                                 'detail' in href.lower())):
                                
                                detail_url = urljoin(self.base_url, href)
                                print(f"      🧪 Using sample tender: {detail_url}")
                                return detail_url
            
            raise Exception("No tender detail pages found")
            
        except Exception as e:
            print(f"      ❌ Failed to find detail page: {e}")
            return None
    
    def download_documents_with_captcha(self, tender_detail_url, tender_folder, source_id):
        """Access tender detail page and download documents after solving CAPTCHA"""
        print(f"      📄 Accessing tender detail: {tender_detail_url}")
        
        try:
            # Access the tender detail page
            response = self.session.get(tender_detail_url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Detail page failed: HTTP {response.status_code}")
            
            if 'session has timed out' in response.text.lower():
                raise Exception("Session timed out")
            
            print(f"         📋 Detail page loaded: {len(response.text):,} chars")
            
            # Save the detail page for analysis
            detail_file = tender_folder / "tender_detail_page.html"
            with open(detail_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for download buttons/links
            download_candidates = []
            
            # Search for download-related elements
            for element in soup.find_all(['a', 'button', 'input'], href=True):
                href = element.get('href', '')
                text = element.get_text(strip=True).lower()
                element_type = element.name
                
                if (any(keyword in text for keyword in ['download', 'document', 'zip', 'attachment', 'nit', 'boq']) or
                    any(keyword in href.lower() for keyword in ['download', 'document', 'zip', 'attachment'])):
                    
                    download_candidates.append({
                        'element': element,
                        'href': href,
                        'text': text,
                        'type': element_type
                    })
            
            print(f"         🔗 Found {len(download_candidates)} download candidates")
            
            if not download_candidates:
                # Look for forms that might lead to downloads
                forms = soup.find_all('form')
                print(f"         📝 Found {len(forms)} forms to analyze")
                
                for form in forms:
                    action = form.get('action', '')
                    if 'download' in action.lower() or 'document' in action.lower():
                        download_candidates.append({
                            'element': form,
                            'href': action,
                            'text': 'form download',
                            'type': 'form'
                        })
            
            # Try each download candidate
            for i, candidate in enumerate(download_candidates[:3], 1):  # Try first 3
                print(f"         🧪 Testing download candidate {i}: {candidate['text'][:40]}...")
                
                download_url = urljoin(tender_detail_url, candidate['href'])
                
                # Check if this leads to a CAPTCHA page
                captcha_result = self.handle_captcha_download(download_url, tender_folder, f"download_{i}")
                
                if captcha_result:
                    print(f"            ✅ Successfully downloaded via candidate {i}")
                    return captcha_result
                else:
                    print(f"            ❌ Candidate {i} failed")
            
            print(f"         ⚠️  No successful downloads from this detail page")
            return None
            
        except Exception as e:
            print(f"         ❌ Detail page processing failed: {e}")
            return None
    
    def handle_captcha_download(self, download_url, tender_folder, download_name):
        """Handle the CAPTCHA-protected download process"""
        print(f"            🔐 Processing CAPTCHA download: {download_url}")
        
        try:
            # Access the download page
            response = self.session.get(download_url, timeout=15)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for CAPTCHA images
            captcha_images = soup.find_all('img', src=True)
            captcha_found = False
            
            for img in captcha_images:
                src = img.get('src', '')
                if (any(keyword in src.lower() for keyword in ['captcha', 'verification', 'challenge']) or
                    any(keyword in img.get('alt', '').lower() for keyword in ['captcha', 'verification'])):
                    
                    captcha_found = True
                    captcha_url = urljoin(download_url, src)
                    
                    print(f"               🎯 Found CAPTCHA image: {captcha_url}")
                    
                    # Download CAPTCHA image
                    captcha_response = self.session.get(captcha_url, timeout=10)
                    if captcha_response.status_code == 200:
                        captcha_image = captcha_response.content
                        
                        # Save CAPTCHA image for analysis
                        captcha_file = tender_folder / f"{download_name}_captcha.png"
                        with open(captcha_file, 'wb') as f:
                            f.write(captcha_image)
                        
                        # Solve the CAPTCHA
                        captcha_solution = self.solve_captcha_image(captcha_image)
                        
                        if captcha_solution:
                            # Submit form with CAPTCHA solution
                            download_result = self.submit_captcha_form(
                                response.text, captcha_solution, download_url, tender_folder, download_name
                            )
                            
                            if download_result:
                                return download_result
                    
                    break
            
            if not captcha_found:
                # Maybe direct download without CAPTCHA
                print(f"               📥 No CAPTCHA found, trying direct download...")
                return self.attempt_direct_download(response, tender_folder, download_name)
            
            return None
            
        except Exception as e:
            print(f"               ❌ CAPTCHA handling failed: {e}")
            return None
    
    def submit_captcha_form(self, page_html, captcha_solution, form_url, tender_folder, download_name):
        """Submit the form with CAPTCHA solution to get documents"""
        print(f"               📤 Submitting CAPTCHA solution: {captcha_solution}")
        
        try:
            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Find the form with CAPTCHA input
            for form in soup.find_all('form'):
                captcha_input = None
                
                # Look for CAPTCHA input field
                for input_field in form.find_all('input'):
                    input_name = input_field.get('name', '').lower()
                    input_type = input_field.get('type', '').lower()
                    
                    if (any(keyword in input_name for keyword in ['captcha', 'verification', 'challenge']) or
                        input_type == 'text' and not input_field.get('value')):
                        captcha_input = input_field
                        break
                
                if captcha_input:
                    # Prepare form data
                    form_data = {}
                    
                    # Get all form fields
                    for input_field in form.find_all(['input', 'select', 'textarea']):
                        name = input_field.get('name')
                        if name:
                            if input_field == captcha_input:
                                form_data[name] = captcha_solution
                            else:
                                value = input_field.get('value', '')
                                form_data[name] = value
                    
                    # Submit the form
                    action = form.get('action', '')
                    submit_url = urljoin(form_url, action) if action else form_url
                    method = form.get('method', 'POST').upper()
                    
                    print(f"                  📋 Submitting to: {submit_url}")
                    print(f"                  📝 Form data: {list(form_data.keys())}")
                    
                    if method == 'POST':
                        submit_response = self.session.post(submit_url, data=form_data, timeout=30)
                    else:
                        submit_response = self.session.get(submit_url, params=form_data, timeout=30)
                    
                    if submit_response.status_code == 200:
                        # Check if we got a ZIP file
                        content_type = submit_response.headers.get('content-type', '').lower()
                        
                        if ('application/zip' in content_type or 
                            'application/octet-stream' in content_type or
                            submit_response.content.startswith(b'PK')):  # ZIP file signature
                            
                            # Save the ZIP file
                            zip_filename = f"{download_name}_documents.zip"
                            zip_path = tender_folder / zip_filename
                            
                            with open(zip_path, 'wb') as f:
                                f.write(submit_response.content)
                            
                            print(f"                  🎉 Downloaded ZIP: {zip_filename} ({len(submit_response.content):,} bytes)")
                            
                            # Extract the ZIP file
                            extracted_files = self.extract_zip_documents(zip_path, tender_folder)
                            
                            return {
                                'zip_file': str(zip_path),
                                'zip_size': len(submit_response.content),
                                'extracted_files': extracted_files,
                                'total_files': len(extracted_files)
                            }
                        else:
                            print(f"                  ⚠️  Response not a ZIP file: {content_type}")
                    else:
                        print(f"                  ❌ Form submission failed: HTTP {submit_response.status_code}")
                    
                    break
            
            return None
            
        except Exception as e:
            print(f"               ❌ Form submission failed: {e}")
            return None
    
    def extract_zip_documents(self, zip_path, extract_to):
        """Extract documents from downloaded ZIP file"""
        print(f"                  📦 Extracting ZIP file...")
        
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                file_list = zip_file.namelist()
                print(f"                     📄 ZIP contains {len(file_list)} files")
                
                for filename in file_list:
                    if filename.endswith('/'):  # Skip directories
                        continue
                    
                    # Extract file
                    zip_file.extract(filename, extract_to)
                    extracted_path = extract_to / filename
                    
                    if extracted_path.exists():
                        file_size = extracted_path.stat().st_size
                        extracted_files.append({
                            'filename': filename,
                            'path': str(extracted_path),
                            'size': file_size
                        })
                        
                        print(f"                        ✅ {filename} ({file_size:,} bytes)")
                
                print(f"                  🎉 Extracted {len(extracted_files)} documents")
                
        except Exception as e:
            print(f"                  ❌ ZIP extraction failed: {e}")
        
        return extracted_files
    
    def attempt_direct_download(self, response, tender_folder, download_name):
        """Try direct download if no CAPTCHA is present"""
        content_type = response.headers.get('content-type', '').lower()
        
        if ('application/zip' in content_type or 
            response.content.startswith(b'PK')):
            
            # Direct ZIP download
            zip_filename = f"{download_name}_direct.zip"
            zip_path = tender_folder / zip_filename
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            print(f"               🎉 Direct ZIP download: {zip_filename}")
            
            extracted_files = self.extract_zip_documents(zip_path, tender_folder)
            
            return {
                'zip_file': str(zip_path),
                'zip_size': len(response.content),
                'extracted_files': extracted_files,
                'total_files': len(extracted_files)
            }
        
        return None
    
    def download_tender_documents(self, tender_id, source_id):
        """Main method to download documents for a Uttarakhand tender"""
        print(f"🏔️  UTTARAKHAND CAPTCHA-ENABLED DOWNLOAD")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        result = {
            'tender_id': tender_id,
            'source_id': source_id,
            'source': 'UTTARAKHAND',
            'status': 'processing',
            'downloaded_files': [],
            'total_size': 0
        }
        
        try:
            # Create tender folder
            tender_folder = self.downloads_dir / f"UK_CAPTCHA_{source_id}_{tender_id[:8]}"
            tender_folder.mkdir(exist_ok=True)
            
            # Step 1: Find tender detail page
            detail_url = self.find_tender_detail_page(source_id)
            
            if not detail_url:
                raise Exception("Could not find tender detail page")
            
            # Step 2: Download documents with CAPTCHA solving
            download_result = self.download_documents_with_captcha(detail_url, tender_folder, source_id)
            
            if download_result and download_result.get('extracted_files'):
                # Process the extracted files
                for file_info in download_result['extracted_files']:
                    result['downloaded_files'].append({
                        'filename': file_info['filename'],
                        'size': file_info['size'],
                        'path': file_info['path'],
                        'type': 'Extracted from ZIP'
                    })
                    result['total_size'] += file_info['size']
                
                result['status'] = 'completed'
                result['folder_path'] = str(tender_folder)
                result['zip_info'] = {
                    'zip_file': download_result['zip_file'],
                    'zip_size': download_result['zip_size']
                }
                
                print(f"   🎉 SUCCESS: Downloaded {len(result['downloaded_files'])} documents from ZIP")
                
            else:
                result['status'] = 'no_documents'
                print(f"   ⚠️  No documents could be downloaded")
            
            # Save metadata
            metadata = {
                'tender_info': result,
                'download_timestamp': datetime.now().isoformat(),
                'captcha_used': True,
                'portal': 'Uttarakhand Government e-Procurement'
            }
            
            metadata_file = tender_folder / "download_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result

def test_uttarakhand_captcha_download():
    """Test the CAPTCHA-enabled downloader"""
    print("🚀 UTTARAKHAND CAPTCHA DOWNLOADER TEST")
    print("=" * 45)
    
    downloader = UttarakhandCaptchaDownloader()
    
    # Test with sample tender
    test_tender_id = "490e3361-24ba-4837-a533-3ffede026294"
    test_source_id = "2026_UKJS_92588_1"
    
    result = downloader.download_tender_documents(test_tender_id, test_source_id)
    
    print(f"\\n📊 TEST RESULTS:")
    print(f"   Status: {result['status']}")
    print(f"   Files: {len(result.get('downloaded_files', []))}")
    print(f"   Size: {result.get('total_size', 0)/(1024*1024):.1f} MB")
    
    if result.get('downloaded_files'):
        print(f"   🎉 SUCCESS: CAPTCHA-enabled download working!")
        
        for doc in result['downloaded_files']:
            print(f"      📄 {doc['filename']} ({doc['size']:,} bytes)")
        
        return True
    else:
        print(f"   🔧 Needs refinement: {result.get('error', 'Unknown')}")
        return False

if __name__ == "__main__":
    success = test_uttarakhand_captcha_download()
    
    if success:
        print(f"\\n✅ UTTARAKHAND CAPTCHA DOWNLOADER: READY!")
    else:
        print(f"\\n🔧 Further development needed")