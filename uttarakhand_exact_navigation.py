#!/usr/bin/env python3
"""
Uttarakhand Exact Navigation - Following Rahul's exact steps
1. Main page → Active Tenders/Tenders by Organisation  
2. Department list → Click department (shows tender count)
3. Tender listing → Click specific tender 
4. Tender details → Download ZIP file button
5. CAPTCHA → Solve → ZIP download
"""

import requests
import time
import zipfile
import base64
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import re
from datetime import datetime

class UttarakhandExactNavigator:
    """Follows the exact navigation path described by Rahul"""
    
    def __init__(self, downloads_dir="storage/documents/uttarakhand_exact"):
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
    
    def step1_access_main_navigation(self):
        """Step 1: Access main page and find Active Tenders / Tenders by Organisation"""
        print("📋 STEP 1: Accessing main page navigation")
        
        try:
            # Access main portal page
            response = self.session.get(self.base_url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Main page failed: HTTP {response.status_code}")
            
            print(f"   ✅ Main page loaded: {len(response.text):,} chars")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for navigation options
            navigation_options = {}
            
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link.get('href')
                
                if ('active tender' in text.lower() or 
                    'tender by organisation' in text.lower() or
                    'tender by organization' in text.lower() or
                    'tenders by organisation' in text.lower()):
                    
                    full_url = urljoin(self.base_url, href)
                    navigation_options[text] = full_url
                    print(f"   🔗 Found navigation: {text} -> {full_url}")
            
            # Try common paths if not found in main page
            if not navigation_options:
                print("   🔍 Navigation not found on main page, trying common paths...")
                
                common_paths = {
                    'Active Tenders': '/nicgep/app?page=FrontEndLatestActiveTenders&service=page',
                    'Tenders by Organisation': '/nicgep/app?page=FrontEndTendersByOrganisation&service=page',
                    'Active Tenders Alt': '/nicgep/app?component=DirectLink&page=ActiveTenders'
                }
                
                for name, path in common_paths.items():
                    full_url = self.base_url + path
                    navigation_options[name] = full_url
                    print(f"   🧪 Testing path: {name} -> {full_url}")
            
            return navigation_options
            
        except Exception as e:
            print(f"   ❌ Step 1 failed: {e}")
            return {}
    
    def step2_get_department_list(self, navigation_options):
        """Step 2: Access department list showing tender counts"""
        print("📋 STEP 2: Getting department list with tender counts")
        
        # Try "Active Tenders" first (has real tenders, not templates)
        preferred_options = [
            'Active Tenders',
            'Active Tenders Alt',
            'Tenders by Organisation',
            'Tender by Organisation'
        ]
        
        for option_name in preferred_options:
            if option_name in navigation_options:
                target_url = navigation_options[option_name]
                print(f"   🎯 Trying: {option_name}")
                
                try:
                    response = self.session.get(target_url, timeout=15)
                    
                    if response.status_code != 200:
                        print(f"      ❌ HTTP {response.status_code}")
                        continue
                    
                    if 'session has timed out' in response.text.lower():
                        print(f"      ❌ Session timeout")
                        continue
                    
                    print(f"      ✅ Page loaded: {len(response.text):,} chars")
                    
                    # Save the page for analysis
                    dept_page_file = self.downloads_dir / f"step2_{option_name.replace(' ', '_')}_page.html"
                    with open(dept_page_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    
                    # Parse for department links
                    departments = self.parse_department_links(response.text, target_url)
                    
                    if departments:
                        print(f"      🎉 Found {len(departments)} departments with tender counts")
                        return departments
                    else:
                        print(f"      ⚠️  No departments found on this page")
                
                except Exception as e:
                    print(f"      ❌ Error: {e}")
                    continue
        
        print("   ❌ Could not find department listing")
        return []
    
    def parse_department_links(self, page_content, base_url):
        """Parse department links with tender counts or direct tender links"""
        print("      🔍 Parsing links for tenders...")
        
        soup = BeautifulSoup(page_content, 'html.parser')
        departments = []
        
        # Check if this is Active Tenders page (has actual tender listings)
        if 'FrontEndLatestActiveTenders' in base_url:
            print("         📋 Active Tenders page detected - looking for direct tender links")
            
            # Look for actual tender entries in tables
            tender_links = []
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                
                if len(rows) > 3:  # Substantial table
                    for row in rows[1:11]:  # Skip header, check first 10 rows
                        cells = row.find_all(['td', 'th'])
                        
                        if len(cells) >= 3:
                            row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                            
                            # Look for real tender indicators
                            if (len(row_text) > 50 and 
                                any(keyword in row_text.lower() for keyword in 
                                    ['tender', 'work', 'supply', 'construction', 'maintenance', 'procurement']) and
                                any(indicator in row_text for indicator in ['2026', '2025', '2024', 'Rs', '₹'])):
                                
                                # Find clickable links in this row
                                for cell in cells:
                                    for link in cell.find_all('a', href=True):
                                        link_text = link.get_text(strip=True)
                                        href = link.get('href')
                                        
                                        if (len(link_text) > 20 and 
                                            ('view' in link_text.lower() or 'detail' in link_text.lower() or
                                             'tender' in href.lower())):
                                            
                                            full_url = urljoin(base_url, href)
                                            tender_links.append({
                                                'title': link_text,
                                                'url': full_url,
                                                'row_text': row_text
                                            })
                                            print(f"         📋 Real tender: {link_text[:40]}...")
                                            break
                                
                                if len(tender_links) >= 10:  # Found enough
                                    break
            
            if tender_links:
                # Create a fake "department" for Active Tenders
                departments.append({
                    'name': 'Active Tenders (Direct)',
                    'url': base_url,
                    'tender_count': len(tender_links),
                    'tender_links': tender_links,
                    'href': base_url
                })
                print(f"         🎯 Found {len(tender_links)} real tenders in Active Tenders")
                return departments
        
        # Original logic for department-based navigation (Tenders by Organisation)
        print("         🏢 Department-based page detected - looking for department links")
        
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link.get('href')
            
            # Look for patterns like "Department Name (25)" or "Department Name - 25 tenders"
            if (re.search(r'\(\d+\)', text) or  # (25)
                re.search(r'\d+\s*tender', text, re.IGNORECASE) or  # "25 tenders"  
                re.search(r':\s*\d+', text) or  # ": 25"
                (len(text) > 10 and any(char.isdigit() for char in text))):  # Contains numbers
                
                full_url = urljoin(base_url, href)
                
                # Extract tender count
                count_match = re.search(r'(\d+)', text)
                tender_count = int(count_match.group(1)) if count_match else 0
                
                departments.append({
                    'name': text,
                    'url': full_url,
                    'tender_count': tender_count,
                    'href': href
                })
                
                print(f"         🏢 {text} -> {tender_count} tenders")
        
        # Sort by tender count (descending)
        departments.sort(key=lambda x: x['tender_count'], reverse=True)
        
        return departments[:10]  # Return top 10 departments
    
    def step3_access_department_tenders(self, departments, max_departments=3):
        """Step 3: Access specific department to see tender listing"""
        print("📋 STEP 3: Accessing department tender listings")
        
        department_results = []
        
        for i, dept in enumerate(departments[:max_departments], 1):
            print(f"   🏢 Department {i}: {dept['name']} ({dept['tender_count']} tenders)")
            print(f"      🔗 URL: {dept['url']}")
            
            # Check if this department already has tender links (Active Tenders case)
            if 'tender_links' in dept:
                print(f"      🎯 Using pre-parsed tender links from Active Tenders")
                
                department_results.append({
                    'department': dept,
                    'tender_links': dept['tender_links'],
                    'page_content': f"Active Tenders Direct - {len(dept['tender_links'])} tenders"
                })
                
                # Show first few tenders
                for j, tender in enumerate(dept['tender_links'][:3], 1):
                    print(f"         📋 Tender {j}: {tender['title'][:50]}...")
                
                continue
            
            # Original department navigation logic
            try:
                response = self.session.get(dept['url'], timeout=15)
                
                if response.status_code != 200:
                    print(f"      ❌ HTTP {response.status_code}")
                    continue
                
                if 'session has timed out' in response.text.lower():
                    print(f"      ❌ Session timeout")
                    continue
                
                print(f"      ✅ Tender listing loaded: {len(response.text):,} chars")
                
                # Save department tender listing
                dept_file = self.downloads_dir / f"step3_dept_{i}_tenders.html"
                with open(dept_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Parse tender links from this department
                tender_links = self.parse_tender_links(response.text, dept['url'])
                
                if tender_links:
                    print(f"      🎯 Found {len(tender_links)} tender links")
                    
                    department_results.append({
                        'department': dept,
                        'tender_links': tender_links,
                        'page_content': response.text
                    })
                    
                    # Show first few tenders
                    for j, tender in enumerate(tender_links[:3], 1):
                        print(f"         📋 Tender {j}: {tender['title'][:50]}...")
                else:
                    print(f"      ⚠️  No tender links found")
            
            except Exception as e:
                print(f"      ❌ Department access failed: {e}")
                continue
        
        return department_results
    
    def parse_tender_links(self, page_content, base_url):
        """Parse individual tender links from department listing"""
        soup = BeautifulSoup(page_content, 'html.parser')
        tender_links = []
        
        # Look for tender entries in tables or lists
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:  # At least 2 columns
                    row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                    
                    # Skip header rows
                    if any(header in row_text.lower() for header in ['s.no', 'tender no', 'description', 'department']):
                        continue
                    
                    # Look for tender-like content
                    if (len(row_text) > 20 and 
                        (any(keyword in row_text.lower() for keyword in ['tender', 'work', 'supply', 'service', 'procurement']) or
                         re.search(r'\d{4}.*\d{4}', row_text))):  # Contains year-like numbers
                        
                        # Find clickable links in this row
                        for cell in cells:
                            for link in cell.find_all('a', href=True):
                                link_text = link.get_text(strip=True)
                                href = link.get('href')
                                
                                if (len(link_text) > 10 and 
                                    ('view' in link_text.lower() or 
                                     'detail' in link_text.lower() or
                                     len(link_text) > 30)):  # Long text likely to be tender title
                                    
                                    full_url = urljoin(base_url, href)
                                    tender_links.append({
                                        'title': link_text,
                                        'url': full_url,
                                        'href': href,
                                        'row_text': row_text
                                    })
        
        # Also check for direct links outside tables
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link.get('href')
            
            if (len(text) > 30 and 
                any(keyword in text.lower() for keyword in ['tender', 'work', 'supply', 'construction', 'maintenance']) and
                any(keyword in href.lower() for keyword in ['tender', 'view', 'detail'])):
                
                full_url = urljoin(base_url, href)
                tender_links.append({
                    'title': text,
                    'url': full_url,
                    'href': href,
                    'row_text': text
                })
        
        # Remove duplicates and limit results
        seen_urls = set()
        unique_tenders = []
        
        for tender in tender_links:
            if tender['url'] not in seen_urls:
                seen_urls.add(tender['url'])
                unique_tenders.append(tender)
        
        return unique_tenders[:5]  # Return top 5 tenders
    
    def step4_access_tender_details(self, tender_link):
        """Step 4: Access specific tender to find download ZIP button"""
        print(f"📋 STEP 4: Accessing tender details")
        print(f"   📋 Tender: {tender_link['title'][:60]}...")
        print(f"   🔗 URL: {tender_link['url']}")
        
        try:
            response = self.session.get(tender_link['url'], timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Tender page failed: HTTP {response.status_code}")
            
            if 'session has timed out' in response.text.lower():
                raise Exception("Session timed out")
            
            print(f"   ✅ Tender details loaded: {len(response.text):,} chars")
            
            # Save tender details page
            details_file = self.downloads_dir / "step4_tender_details.html"
            with open(details_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Look for download ZIP button
            download_options = self.find_zip_download_button(response.text, tender_link['url'])
            
            if download_options:
                print(f"   🎯 Found {len(download_options)} download options:")
                for i, option in enumerate(download_options, 1):
                    print(f"      {i}. {option['text']} -> {option['url']}")
                
                return download_options[0]  # Return first option
            else:
                print(f"   ⚠️  No download ZIP button found")
                return None
                
        except Exception as e:
            print(f"   ❌ Step 4 failed: {e}")
            return None
    
    def find_zip_download_button(self, page_content, base_url):
        """Find the download ZIP file button on tender details page"""
        soup = BeautifulSoup(page_content, 'html.parser')
        download_options = []
        
        # Look for download-related buttons/links
        for element in soup.find_all(['a', 'button', 'input'], href=True):
            text = element.get_text(strip=True).lower()
            href = element.get('href', '')
            
            # Look for ZIP download indicators
            if (any(keyword in text for keyword in ['download', 'zip', 'attachment', 'document', 'file']) and
                ('zip' in text or 'download' in text)):
                
                full_url = urljoin(base_url, href)
                download_options.append({
                    'text': element.get_text(strip=True),
                    'url': full_url,
                    'element': element.name,
                    'href': href
                })
        
        # Also check form actions that might lead to downloads
        for form in soup.find_all('form'):
            action = form.get('action', '')
            
            if any(keyword in action.lower() for keyword in ['download', 'document', 'file']):
                full_url = urljoin(base_url, action)
                
                # Look for submit buttons in the form
                for button in form.find_all(['button', 'input']):
                    button_text = button.get_text(strip=True) or button.get('value', '')
                    
                    if any(keyword in button_text.lower() for keyword in ['download', 'submit', 'get']):
                        download_options.append({
                            'text': f"Form: {button_text}",
                            'url': full_url,
                            'element': 'form',
                            'form': form
                        })
                        break
        
        return download_options
    
    def step5_download_with_captcha(self, download_option, tender_folder):
        """Step 5: Handle CAPTCHA and download ZIP file"""
        print(f"📋 STEP 5: Downloading ZIP with CAPTCHA")
        print(f"   🎯 Download option: {download_option['text']}")
        print(f"   🔗 URL: {download_option['url']}")
        
        try:
            # Access the download URL
            response = self.session.get(download_option['url'], timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"Download page failed: HTTP {response.status_code}")
            
            print(f"   ✅ Download page loaded: {len(response.text):,} chars")
            
            # Save download page
            download_page_file = tender_folder / "step5_download_page.html"
            with open(download_page_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Look for CAPTCHA and handle download
            result = self.handle_captcha_and_download(response.text, download_option['url'], tender_folder)
            
            return result
            
        except Exception as e:
            print(f"   ❌ Step 5 failed: {e}")
            return None
    
    def handle_captcha_and_download(self, page_content, page_url, tender_folder):
        """Handle CAPTCHA solving and ZIP download"""
        print("   🤖 Looking for CAPTCHA...")
        
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Look for CAPTCHA image
        captcha_img = None
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            
            if (any(keyword in src.lower() for keyword in ['captcha', 'verification', 'challenge']) or
                any(keyword in alt for keyword in ['captcha', 'verification', 'challenge'])):
                
                captcha_url = urljoin(page_url, src)
                print(f"      🎯 Found CAPTCHA image: {captcha_url}")
                
                # Download CAPTCHA image
                captcha_response = self.session.get(captcha_url, timeout=10)
                if captcha_response.status_code == 200:
                    captcha_img = captcha_response.content
                    
                    # Save CAPTCHA image
                    captcha_file = tender_folder / "captcha_image.png"
                    with open(captcha_file, 'wb') as f:
                        f.write(captcha_img)
                    
                    print(f"      💾 CAPTCHA image saved: {len(captcha_img)} bytes")
                break
        
        if captcha_img:
            # Solve CAPTCHA using 2Captcha
            captcha_solution = self.solve_captcha_2captcha(captcha_img)
            
            if captcha_solution:
                print(f"      ✅ CAPTCHA solved: '{captcha_solution}'")
                
                # Submit form with CAPTCHA solution
                zip_result = self.submit_captcha_form(soup, captcha_solution, page_url, tender_folder)
                
                if zip_result:
                    print(f"   🎉 ZIP download successful!")
                    return zip_result
                else:
                    print(f"   ❌ ZIP download failed")
            else:
                print(f"      ❌ CAPTCHA solving failed")
        else:
            print(f"      ⚠️  No CAPTCHA found - trying direct download")
            
            # Check if response is already a ZIP file
            content_type = self.session.head(page_url).headers.get('content-type', '').lower()
            if 'zip' in content_type:
                return self.save_zip_file(self.session.get(page_url).content, tender_folder)
        
        return None
    
    def solve_captcha_2captcha(self, captcha_image):
        """Solve CAPTCHA using 2Captcha API"""
        print("      🔄 Submitting CAPTCHA to 2Captcha...")
        
        try:
            # Step 1: Submit image
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
            
            # Step 2: Poll for solution
            for attempt in range(20):  # Max 20 attempts (100 seconds)
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
                    print(f"         ⏳ Waiting... (attempt {attempt + 1}/20)")
                    continue
                else:
                    raise Exception(f"Solving failed: {result_data.get('error_text')}")
            
            raise Exception("Timed out waiting for CAPTCHA solution")
            
        except Exception as e:
            print(f"         ❌ 2Captcha error: {e}")
            return None
    
    def submit_captcha_form(self, soup, captcha_solution, page_url, tender_folder):
        """Submit form with CAPTCHA solution to get ZIP"""
        print(f"      📤 Submitting form with CAPTCHA: {captcha_solution}")
        
        # Find form with CAPTCHA input
        for form in soup.find_all('form'):
            captcha_input = None
            
            for input_field in form.find_all('input'):
                input_name = input_field.get('name', '').lower()
                input_type = input_field.get('type', '').lower()
                
                if (any(keyword in input_name for keyword in ['captcha', 'verification', 'challenge']) or
                    (input_type == 'text' and not input_field.get('value'))):
                    captcha_input = input_field
                    break
            
            if captcha_input:
                # Prepare form data
                form_data = {}
                
                for input_field in form.find_all(['input', 'select']):
                    name = input_field.get('name')
                    if name:
                        if input_field == captcha_input:
                            form_data[name] = captcha_solution
                        else:
                            form_data[name] = input_field.get('value', '')
                
                # Submit form
                action = form.get('action', '')
                submit_url = urljoin(page_url, action) if action else page_url
                method = form.get('method', 'POST').upper()
                
                print(f"         🌐 Submitting to: {submit_url}")
                
                if method == 'POST':
                    response = self.session.post(submit_url, data=form_data, timeout=30)
                else:
                    response = self.session.get(submit_url, params=form_data, timeout=30)
                
                if response.status_code == 200:
                    # Check if we got a ZIP file
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if ('zip' in content_type or 
                        response.content.startswith(b'PK')):  # ZIP signature
                        
                        return self.save_zip_file(response.content, tender_folder)
                    else:
                        print(f"         ⚠️  Response not a ZIP: {content_type}")
                
                break
        
        return None
    
    def save_zip_file(self, zip_content, tender_folder):
        """Save and extract ZIP file"""
        print(f"         💾 Saving ZIP file: {len(zip_content):,} bytes")
        
        zip_path = tender_folder / "tender_documents.zip"
        
        with open(zip_path, 'wb') as f:
            f.write(zip_content)
        
        # Extract ZIP
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                file_list = zip_file.namelist()
                print(f"         📦 Extracting {len(file_list)} files...")
                
                for filename in file_list:
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
            'zip_path': str(zip_path),
            'zip_size': len(zip_content),
            'extracted_files': extracted_files
        }
    
    def download_tender_documents(self, tender_id, source_id):
        """Complete document download following exact navigation"""
        print(f"🚀 UTTARAKHAND EXACT NAVIGATION DOWNLOAD")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        print("   Following Rahul's exact navigation path...")
        print()
        
        result = {
            'tender_id': tender_id,
            'source_id': source_id,
            'source': 'UTTARAKHAND',
            'status': 'processing',
            'downloaded_files': []
        }
        
        try:
            # Create tender folder
            tender_folder = self.downloads_dir / f"UK_EXACT_{source_id}_{tender_id[:8]}"
            tender_folder.mkdir(exist_ok=True)
            
            # Execute the exact navigation path
            
            # Step 1: Main page navigation
            navigation_options = self.step1_access_main_navigation()
            if not navigation_options:
                raise Exception("Could not find main navigation")
            
            # Step 2: Get department list
            departments = self.step2_get_department_list(navigation_options)
            if not departments:
                raise Exception("Could not find departments")
            
            # Step 3: Access department tenders
            department_results = self.step3_access_department_tenders(departments, max_departments=2)
            if not department_results:
                raise Exception("Could not access department tender listings")
            
            # Step 4 & 5: Try each department's tenders
            for dept_result in department_results:
                print(f"\n🏢 Trying department: {dept_result['department']['name']}")
                
                for tender_link in dept_result['tender_links'][:2]:  # Try first 2 tenders
                    print(f"\n📋 Trying tender: {tender_link['title'][:50]}...")
                    
                    # Step 4: Access tender details
                    download_option = self.step4_access_tender_details(tender_link)
                    
                    if download_option:
                        # Step 5: Download with CAPTCHA
                        download_result = self.step5_download_with_captcha(download_option, tender_folder)
                        
                        if download_result and download_result.get('extracted_files'):
                            # Success!
                            result['downloaded_files'] = download_result['extracted_files']
                            result['zip_info'] = {
                                'zip_path': download_result['zip_path'],
                                'zip_size': download_result['zip_size']
                            }
                            result['status'] = 'completed'
                            result['folder_path'] = str(tender_folder)
                            
                            print(f"\n🎉 SUCCESS! Downloaded {len(result['downloaded_files'])} files")
                            return result
                        else:
                            print(f"   ⚠️  No download from this tender")
                    else:
                        print(f"   ⚠️  No download button found")
            
            result['status'] = 'no_documents'
            print(f"\n⚠️  No documents could be downloaded from any tender")
            
        except Exception as e:
            print(f"\n❌ Download failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result

def test_uttarakhand_exact_navigation():
    """Test the exact navigation implementation"""
    print("🚀 UTTARAKHAND EXACT NAVIGATION TEST")
    print("=" * 45)
    
    navigator = UttarakhandExactNavigator()
    
    # Test with sample tender
    test_tender_id = "490e3361-24ba-4837-a533-3ffede026294"
    test_source_id = "2026_UKJS_92588_1"
    
    result = navigator.download_tender_documents(test_tender_id, test_source_id)
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"   Status: {result['status']}")
    print(f"   Files: {len(result.get('downloaded_files', []))}")
    
    if result.get('downloaded_files'):
        total_size = sum(f['size'] for f in result['downloaded_files'])
        print(f"   Size: {total_size/(1024*1024):.1f} MB")
        print(f"   🎉 SUCCESS: Exact navigation working!")
        
        for doc in result['downloaded_files']:
            print(f"      📄 {doc['filename']} ({doc['size']:,} bytes)")
        
        return True
    else:
        print(f"   🔧 Needs refinement: {result.get('error', 'Unknown')}")
        return False

if __name__ == "__main__":
    success = test_uttarakhand_exact_navigation()
    
    if success:
        print(f"\n✅ EXACT NAVIGATION: SUCCESS!")
        print(f"Ready for production integration!")
    else:
        print(f"\n🔧 Navigation path needs adjustment")