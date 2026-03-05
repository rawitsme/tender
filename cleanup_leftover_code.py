#!/usr/bin/env python3
"""
Clean up leftover code references from the surgical removal
"""

import re

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🧹 CLEANING UP LEFTOVER CODE")
print("=" * 30)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📁 Original file size: {len(content):,} characters")
    
    # Remove the details status check API call and its related lines
    print("🗑️  Removing leftover API calls...")
    
    # Remove the entire block:
    # // Check details status
    # api.get(`/details/status/${id}`)
    #   .then(r => setDetailsStatus(r.data))
    #   .catch(() => {})
    
    pattern = r'\s*// Check details status\s*\n\s*api\.get\(`/details/status/\$\{id\}`\)\s*\n\s*\.then\(r => setDetailsStatus\(r\.data\)\)\s*\n\s*\.catch\(\(\) => \{\}\)\s*\n'
    if re.search(pattern, content):
        content = re.sub(pattern, '\n', content)
        print("   ✅ Removed details status API call")
    else:
        # Try a more flexible pattern
        lines = content.split('\n')
        new_lines = []
        skip_next = 0
        
        for i, line in enumerate(lines):
            if skip_next > 0:
                skip_next -= 1
                continue
                
            if 'Check details status' in line:
                # Skip this line and the next few lines
                skip_next = 3  # Skip the api.get, .then, and .catch lines
                continue
            elif 'api.get(`/details/status/' in line:
                # Skip this line and next 2
                skip_next = 2
                continue
            elif 'setDetailsStatus(r.data)' in line:
                # Skip this line and next 1
                skip_next = 1
                continue
            else:
                new_lines.append(line)
        
        content = '\n'.join(new_lines)
        print("   ✅ Removed details status API call (alternative method)")
    
    # Remove any other references to setDetailsStatus that might remain
    content = re.sub(r'.*setDetailsStatus.*\n', '', content)
    
    print(f"📁 New file size: {len(content):,} characters")
    
    # Write the cleaned file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ LEFTOVER CODE CLEANUP COMPLETE!")
    
    # Verify no references remain
    remaining_refs = []
    if 'detailsStatus' in content:
        remaining_refs.append('detailsStatus')
    if 'fetchingDetails' in content:
        remaining_refs.append('fetchingDetails')
    if 'handleGetDetails' in content:
        remaining_refs.append('handleGetDetails')
        
    if remaining_refs:
        print(f"⚠️  Warning: Still found references to: {', '.join(remaining_refs)}")
    else:
        print("✅ No leftover references found")
    
except Exception as e:
    print(f"❌ Error: {e}")