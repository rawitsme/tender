#!/usr/bin/env python3
"""
Remove the "Get Detailed Info" section from TenderDetail.jsx
"""

import re

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🔧 REMOVING 'Get Detailed Info' SECTION")
print("=" * 40)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📁 Original file size: {len(content):,} characters")
    
    # Find the start of the Detailed Info Section
    start_marker = '      {/* Detailed Info Section */}'
    start_pos = content.find(start_marker)
    
    if start_pos == -1:
        print("❌ 'Detailed Info Section' comment not found")
        exit(1)
    
    print(f"📍 Found section at position: {start_pos}")
    
    # Find the closing div by counting opening and closing divs
    search_start = start_pos + len(start_marker)
    div_count = 0
    pos = search_start
    section_start_found = False
    
    while pos < len(content):
        if content[pos:pos+4] == '<div':
            div_count += 1
            if not section_start_found:
                section_start_found = True
        elif content[pos:pos+6] == '</div>':
            div_count -= 1
            if section_start_found and div_count == 0:
                # Found the closing div
                end_pos = pos + 6
                break
        pos += 1
    else:
        print("❌ Could not find closing div")
        exit(1)
    
    print(f"📍 Section ends at position: {end_pos}")
    
    # Extract the section to remove
    section_to_remove = content[start_pos:end_pos]
    print(f"📏 Section size: {len(section_to_remove):,} characters")
    
    # Verify this is the right section
    if 'Get Detailed Info' in section_to_remove and 'handleGetDetails' in section_to_remove:
        print("✅ Verified: Found correct section with 'Get Detailed Info' button")
    else:
        print("❌ Warning: Section doesn't contain expected content")
        print("First 200 chars of section:")
        print(section_to_remove[:200])
        exit(1)
    
    # Remove the section
    new_content = content[:start_pos] + content[end_pos:]
    
    print(f"📁 New file size: {len(new_content):,} characters")
    print(f"📉 Removed: {len(content) - len(new_content):,} characters")
    
    # Write the modified content
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print("✅ Successfully removed 'Get Detailed Info' section!")
    print("🧹 Now only 'Real Tender Documents' section remains")
    
except Exception as e:
    print(f"❌ Error: {e}")