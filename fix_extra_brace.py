#!/usr/bin/env python3
"""
Remove the extra closing brace from TenderDetail.jsx
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🔧 REMOVING EXTRA CLOSING BRACE")
print("=" * 35)

try:
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    print(f"📁 Total lines: {len(lines)}")
    
    # Show lines around the problem area
    for i in range(540, min(547, len(lines))):
        print(f"{i+1:3d}: {lines[i].rstrip()}")
    
    # Remove line 545 (index 544) which has the extra brace
    if len(lines) > 544 and lines[544].strip() == '}':
        print(f"🗑️  Removing extra brace at line 545: '{lines[544].strip()}'")
        lines.pop(544)
        
        # Write the fixed content
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print("✅ Successfully removed extra closing brace!")
        print(f"📁 New total lines: {len(lines)}")
        
        # Show the fixed lines
        print("\n📋 Fixed structure:")
        for i in range(min(540, len(lines)), len(lines)):
            print(f"{i+1:3d}: {lines[i].rstrip()}")
        
    else:
        print("❌ Could not identify the exact extra brace to remove")
        
except Exception as e:
    print(f"❌ Error: {e}")