#!/usr/bin/env python3
"""
Final fix for extra closing brace in TenderDetail.jsx
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🔧 FINAL FIX FOR EXTRA CLOSING BRACE")
print("=" * 38)

try:
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    print(f"📁 Total lines: {len(lines)}")
    
    # Show the end of the file
    print("\n📋 Current end of file:")
    for i in range(max(0, len(lines)-10), len(lines)):
        print(f"{i+1:3d}: {repr(lines[i])}")
    
    # Find the pattern where we have:
    # )
    # [blank line]
    # }
    # [blank line]
    # export default...
    
    # This should be:
    # )
    # }
    # [blank line] 
    # export default...
    
    modified = False
    for i in range(len(lines)-3):
        if (lines[i].strip() == ')' and 
            lines[i+1].strip() == '' and
            lines[i+2].strip() == '}' and
            i+3 < len(lines) and 
            lines[i+3].strip() == ''):
            
            print(f"🔍 Found pattern at line {i+1}")
            # Remove the blank line between ) and }
            lines.pop(i+1)
            modified = True
            break
    
    if modified:
        # Write the corrected file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print("✅ Removed extra blank line")
        print(f"📁 New total lines: {len(lines)}")
        
        # Show the fixed end of file  
        print("\n📋 Fixed end of file:")
        for i in range(max(0, len(lines)-8), len(lines)):
            print(f"{i+1:3d}: {repr(lines[i])}")
            
    else:
        print("❌ Could not identify the specific pattern to fix")
        
        # Let's just manually fix the known issue
        # Look for the specific pattern around line 546
        for i in range(len(lines)):
            if lines[i].strip() == ')' and i+1 < len(lines):
                next_non_empty = i+1
                while next_non_empty < len(lines) and lines[next_non_empty].strip() == '':
                    next_non_empty += 1
                
                if (next_non_empty < len(lines) and 
                    lines[next_non_empty].strip() == '}' and 
                    next_non_empty + 1 < len(lines) and
                    next_non_empty + 2 < len(lines) and
                    'export default' in lines[next_non_empty + 2]):
                    
                    print(f"🔍 Alternative fix: Removing extra content between lines {i+1} and {next_non_empty+2}")
                    
                    # Keep only: ), }, blank line, export
                    new_lines = lines[:i+1] + [lines[next_non_empty]] + ['\n'] + lines[next_non_empty+2:]
                    
                    with open(file_path, 'w') as f:
                        f.writelines(new_lines)
                    
                    print("✅ Applied alternative fix")
                    print(f"📁 New total lines: {len(new_lines)}")
                    break
        
except Exception as e:
    print(f"❌ Error: {e}")