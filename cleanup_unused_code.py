#!/usr/bin/env python3
"""
Remove unused state variables and functions from TenderDetail.jsx
"""

import re

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🧹 CLEANING UP UNUSED CODE")
print("=" * 30)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📁 Original file size: {len(content):,} characters")
    
    # Remove state variables
    print("🗑️  Removing unused state variables...")
    content = re.sub(r'  const \[detailsStatus, setDetailsStatus\] = useState\(null\)\n', '', content)
    content = re.sub(r'  const \[fetchingDetails, setFetchingDetails\] = useState\(false\)\n', '', content)
    
    # Remove handleGetDetails function
    print("🗑️  Removing handleGetDetails function...")
    # Find the function start
    start_pattern = r'  const handleGetDetails = async \(\) => \{'
    start_match = re.search(start_pattern, content)
    if start_match:
        start_pos = start_match.start()
        
        # Find the matching closing brace by counting braces
        pos = start_match.end()
        brace_count = 1
        
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        
        if brace_count == 0:
            # Include the closing brace and newline
            end_pos = pos
            # Also remove the extra newline after the function
            if pos < len(content) and content[pos] == '\n':
                end_pos += 1
            content = content[:start_pos] + content[end_pos:]
            print("   ✅ Removed handleGetDetails function")
        else:
            print("   ❌ Could not find closing brace for handleGetDetails")
    else:
        print("   ❌ handleGetDetails function not found")
    
    # Remove downloadDetailFile function
    print("🗑️  Removing downloadDetailFile function...")
    pattern = r'  const downloadDetailFile = \(filename\) => \{[^}]+\}[^\n]*\n'
    if re.search(pattern, content):
        content = re.sub(pattern, '', content)
        print("   ✅ Removed downloadDetailFile function")
    else:
        print("   ❌ downloadDetailFile function not found")
    
    # Remove Package import since it's no longer used
    print("🗑️  Removing unused Package import...")
    content = re.sub(r', Package', '', content)
    content = re.sub(r'Package, ', '', content)
    
    # Remove Clock import since it's only used in removed section
    print("🗑️  Removing unused Clock import...")  
    content = re.sub(r', Clock', '', content)
    content = re.sub(r'Clock, ', '', content)
    
    print(f"📁 New file size: {len(content):,} characters")
    print(f"📉 Removed: {len(content) - len(re.sub(r'', '', content)):,} characters")
    
    # Write the modified content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Successfully cleaned up unused code!")
    print("🎯 File now contains only Real Documents functionality")
    
except Exception as e:
    print(f"❌ Error: {e}")