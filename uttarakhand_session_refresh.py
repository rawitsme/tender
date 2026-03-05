#!/usr/bin/env python3
"""
Uttarakhand Session Refresh System
Gets fresh session URLs for individual tenders, then accesses real documents with CAPTCHA
"""

import requests
import time
import base64
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
import re
import json
from datetime import datetime

class UttarakhandSessionRefresh:
    """Refresh expired sessions and access real tender documents"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_session"):
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
    
    def get_fresh_tender_session_urls(self):
        """Navigate portal to get fresh session URLs for individual tenders"""
        print("🔄 STEP 1: Getting fresh session URLs from portal navigation")
        
        fresh_urls = []
        
        try:
            # Try multiple entry points to find tender listings
            entry_points = [
                f"{self.base_url}/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
                f"{self.base_url}/nicgep/app?page=FrontEndTendersByOrganisation&service=page", 
                f"{self.base_url}/nicgep/app?page=FrontEndListTendersbyDate&service=page"
            ]
            
            for entry_url in entry_points:
                print(f"   📡 Trying: {entry_url.split('?')[1]}")
                
                try:
                    response = self.session.get(entry_url, timeout=15)
                    
                    if response.status_code != 200:
                        continue
                    
                    print(f"      ✅ Page loaded: {len(response.text):,} chars")
                    
                    # Look for direct tender links with session parameters
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        
                        # Look for DirectLink URLs with session parameters
                        if (('DirectLink' in href or 'service=direct' in href) and 
                            'session=T' in href and 'sp=' in href):
                            
                            full_url = urljoin(entry_url, href)
                            link_text = link.get_text(strip=True)
                            
                            fresh_urls.append({
                                'url': full_url,
                                'title': link_text,
                                'source_page': entry_url
                            })
                            
                            print(f"      🎯 Fresh session URL: {link_text[:40]}...")
                            
                            if len(fresh_urls) >= 10:  # Get up to 10 fresh URLs
                                break
                    
                    if fresh_urls:
                        break  # Found URLs, no need to try other entry points
                        
                except Exception as e:
                    print(f"      ❌ Error: {e}")
                    continue
            
            print(f"   📊 Found {len(fresh_urls)} fresh session URLs")
            return fresh_urls
            
        except Exception as e:
            print(f"   ❌ Navigation failed: {e}")
            return []
    
    def access_tender_with_fresh_session(self, tender_info):
        """Access individual tender page with fresh session URL"""
        print(f"📋 STEP 2: Accessing tender with fresh session")
        print(f"   🎯 Title: {tender_info['title'][:50]}...")
        print(f"   🔗 URL: {tender_info['url']}")
        
        try:
            response = self.session.get(tender_info['url'], timeout=15)
            
            if response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}")
                return None
            
            if 'session has timed out' in response.text.lower():
                print(f"   ⚠️  Session already expired")
                return None
            
            print(f"   ✅ Tender page loaded: {len(response.text):,} chars")
            
            # Save the page
            page_file = self.downloads_dir / f"fresh_tender_page.html"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Parse tender details and look for downloads
            tender_data = self.parse_tender_page(response.text, tender_info['url'])
            
            if tender_data:
                tender_data['fresh_url'] = tender_info['url']
                tender_data['title'] = tender_info['title']
                
            return tender_data
            
        except Exception as e:
            print(f"   ❌ Access failed: {e}")
            return None
    
    def parse_tender_page(self, page_content, base_url):
        """Parse tender page for details and download options"""
        print("   🔍 Parsing tender page for download options")
        
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Look for tender details
        tender_info = {}
        
        # Get tender title/description
        for elem in soup.find_all(['title', 'h1', 'h2', 'h3']):
            text = elem.get_text(strip=True)
            if len(text) > 20 and 'tender' in text.lower():
                tender_info['description'] = text
                break
        
        # Look for download options
        download_options = []
        
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
                
                print(f"      📥 Download option: {element.get_text(strip=True)}")
        
        if download_options:
            tender_info['download_options'] = download_options
            tender_info['has_downloads'] = True
            print(f"   ✅ Found {len(download_options)} download options")
        else:
            tender_info['has_downloads'] = False
            print(f"   ⚠️  No download options found")
        
        return tender_info
    
    def test_document_download_with_captcha(self, download_option, tender_folder):
        """Test downloading documents with CAPTCHA support"""
        print(f"🔥 STEP 3: Testing document download with CAPTCHA")
        print(f"   📥 Download: {download_option['text']}")
        print(f"   🔗 URL: {download_option['url']}")
        
        try:
            response = self.session.get(download_option['url'], timeout=15)
            
            if response.status_code != 200:
                print(f"   ❌ Download page failed: HTTP {response.status_code}")
                return None
            
            print(f"   ✅ Download page loaded: {len(response.text):,} chars")
            
            # Save download page
            download_page_file = tender_folder / "download_page.html"
            with open(download_page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Check for CAPTCHA
            soup = BeautifulSoup(response.text, 'html.parser')
            
            captcha_images = []
            for img in soup.find_all('img'):
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                if (any(keyword in src.lower() for keyword in ['captcha', 'verification', 'challenge']) or
                    any(keyword in alt for keyword in ['captcha', 'verification', 'challenge'])):
                    
                    captcha_url = urljoin(download_option['url'], src)
                    captcha_images.append(captcha_url)
                    print(f"   🤖 CAPTCHA found: {captcha_url}")
            
            if captcha_images:
                # Download and solve first CAPTCHA
                result = self.handle_captcha_download(captcha_images[0], soup, download_option['url'], tender_folder)
                
                if result:
                    print(f"   🎉 SUCCESS: CAPTCHA solved and documents downloaded!")
                    return result
                else:
                    print(f"   ❌ CAPTCHA solving failed")
            else:
                # Check if direct file download
                content_type = response.headers.get('content-type', '').lower()
                
                if any(ftype in content_type for ftype in ['zip', 'pdf', 'application']):
                    print(f"   📄 Direct download: {content_type}")
                    
                    # Save file directly
                    file_ext = 'zip' if 'zip' in content_type else 'pdf' if 'pdf' in content_type else 'bin'
                    file_path = tender_folder / f"tender_document.{file_ext}"
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"   💾 File saved: {file_path} ({len(response.content):,} bytes)")
                    
                    return {
                        'status': 'direct_download',
                        'file_path': str(file_path),
                        'file_size': len(response.content),
                        'content_type': content_type
                    }
                else:
                    print(f"   ⚠️  No CAPTCHA, no direct file ({content_type})")
            
            return None
            
        except Exception as e:
            print(f"   ❌ Download test failed: {e}")
            return None
    
    def handle_captcha_download(self, captcha_url, soup, form_url, tender_folder):
        """Download CAPTCHA, solve with 2Captcha, submit form, get ZIP"""
        print(f"   🤖 Solving CAPTCHA: {captcha_url}")
        
        try:
            # Download CAPTCHA image
            captcha_response = self.session.get(captcha_url, timeout=10)
            
            if captcha_response.status_code == 200:
                captcha_img = captcha_response.content
                
                # Save CAPTCHA image
                captcha_file = tender_folder / "captcha.png"
                with open(captcha_file, 'wb') as f:
                    f.write(captcha_img)
                
                print(f"      💾 CAPTCHA saved: {len(captcha_img)} bytes")
                
                # Solve with 2Captcha
                solution = self.solve_captcha_2captcha(captcha_img)
                
                if solution:
                    print(f"      ✅ CAPTCHA solved: '{solution}'")
                    
                    # Submit form with solution
                    result = self.submit_captcha_form(soup, solution, form_url, tender_folder)
                    
                    return result
                else:
                    print(f"      ❌ CAPTCHA solving failed")
            else:
                print(f"      ❌ CAPTCHA download failed: HTTP {captcha_response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"      ❌ CAPTCHA handling failed: {e}")
            return None
    
    def solve_captcha_2captcha(self, captcha_image):
        """Solve CAPTCHA using 2Captcha API"""
        print("      🔄 Submitting to 2Captcha...")
        
        try:
            # Submit image
            captcha_base64 = base64.b64encode(captcha_image).decode()
            
            submit_data = {
                'method': 'base64',
                'key': self.captcha_api_key,
                'body': captcha_base64,
                'phrase': 0,
                'regsense': 1,
                'numeric': 0,
                'calc': 0,
                'min_len': 4,
                'max_len': 8,
                'json': 1
            }
            
            submit_response = requests.post(f"{self.captcha_api_url}/in.php", data=submit_data, timeout=30)
            submit_result = submit_response.json()
            
            if submit_result.get('status') != 1:
                raise Exception(f"Submission failed: {submit_result.get('error_text')}")
            
            captcha_id = submit_result['request']
            print(f"         📤 Submitted with ID: {captcha_id}")
            
            # Poll for solution
            for attempt in range(24):  # Max 2 minutes
                time.sleep(5)
                
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
                    return result_data['request']
                elif result_data.get('error_text') == 'CAPCHA_NOT_READY':
                    continue
                else:
                    raise Exception(f"Solving failed: {result_data.get('error_text')}")
            
            raise Exception("Timeout waiting for solution")
            
        except Exception as e:
            print(f"         ❌ 2Captcha error: {e}")
            return None
    
    def submit_captcha_form(self, soup, solution, form_url, tender_folder):
        """Submit form with CAPTCHA solution"""
        print(f"      📤 Submitting form with solution: {solution}")
        
        # Find form with CAPTCHA input
        for form in soup.find_all('form'):
            form_data = {}
            captcha_input_found = False
            
            for input_field in form.find_all(['input', 'select']):
                name = input_field.get('name')
                if name:
                    input_type = input_field.get('type', '').lower()
                    
                    # Check if this is the CAPTCHA input
                    if (any(keyword in name.lower() for keyword in ['captcha', 'verification', 'challenge']) or
                        (input_type == 'text' and not input_field.get('value'))):
                        
                        form_data[name] = solution
                        captcha_input_found = True
                    else:
                        form_data[name] = input_field.get('value', '')
            
            if captcha_input_found:
                # Submit the form
                action = form.get('action', '')
                submit_url = urljoin(form_url, action) if action else form_url
                method = form.get('method', 'POST').upper()
                
                print(f"         🌐 Submitting to: {submit_url}")
                
                if method == 'POST':
                    response = self.session.post(submit_url, data=form_data, timeout=30)
                else:
                    response = self.session.get(submit_url, params=form_data, timeout=30)
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if ('zip' in content_type or response.content.startswith(b'PK')):
                        # Got ZIP file!
                        zip_path = tender_folder / "tender_documents.zip"
                        
                        with open(zip_path, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"         🎉 ZIP downloaded: {len(response.content):,} bytes")
                        
                        # Extract ZIP
                        extracted_files = []
                        
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                                for filename in zip_file.namelist():
                                    if not filename.endswith('/'):
                                        zip_file.extract(filename, tender_folder)
                                        
                                        extracted_path = tender_folder / filename
                                        if extracted_path.exists():
                                            file_size = extracted_path.stat().st_size
                                            extracted_files.append({
                                                'filename': filename,
                                                'path': str(extracted_path),
                                                'size': file_size
                                            })
                                            print(f"            📄 {filename} ({file_size:,} bytes)")
                        
                        except Exception as e:
                            print(f"         ❌ ZIP extraction failed: {e}")
                        
                        return {
                            'status': 'captcha_solved',
                            'zip_path': str(zip_path),
                            'zip_size': len(response.content),
                            'extracted_files': extracted_files
                        }
                    else:
                        print(f"         ⚠️  Response not ZIP: {content_type}")
                
                break
        
        return None
    
    def test_complete_flow(self):
        """Test complete flow: session refresh → tender access → document download"""
        print("🚀 UTTARAKHAND SESSION REFRESH & DOWNLOAD TEST")
        print("=" * 52)
        
        result = {
            'status': 'testing',
            'fresh_sessions_found': 0,
            'tender_accessed': False,
            'downloads_found': 0,
            'captcha_solved': False,
            'documents_downloaded': 0
        }
        
        try:
            # Step 1: Get fresh session URLs
            fresh_urls = self.get_fresh_tender_session_urls()
            
            if not fresh_urls:
                result['status'] = 'no_fresh_sessions'
                return result
            
            result['fresh_sessions_found'] = len(fresh_urls)
            
            # Step 2: Test accessing tenders
            for i, tender_info in enumerate(fresh_urls[:3], 1):  # Test first 3
                print(f"\n🎯 TESTING TENDER {i}/{min(3, len(fresh_urls))}")
                
                tender_data = self.access_tender_with_fresh_session(tender_info)
                
                if tender_data and tender_data.get('has_downloads'):
                    result['tender_accessed'] = True
                    result['downloads_found'] = len(tender_data['download_options'])
                    
                    # Step 3: Test document download with CAPTCHA
                    tender_folder = self.downloads_dir / f"tender_{i}"
                    tender_folder.mkdir(exist_ok=True)
                    
                    for download_option in tender_data['download_options'][:1]:  # Test first download
                        download_result = self.test_document_download_with_captcha(
                            download_option, tender_folder
                        )
                        
                        if download_result:
                            if download_result['status'] == 'captcha_solved':
                                result['captcha_solved'] = True
                                result['documents_downloaded'] = len(download_result.get('extracted_files', []))
                                result['status'] = 'success'
                                result['download_result'] = download_result
                                return result
                            elif download_result['status'] == 'direct_download':
                                result['documents_downloaded'] = 1
                                result['status'] = 'success'
                                result['download_result'] = download_result
                                return result
            
            result['status'] = 'no_documents' if result['tender_accessed'] else 'no_tender_access'
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result

def test_session_refresh_system():
    """Test the complete session refresh and download system"""
    refresher = UttarakhandSessionRefresh()
    result = refresher.test_complete_flow()
    
    print(f"\n📊 FINAL TEST RESULTS:")
    print(f"   Status: {result['status']}")
    print(f"   Fresh Sessions: {result['fresh_sessions_found']}")
    print(f"   Tender Accessed: {result['tender_accessed']}")
    print(f"   Downloads Found: {result['downloads_found']}")
    print(f"   CAPTCHA Solved: {result['captcha_solved']}")
    print(f"   Documents Downloaded: {result['documents_downloaded']}")
    
    if result['status'] == 'success':
        print(f"\n🎉 SUCCESS: Complete workflow working!")
        
        if result.get('download_result'):
            dr = result['download_result']
            if dr['status'] == 'captcha_solved':
                print(f"   🤖 CAPTCHA solved successfully")
                print(f"   📦 ZIP: {dr['zip_size']:,} bytes")
                print(f"   📄 Files: {len(dr.get('extracted_files', []))} extracted")
            else:
                print(f"   📄 Direct download: {dr['file_size']:,} bytes")
        
        return True
    else:
        print(f"   Issue: {result.get('error', 'Unknown')}")
        return False

if __name__ == "__main__":
    success = test_session_refresh_system()
    
    if success:
        print(f"\n✅ SESSION REFRESH SYSTEM: SUCCESS!")
        print(f"Ready for production integration!")
    else:
        print(f"\n🔧 System needs refinement")