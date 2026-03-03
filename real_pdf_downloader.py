#!/usr/bin/env python3
"""
REAL PDF DOWNLOADER - Download actual tender documents
This downloads the actual PDF files (NIT, BOQ, Technical Specs) that bidders need
"""

import requests
import asyncio
import aiohttp
import aiofiles
import os
import sys
import json
from pathlib import Path
from urllib.parse import urljoin
import re
from datetime import datetime

# Database connection
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Float, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

# Define minimal Tender model
Base = declarative_base()

class Tender(Base):
    __tablename__ = 'tenders'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String)
    source = Column(String)
    source_id = Column(String)
    source_url = Column(String)

class RealPDFDownloader:
    """Downloads actual tender PDFs from government portals"""
    
    def __init__(self, base_dir="storage/documents/real_pdfs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session = None
        
    async def create_session(self):
        """Create HTTP session with proper headers"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
                connector=aiohttp.TCPConnector(ssl=False)
            )
        return self.session
    
    async def download_gem_pdfs(self, tender_id: str, source_id: str) -> dict:
        """Download real PDFs from GEM portal"""
        print(f"🔥 DOWNLOADING REAL PDFs FROM GEM")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        result = {
            "tender_id": tender_id,
            "source_id": source_id,
            "source": "GEM",
            "downloaded_files": [],
            "total_size": 0,
            "status": "processing"
        }
        
        session = await self.create_session()
        
        try:
            # Create folder for this tender
            tender_folder = self.base_dir / f"GEM_{source_id}_{tender_id[:8]}"
            tender_folder.mkdir(exist_ok=True)
            
            # Try multiple GEM access patterns
            gem_urls = [
                f"https://bidplus.gem.gov.in/showbidDocument/{source_id}",
                f"https://gem.gov.in/showbidDocument/{source_id}",
                f"https://bidplus.gem.gov.in/tender/{source_id}",
            ]
            
            for i, url in enumerate(gem_urls, 1):
                try:
                    print(f"   🌐 Trying GEM URL {i}: {url}")
                    
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            print(f"      ✅ Got content: {len(content):,} characters")
                            
                            # Save the portal page
                            page_file = tender_folder / f"gem_portal_page_{i}.html"
                            async with aiofiles.open(page_file, 'w', encoding='utf-8') as f:
                                await f.write(content)
                            
                            # Look for PDF links
                            pdf_patterns = [
                                r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
                                r'href=["\']([^"\']*\.PDF[^"\']*)["\']',
                                r'(https://[^\\s"\'<>]*\.pdf)',
                                r'(https://[^\\s"\'<>]*\.PDF)',
                                r'src=["\']([^"\']*\.pdf[^"\']*)["\']'
                            ]
                            
                            found_pdfs = set()
                            for pattern in pdf_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    # Clean up the URL
                                    pdf_url = match.strip()
                                    if pdf_url.startswith('/'):
                                        pdf_url = urljoin(url, pdf_url)
                                    if pdf_url.startswith('http') and pdf_url not in found_pdfs:
                                        found_pdfs.add(pdf_url)
                            
                            print(f"      📄 Found {len(found_pdfs)} PDF URLs:")
                            for j, pdf_url in enumerate(list(found_pdfs)[:10], 1):
                                print(f"         {j}. {pdf_url}")
                            
                            # Download each PDF
                            for j, pdf_url in enumerate(list(found_pdfs)[:10], 1):
                                try:
                                    print(f"      ⬇️  Downloading PDF {j}...")
                                    
                                    async with session.get(pdf_url) as pdf_resp:
                                        if pdf_resp.status == 200:
                                            pdf_content = await pdf_resp.read()
                                            
                                            # Check if it's actually a PDF
                                            if pdf_content.startswith(b'%PDF') and len(pdf_content) > 1000:
                                                # Generate meaningful filename
                                                filename = f"GEM_{source_id}_Document_{j}.pdf"
                                                
                                                # Try to get a better name from URL
                                                if '/' in pdf_url:
                                                    url_name = pdf_url.split('/')[-1]
                                                    if '.pdf' in url_name.lower():
                                                        filename = f"GEM_{source_id}_{url_name}"
                                                
                                                pdf_file = tender_folder / filename
                                                async with aiofiles.open(pdf_file, 'wb') as f:
                                                    await f.write(pdf_content)
                                                
                                                file_info = {
                                                    "filename": filename,
                                                    "size": len(pdf_content),
                                                    "url": pdf_url,
                                                    "type": "PDF",
                                                    "downloaded_at": datetime.now().isoformat()
                                                }
                                                
                                                result["downloaded_files"].append(file_info)
                                                result["total_size"] += len(pdf_content)
                                                
                                                print(f"         ✅ Downloaded: {filename} ({len(pdf_content):,} bytes)")
                                            else:
                                                print(f"         ❌ Not a valid PDF: {len(pdf_content)} bytes")
                                        else:
                                            print(f"         ❌ HTTP {pdf_resp.status}")
                                
                                except Exception as e:
                                    print(f"         ❌ Download failed: {e}")
                            
                            # If we found PDFs, we're done
                            if result["downloaded_files"]:
                                break
                                
                        else:
                            print(f"      ❌ HTTP {resp.status}")
                
                except Exception as e:
                    print(f"      ❌ URL {i} failed: {e}")
                    continue
            
            # Save metadata
            metadata = {
                "tender_info": result,
                "download_summary": {
                    "total_files": len(result["downloaded_files"]),
                    "total_size_mb": result["total_size"] / (1024 * 1024),
                    "files": result["downloaded_files"]
                },
                "timestamp": datetime.now().isoformat()
            }
            
            metadata_file = tender_folder / "download_metadata.json"
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            result["status"] = "completed" if result["downloaded_files"] else "no_pdfs_found"
            result["folder_path"] = str(tender_folder)
            
        except Exception as e:
            print(f"   ❌ GEM download failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def download_cppp_pdfs(self, tender_id: str, source_id: str) -> dict:
        """Download real PDFs from CPPP portal"""
        print(f"🔥 DOWNLOADING REAL PDFs FROM CPPP")
        print(f"   Tender ID: {tender_id}")
        print(f"   Source ID: {source_id}")
        
        result = {
            "tender_id": tender_id,
            "source_id": source_id,
            "source": "CPPP",
            "downloaded_files": [],
            "total_size": 0,
            "status": "processing"
        }
        
        session = await self.create_session()
        
        try:
            # Create folder for this tender
            tender_folder = self.base_dir / f"CPPP_{source_id}_{tender_id[:8]}"
            tender_folder.mkdir(exist_ok=True)
            
            # CPPP URLs
            cppp_urls = [
                f"https://eprocure.gov.in/cppp/tenderdetails/{source_id}",
                f"https://eprocure.gov.in/cppp/viewtender/{source_id}",
                f"https://cppp.gov.in/tender/{source_id}",
            ]
            
            for i, url in enumerate(cppp_urls, 1):
                try:
                    print(f"   🌐 Trying CPPP URL {i}: {url}")
                    
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            print(f"      ✅ Got content: {len(content):,} characters")
                            
                            # Save the portal page
                            page_file = tender_folder / f"cppp_portal_page_{i}.html"
                            async with aiofiles.open(page_file, 'w', encoding='utf-8') as f:
                                await f.write(content)
                            
                            # CPPP-specific PDF patterns
                            pdf_patterns = [
                                r'downloadDocument\([\'"]([^\'"]*)[\'"]',
                                r'viewDocument\([\'"]([^\'"]*)[\'"]',
                                r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
                                r'download\.php\?([^"\']*)',
                            ]
                            
                            found_docs = set()
                            for pattern in pdf_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                found_docs.update(matches)
                            
                            if found_docs:
                                print(f"      📄 Found {len(found_docs)} document references")
                                # TODO: Implement CPPP-specific download logic
                                
                        else:
                            print(f"      ❌ HTTP {resp.status}")
                
                except Exception as e:
                    print(f"      ❌ URL {i} failed: {e}")
                    continue
            
            result["status"] = "completed" if result["downloaded_files"] else "no_pdfs_found"
            result["folder_path"] = str(tender_folder)
            
        except Exception as e:
            print(f"   ❌ CPPP download failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()

async def download_real_pdfs_for_tender(tender_id: str):
    """Download real PDFs for a specific tender"""
    
    print(f"🚀 REAL PDF DOWNLOAD FOR TENDER: {tender_id}")
    print("=" * 60)
    
    # Get tender info from database
    DATABASE_URL = "postgresql://tender:tender_dev_2026@localhost:5432/tender_portal"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        
        if not tender:
            print(f"❌ Tender {tender_id} not found in database")
            return None
        
        print(f"📋 Found tender:")
        print(f"   Title: {tender.title}")
        print(f"   Source: {tender.source}")
        print(f"   Source ID: {tender.source_id}")
        print()
        
        downloader = RealPDFDownloader()
        
        try:
            if tender.source.upper() == 'GEM':
                result = await downloader.download_gem_pdfs(tender_id, tender.source_id)
            elif tender.source.upper() == 'CPPP':
                result = await downloader.download_cppp_pdfs(tender_id, tender.source_id)
            else:
                print(f"⚠️  Source {tender.source} not yet supported for PDF download")
                return None
            
            # Print results
            if result["downloaded_files"]:
                print(f"\n🎉 SUCCESS! Downloaded {len(result['downloaded_files'])} PDF files:")
                total_size = sum(f["size"] for f in result["downloaded_files"])
                
                for file_info in result["downloaded_files"]:
                    size_mb = file_info["size"] / (1024 * 1024)
                    print(f"   📄 {file_info['filename']} ({size_mb:.1f} MB)")
                
                print(f"\n📊 Summary:")
                print(f"   Files: {len(result['downloaded_files'])}")
                print(f"   Total Size: {total_size/(1024*1024):.1f} MB")
                print(f"   Location: {result['folder_path']}")
                
                print(f"\n✅ THESE ARE THE ACTUAL TENDER DOCUMENTS!")
                print(f"Users can now download the real PDFs they need for bidding.")
                
                return result
            else:
                print(f"\n⚠️  No PDF files found for this tender")
                print(f"Status: {result['status']}")
                if 'error' in result:
                    print(f"Error: {result['error']}")
                return result
                
        finally:
            await downloader.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python real_pdf_downloader.py <tender_id>")
        print("Example: python real_pdf_downloader.py feef799d-a10e-4d23-90b0-69ff6f73da61")
        sys.exit(1)
    
    tender_id = sys.argv[1]
    result = asyncio.run(download_real_pdfs_for_tender(tender_id))
    
    if result and result["downloaded_files"]:
        print(f"\n🎯 READY FOR USERS!")
        print(f"Add a 'Download Real PDFs' button that points to: {result['folder_path']}")
    else:
        print(f"\n🔧 NEEDS WORK: Authentication or portal-specific handling required")