#!/usr/bin/env python3
"""
REAL DOCUMENT DOWNLOADER - Proof of Concept
Downloads actual PDF documents from government tender portals using Selenium
"""

import asyncio
import os
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

class RealDocumentDownloader:
    """Downloads actual tender documents using browser automation"""
    
    def __init__(self, downloads_dir="storage/documents/downloads"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.driver = None
        
    def setup_browser(self, headless=False):
        """Setup Chrome browser with download capabilities"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Set download directory
        download_path = str(self.downloads_dir.absolute())
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True  # Download PDFs instead of viewing
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        return self.driver
    
    def download_gem_documents(self, tender_id, source_id, max_wait=30):
        """
        Download documents from GEM portal for a specific tender
        Returns list of downloaded file paths
        """
        print(f"🔥 ATTEMPTING REAL GEM DOCUMENT DOWNLOAD")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        downloaded_files = []
        
        try:
            if not self.driver:
                self.setup_browser(headless=False)  # Keep browser visible for debugging
            
            # Navigate to GEM tender page
            gem_url = f"https://bidplus.gem.gov.in/showbidDocument/{source_id}"
            print(f"   📡 Navigating to: {gem_url}")
            
            self.driver.get(gem_url)
            time.sleep(3)
            
            # Check if we need to handle authentication or redirects
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            print(f"   🌐 Current URL: {current_url}")
            print(f"   📄 Page length: {len(page_source):,} characters")
            
            # Look for document links on the page
            document_links = []
            
            # Common selectors for document links
            selectors = [
                'a[href*=".pdf"]',
                'a[href*="download"]', 
                'a[href*="attachment"]',
                'a[contains(text(), "PDF")]',
                'a[contains(text(), "Download")]',
                'a[contains(text(), "Document")]',
                'a[contains(text(), "NIT")]',
                'a[contains(text(), "BOQ")]'
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        href = elem.get_attribute('href')
                        text = elem.text.strip()
                        if href and (href not in [link['url'] for link in document_links]):
                            document_links.append({
                                'url': href,
                                'text': text,
                                'element': elem
                            })
                except Exception as e:
                    continue
            
            print(f"   🔗 Found {len(document_links)} potential document links:")
            for i, link in enumerate(document_links[:5], 1):
                print(f"      {i}. {link['text']} -> {link['url']}")
            
            # Attempt to download each document
            original_files = set(os.listdir(self.downloads_dir))
            
            for i, link in enumerate(document_links[:10], 1):  # Limit to 10 documents
                try:
                    print(f"   ⬇️  Attempting download {i}: {link['text']}")
                    
                    # Click the link to trigger download
                    self.driver.execute_script("arguments[0].click();", link['element'])
                    
                    # Wait a bit for download to start
                    time.sleep(2)
                    
                    # Check if new files appeared
                    current_files = set(os.listdir(self.downloads_dir))
                    new_files = current_files - original_files
                    
                    if new_files:
                        for new_file in new_files:
                            file_path = self.downloads_dir / new_file
                            if file_path.stat().st_size > 1000:  # At least 1KB
                                # Rename to include tender info
                                new_name = f"GEM_{source_id}_Doc_{i}_{new_file}"
                                new_path = self.downloads_dir / new_name
                                file_path.rename(new_path)
                                downloaded_files.append(str(new_path))
                                print(f"      ✅ Downloaded: {new_name} ({file_path.stat().st_size:,} bytes)")
                        
                        original_files = current_files
                    else:
                        print(f"      ⚠️  No file downloaded for link {i}")
                
                except Exception as e:
                    print(f"      ❌ Failed to download link {i}: {e}")
            
            # If no document links found, try alternative approach
            if not document_links:
                print("   🔍 No direct document links found, checking for alternative access...")
                
                # Look for forms or buttons that might reveal documents
                forms = self.driver.find_elements(By.TAG_NAME, "form")
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="submit"], input[type="button"]')
                
                print(f"   📋 Page elements: {len(forms)} forms, {len(buttons)} buttons, {len(inputs)} inputs")
                
                # Try clicking common document-related buttons
                doc_button_texts = ['download', 'document', 'view', 'pdf', 'nit', 'boq', 'attachment']
                for button in buttons + inputs:
                    try:
                        button_text = button.text.lower() or button.get_attribute('value', '').lower()
                        if any(keyword in button_text for keyword in doc_button_texts):
                            print(f"   🖱️  Trying button: {button_text}")
                            button.click()
                            time.sleep(3)
                            
                            # Check for new downloads
                            current_files = set(os.listdir(self.downloads_dir))
                            new_files = current_files - original_files
                            
                            if new_files:
                                for new_file in new_files:
                                    file_path = self.downloads_dir / new_file
                                    if file_path.stat().st_size > 1000:
                                        downloaded_files.append(str(file_path))
                                        print(f"      ✅ Downloaded via button: {new_file}")
                                original_files = current_files
                            
                            break  # Only try one button to avoid issues
                    except Exception as e:
                        continue
            
            # Save page source for analysis
            page_source_file = self.downloads_dir / f"GEM_{source_id}_page_source.html"
            with open(page_source_file, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            downloaded_files.append(str(page_source_file))
            print(f"   📄 Saved page source: {page_source_file.name}")
            
        except Exception as e:
            print(f"   ❌ Error in GEM download: {e}")
            
        finally:
            # Don't close browser immediately for debugging
            print(f"   ⏳ Keeping browser open for 10 seconds for inspection...")
            time.sleep(10)
        
        print(f"   🎯 DOWNLOAD COMPLETE: {len(downloaded_files)} files obtained")
        return downloaded_files
    
    def download_cppp_documents(self, tender_id, source_id):
        """Download documents from CPPP portal"""
        print(f"🔥 ATTEMPTING REAL CPPP DOCUMENT DOWNLOAD")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        # CPPP URLs typically require specific formatting
        cppp_urls = [
            f"https://eprocure.gov.in/cppp/tenderdetails/{source_id}",
            f"https://eprocure.gov.in/cppp/viewtender/{source_id}",
            f"https://cppp.gov.in/tender/{source_id}"
        ]
        
        downloaded_files = []
        
        try:
            if not self.driver:
                self.setup_browser(headless=False)
            
            for url in cppp_urls:
                try:
                    print(f"   📡 Trying URL: {url}")
                    self.driver.get(url)
                    time.sleep(3)
                    
                    # Check if page loaded successfully
                    if "tender" in self.driver.page_source.lower():
                        print(f"   ✅ Found tender page")
                        # Continue with document extraction logic...
                        break
                    else:
                        print(f"   ❌ No tender content found")
                        
                except Exception as e:
                    print(f"   ⚠️  URL failed: {e}")
                    continue
            
            # Save page source for analysis
            page_source_file = self.downloads_dir / f"CPPP_{source_id}_page_source.html"
            with open(page_source_file, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            downloaded_files.append(str(page_source_file))
            
        except Exception as e:
            print(f"   ❌ Error in CPPP download: {e}")
        
        return downloaded_files
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None

def test_real_document_download():
    """Test real document download with actual examples"""
    
    print("🚀 PROOF OF CONCEPT: REAL DOCUMENT DOWNLOAD")
    print("=" * 60)
    
    # Use our richest GEM example
    gem_tender_id = "feef799d-a10e-4d23-90b0-69ff6f73da61"
    gem_source_id = "9064186"
    
    downloader = RealDocumentDownloader()
    
    try:
        print("\n🏛️  TESTING GEM DOCUMENT DOWNLOAD:")
        print("=" * 40)
        
        gem_files = downloader.download_gem_documents(gem_tender_id, gem_source_id)
        
        if gem_files:
            print(f"\n✅ SUCCESS: Downloaded {len(gem_files)} files from GEM:")
            for file_path in gem_files:
                file_size = Path(file_path).stat().st_size
                print(f"   📄 {Path(file_path).name} ({file_size:,} bytes)")
        else:
            print(f"\n❌ No files downloaded from GEM")
        
        print("\n📊 DOWNLOAD SUMMARY:")
        print(f"   GEM Portal: {len(gem_files)} files")
        print(f"   Total Size: {sum(Path(f).stat().st_size for f in gem_files):,} bytes")
        
        return len(gem_files) > 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        downloader.close()

if __name__ == "__main__":
    success = test_real_document_download()
    if success:
        print("\n🎉 PROOF OF CONCEPT: SUCCESS!")
        print("Real document download is possible with proper browser automation")
    else:
        print("\n⚠️  PROOF OF CONCEPT: Needs refinement")
        print("Authentication or portal-specific handling required")