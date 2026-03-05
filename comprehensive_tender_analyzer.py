#!/usr/bin/env python3
"""
Comprehensive Tender Document Analyzer
Downloads ZIP files, extracts PDFs, and summarizes key tender details:
- Last Date/Closing Date
- EMD (Earnest Money Deposit) 
- JV Allowed (Joint Venture)
- Eligibility Criteria
- Contract Value
- Technical Specifications
"""

import requests
import zipfile
import PyPDF2
import pdfplumber
from pathlib import Path
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
import base64
import time

class TenderDocumentAnalyzer:
    """Comprehensive analyzer for tender documents"""
    
    def __init__(self, downloads_dir="storage/documents/analyzed_tenders"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        
        # 2Captcha for Uttarakhand downloads
        self.captcha_api_key = "9a09f9a33a7e9f216792c77113f31c11"
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def analyze_existing_downloads(self):
        """Analyze all existing downloaded files"""
        print("🔍 ANALYZING EXISTING DOWNLOADED TENDER DOCUMENTS")
        print("=" * 55)
        
        results = []
        
        # Check GEM PDFs
        gem_dirs = list(Path("storage/documents/real_pdfs").glob("GEM_*"))
        
        for gem_dir in gem_dirs[:3]:  # Analyze first 3 GEM tenders
            print(f"\n📋 Analyzing GEM tender: {gem_dir.name}")
            
            # Look for PDF files
            pdf_files = list(gem_dir.glob("*.pdf")) + list(gem_dir.glob("*.PDF"))
            
            if pdf_files:
                for pdf_file in pdf_files:
                    print(f"   📄 Found PDF: {pdf_file.name} ({pdf_file.stat().st_size:,} bytes)")
                    
                    analysis = self.analyze_pdf_document(pdf_file)
                    
                    if analysis:
                        analysis['source'] = 'GEM'
                        analysis['tender_folder'] = str(gem_dir)
                        analysis['pdf_file'] = str(pdf_file)
                        results.append(analysis)
                        
                        # Print summary
                        self.print_tender_summary(analysis, gem_dir.name)
            else:
                print(f"   ⚠️  No PDF files found")
        
        # Check other sources
        other_dirs = []
        for pattern in ["uttarakhand_*", "CPPP_*", "STATE_*"]:
            other_dirs.extend(list(Path("storage/documents").glob(pattern)))
        
        for other_dir in other_dirs[:2]:  # Check first 2
            if other_dir.is_dir():
                print(f"\n📋 Checking {other_dir.name}...")
                
                pdf_files = list(other_dir.rglob("*.pdf")) + list(other_dir.rglob("*.PDF"))
                zip_files = list(other_dir.rglob("*.zip"))
                
                if zip_files:
                    for zip_file in zip_files:
                        print(f"   📦 Found ZIP: {zip_file.name}")
                        extracted_pdfs = self.extract_and_analyze_zip(zip_file)
                        results.extend(extracted_pdfs)
                
                elif pdf_files:
                    for pdf_file in pdf_files:
                        analysis = self.analyze_pdf_document(pdf_file)
                        if analysis:
                            results.append(analysis)
        
        return results
    
    def download_and_analyze_zip(self, zip_url, captcha_solver=None):
        """Download ZIP file (with CAPTCHA if needed) and analyze contents"""
        print(f"🔥 DOWNLOADING AND ANALYZING ZIP FILE")
        print(f"   🔗 URL: {zip_url}")
        
        tender_folder = self.downloads_dir / f"zip_analysis_{int(time.time())}"
        tender_folder.mkdir(exist_ok=True)
        
        try:
            # Download ZIP (handle CAPTCHA if needed)
            zip_content = self.download_zip_with_captcha(zip_url, tender_folder, captcha_solver)
            
            if zip_content:
                # Save ZIP file
                zip_path = tender_folder / "tender_documents.zip"
                with open(zip_path, 'wb') as f:
                    f.write(zip_content)
                
                print(f"   📦 ZIP downloaded: {len(zip_content):,} bytes")
                
                # Extract and analyze
                return self.extract_and_analyze_zip(zip_path)
            else:
                print(f"   ❌ Failed to download ZIP")
                return []
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def extract_and_analyze_zip(self, zip_path):
        """Extract ZIP file and analyze all PDF documents"""
        print(f"   📦 Extracting ZIP: {zip_path}")
        
        results = []
        extract_dir = zip_path.parent / f"extracted_{zip_path.stem}"
        extract_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(extract_dir)
                
                # Find all PDF files
                pdf_files = list(extract_dir.rglob("*.pdf")) + list(extract_dir.rglob("*.PDF"))
                
                print(f"   📄 Found {len(pdf_files)} PDF files")
                
                for pdf_file in pdf_files:
                    print(f"      📋 Analyzing: {pdf_file.name}")
                    
                    analysis = self.analyze_pdf_document(pdf_file)
                    
                    if analysis:
                        analysis['zip_source'] = str(zip_path)
                        analysis['extracted_from'] = str(pdf_file)
                        results.append(analysis)
                        
                        # Print individual summary
                        self.print_tender_summary(analysis, pdf_file.name)
        
        except Exception as e:
            print(f"   ❌ ZIP extraction failed: {e}")
        
        return results
    
    def analyze_pdf_document(self, pdf_path):
        """Analyze PDF document and extract key tender details"""
        try:
            # Read PDF text using both PyPDF2 and pdfplumber for best results
            text_content = self.extract_pdf_text(pdf_path)
            
            if not text_content or len(text_content.strip()) < 100:
                print(f"      ⚠️  Could not extract meaningful text from PDF")
                return None
            
            print(f"      ✅ Extracted {len(text_content):,} characters")
            
            # Analyze content for key details
            analysis = {
                'pdf_file': pdf_path.name,
                'content_length': len(text_content),
                'analysis_date': datetime.now().isoformat(),
                'extracted_details': self.extract_tender_details(text_content)
            }
            
            return analysis
            
        except Exception as e:
            print(f"      ❌ PDF analysis failed: {e}")
            return None
    
    def extract_pdf_text(self, pdf_path):
        """Extract text from PDF using multiple methods"""
        text_content = ""
        
        # Method 1: pdfplumber (better for tables and complex layouts)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:10]:  # First 10 pages
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\\n"
        except:
            pass
        
        # Method 2: PyPDF2 (backup method)
        if len(text_content.strip()) < 100:
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    for page_num in range(min(10, len(pdf_reader.pages))):
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\\n"
            except:
                pass
        
        return text_content
    
    def extract_tender_details(self, text_content):
        """Extract key tender details from text content"""
        details = {
            'last_date': self.extract_last_date(text_content),
            'emd_amount': self.extract_emd_amount(text_content), 
            'jv_allowed': self.extract_jv_policy(text_content),
            'eligibility_criteria': self.extract_eligibility_criteria(text_content),
            'contract_value': self.extract_contract_value(text_content),
            'technical_specifications': self.extract_technical_specs(text_content),
            'tender_type': self.extract_tender_type(text_content),
            'work_description': self.extract_work_description(text_content)
        }
        
        return details
    
    def extract_last_date(self, text):
        """Extract last date/closing date"""
        patterns = [
            r'(?:last date|closing date|bid submission|due date).*?(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(?:last date|closing date|bid submission|due date).*?(\d{1,2}\s+\w+\s+\d{4})',
            r'submission.*?before.*?(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'before.*?(\d{1,2}:\d{2}.*?\d{1,2}[/-]\d{1,2}[/-]\d{4})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                return matches[0]
        
        return "Not found"
    
    def extract_emd_amount(self, text):
        """Extract Earnest Money Deposit amount"""
        patterns = [
            r'(?:EMD|earnest money|earnest money deposit).*?(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)',
            r'(?:EMD|earnest money).*?([\d,]+(?:\.\d{2})?)\s*(?:lakhs?|crores?)',
            r'security deposit.*?(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                return f"₹ {matches[0]}"
        
        return "Not specified"
    
    def extract_jv_policy(self, text):
        """Extract Joint Venture policy"""
        jv_indicators = [
            ('joint venture.*?(?:allowed|permitted)', 'Allowed'),
            ('joint venture.*?(?:not allowed|not permitted|prohibited)', 'Not Allowed'), 
            ('JV.*?(?:allowed|permitted)', 'Allowed'),
            ('JV.*?(?:not allowed|not permitted|prohibited)', 'Not Allowed'),
            ('consortium.*?(?:allowed|permitted)', 'Allowed'),
            ('consortium.*?(?:not allowed|not permitted)', 'Not Allowed')
        ]
        
        text_lower = text.lower()
        for pattern, result in jv_indicators:
            if re.search(pattern, text_lower):
                return result
        
        return "Not specified"
    
    def extract_eligibility_criteria(self, text):
        """Extract eligibility criteria"""
        criteria_patterns = [
            r'(?:eligibility|qualification).*?criteria.*?(?:\n.*?){0,10}',
            r'(?:minimum|required).*?(?:experience|turnover|qualification).*?(?:\n.*?){0,5}',
            r'bidder.*?(?:should|must|shall).*?(?:\n.*?){0,5}'
        ]
        
        criteria = []
        for pattern in criteria_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            criteria.extend([match.strip()[:200] for match in matches[:2]])  # Limit length
        
        if criteria:
            return '; '.join(criteria)
        else:
            return "Standard eligibility criteria apply"
    
    def extract_contract_value(self, text):
        """Extract contract/tender value"""
        patterns = [
            r'(?:contract value|tender value|estimated cost).*?(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)\s*(?:lakhs?|crores?)',
            r'(?:contract value|tender value|estimated cost).*?(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)',
            r'(?:total value|project cost).*?(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                return f"₹ {matches[0]}"
        
        return "Not specified"
    
    def extract_technical_specs(self, text):
        """Extract technical specifications"""
        spec_patterns = [
            r'(?:technical specification|technical requirement|scope of work).*?(?:\n.*?){0,5}',
            r'(?:material|equipment|machinery).*?specification.*?(?:\n.*?){0,3}'
        ]
        
        specs = []
        for pattern in spec_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            specs.extend([match.strip()[:300] for match in matches[:2]])
        
        if specs:
            return '; '.join(specs)
        else:
            return "Refer to tender document"
    
    def extract_tender_type(self, text):
        """Extract tender type/category"""
        type_patterns = [
            ('construction', 'Construction'),
            ('supply', 'Supply'), 
            ('service', 'Service'),
            ('maintenance', 'Maintenance'),
            ('consultancy', 'Consultancy'),
            ('works?', 'Works'),
            ('goods', 'Goods')
        ]
        
        text_lower = text.lower()
        for pattern, tender_type in type_patterns:
            if re.search(pattern, text_lower):
                return tender_type
        
        return "General"
    
    def extract_work_description(self, text):
        """Extract work description summary"""
        # Look for descriptive content in first 1000 chars
        first_part = text[:1000]
        
        # Remove common headers/footers
        cleaned = re.sub(r'(?:page \d+|government of|tender document|bid document)', '', first_part, flags=re.IGNORECASE)
        
        # Find sentences with key work-related words
        work_sentences = []
        sentences = re.split(r'[.!?]+', cleaned)
        
        for sentence in sentences[:10]:
            sentence = sentence.strip()
            if (len(sentence) > 30 and 
                any(word in sentence.lower() for word in ['work', 'supply', 'construction', 'service', 'maintenance'])):
                work_sentences.append(sentence[:200])
        
        if work_sentences:
            return '; '.join(work_sentences[:2])
        else:
            return "Refer to tender document"
    
    def print_tender_summary(self, analysis, tender_name):
        """Print formatted tender summary"""
        print(f"\n📋 TENDER SUMMARY: {tender_name}")
        print("=" * 60)
        
        details = analysis['extracted_details']
        
        print(f"📅 **Last Date:** {details['last_date']}")
        print(f"💰 **EMD Amount:** {details['emd_amount']}")
        print(f"🤝 **JV Allowed:** {details['jv_allowed']}")
        print(f"📊 **Contract Value:** {details['contract_value']}")
        print(f"📋 **Tender Type:** {details['tender_type']}")
        
        print(f"\\n✅ **Eligibility Criteria:**")
        print(f"   {details['eligibility_criteria']}")
        
        print(f"\\n🔧 **Technical Specifications:**")  
        print(f"   {details['technical_specifications']}")
        
        print(f"\\n📄 **Work Description:**")
        print(f"   {details['work_description']}")
        
        print(f"\\n📊 **Analysis Info:**")
        print(f"   Content Length: {analysis['content_length']:,} characters")
        print(f"   PDF File: {analysis['pdf_file']}")
    
    def download_zip_with_captcha(self, zip_url, tender_folder, captcha_solver=None):
        """Download ZIP file handling CAPTCHA if needed"""
        try:
            response = self.session.get(zip_url, timeout=30)
            
            if response.status_code == 200:
                # Check if we got a ZIP file directly
                if response.content.startswith(b'PK') or 'zip' in response.headers.get('content-type', ''):
                    return response.content
                
                # If HTML page, might need CAPTCHA solving
                if 'text/html' in response.headers.get('content-type', ''):
                    if captcha_solver:
                        return captcha_solver(response.text, zip_url, tender_folder)
                    else:
                        print(f"   🤖 CAPTCHA detected but no solver provided")
            
            return None
            
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return None
    
    def run_comprehensive_analysis(self):
        """Run comprehensive analysis of all available documents"""
        print("🚀 COMPREHENSIVE TENDER DOCUMENT ANALYSIS")
        print("=" * 50)
        
        # Analyze existing downloads
        results = self.analyze_existing_downloads()
        
        print(f"\\n📊 ANALYSIS COMPLETE")
        print(f"   Total documents analyzed: {len(results)}")
        
        if results:
            print(f"\\n🎯 SUMMARY OF ALL ANALYZED TENDERS:")
            print("=" * 40)
            
            for i, result in enumerate(results, 1):
                details = result['extracted_details']
                print(f"{i}. {result.get('pdf_file', 'Unknown')}:")
                print(f"   📅 Last Date: {details['last_date']}")
                print(f"   💰 EMD: {details['emd_amount']}")
                print(f"   🤝 JV: {details['jv_allowed']}")
                print(f"   📊 Value: {details['contract_value']}")
                print()
        
        return results

def main():
    """Main function to run comprehensive analysis"""
    analyzer = TenderDocumentAnalyzer()
    
    # Run analysis of existing documents
    results = analyzer.run_comprehensive_analysis()
    
    if not results:
        print("\\n💡 No documents found to analyze.")
        print("To analyze new documents:")
        print("1. Provide ZIP file URL for download")
        print("2. Place PDF files in storage/documents/ folders") 
        print("3. Use the GEM portal integration (already working)")

if __name__ == "__main__":
    main()