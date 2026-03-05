#!/usr/bin/env python3
"""
Surgical removal of ONLY the Get Detailed Info functionality
from the restored backup file
"""

import re

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🎯 SURGICAL REMOVAL OF GET DETAILED INFO")
print("=" * 40)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📁 Original file size: {len(content):,} characters")
    
    # Step 1: Remove the entire GetMoreDetailsButton component (everything after line 677)
    print("🗑️  Step 1: Removing GetMoreDetailsButton component...")
    
    # Find the comment that starts the component
    component_start = content.find('// Get More Details Button Component')
    if component_start != -1:
        # Remove everything after this point until "export default TenderDetail"
        export_pos = content.find('export default TenderDetail')
        if export_pos != -1:
            content = content[:component_start] + '\n' + content[export_pos:]
            print("   ✅ Removed GetMoreDetailsButton component")
        else:
            print("   ❌ Could not find export statement")
    else:
        print("   ❌ Could not find GetMoreDetailsButton component start")
    
    # Step 2: Remove the Detailed Info Section (the main offending section)
    print("🗑️  Step 2: Removing Detailed Info Section...")
    
    # Find the section start
    section_start = content.find('      {/* Detailed Info Section */}')
    if section_start != -1:
        # Find the end by looking for the next major section comment
        section_patterns = [
            '      {/* Key Details */}',
            '      {/* Real Documents Download */}',
            '      {/* Contact */}'
        ]
        
        section_end = None
        for pattern in section_patterns:
            pos = content.find(pattern, section_start + 1)
            if pos != -1:
                section_end = pos
                break
        
        if section_end:
            content = content[:section_start] + content[section_end:]
            print("   ✅ Removed Detailed Info Section")
        else:
            print("   ❌ Could not find end of Detailed Info Section")
    else:
        print("   ❌ Could not find Detailed Info Section")
    
    # Step 3: Remove state variables
    print("🗑️  Step 3: Removing state variables...")
    
    # Remove detailsStatus state
    content = re.sub(r'  const \[detailsStatus, setDetailsStatus\] = useState\(null\)\n', '', content)
    content = re.sub(r'  const \[fetchingDetails, setFetchingDetails\] = useState\(false\)\n', '', content)
    
    # Step 4: Remove handleGetDetails function
    print("🗑️  Step 4: Removing handleGetDetails function...")
    
    # Find the function
    func_start = content.find('  const handleGetDetails = async () => {')
    if func_start != -1:
        # Find the matching closing brace
        brace_count = 0
        pos = func_start
        in_function = False
        
        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
                in_function = True
            elif content[pos] == '}':
                brace_count -= 1
                if in_function and brace_count == 0:
                    # Found the end
                    func_end = pos + 1
                    # Include any trailing newlines
                    while func_end < len(content) and content[func_end] in ['\n', ' ', '\t']:
                        if content[func_end] == '\n':
                            func_end += 1
                            break
                        func_end += 1
                    
                    content = content[:func_start] + content[func_end:]
                    print("   ✅ Removed handleGetDetails function")
                    break
            pos += 1
    else:
        print("   ❌ Could not find handleGetDetails function")
    
    # Step 5: Remove downloadDetailFile function
    print("🗑️  Step 5: Removing downloadDetailFile function...")
    
    pattern = r'  const downloadDetailFile = \(filename\) => \{[^}]+\}\n+'
    if re.search(pattern, content):
        content = re.sub(pattern, '', content)
        print("   ✅ Removed downloadDetailFile function")
    else:
        print("   ❌ Could not find downloadDetailFile function")
    
    # Step 6: Clean up unused imports
    print("🗑️  Step 6: Cleaning up imports...")
    
    # Remove Package and Clock from imports since they were only used in removed sections
    content = re.sub(r', Package', '', content)
    content = re.sub(r'Package, ', '', content)
    content = re.sub(r', Clock', '', content) 
    content = re.sub(r'Clock, ', '', content)
    
    print(f"📁 New file size: {len(content):,} characters")
    print(f"📉 Removed: {len(re.sub(r'', '', content))} characters")
    
    # Write the cleaned file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ SURGICAL REMOVAL COMPLETE!")
    print("🎯 Only Real Documents functionality should remain")
    
except Exception as e:
    print(f"❌ Error: {e}")