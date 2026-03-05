#!/usr/bin/env python3
"""
Create a completely clean end for TenderDetail.jsx by finding the JSX return statement
and ensuring proper closure
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🧹 CREATING CLEAN FILE END")
print("=" * 28)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the main return statement in the TenderDetail function
    return_pattern = '  return ('
    return_pos = content.find(return_pattern)
    
    if return_pos == -1:
        print("❌ Could not find main return statement")
        exit(1)
    
    print(f"📍 Found main return at position: {return_pos}")
    
    # Now find the JSX content - look for the closing div and closing paren that match
    # The structure should be:
    # return (
    #   <div className="max-w-4xl space-y-6">
    #     ... lots of JSX ...
    #   </div>
    # )
    
    # Count opening and closing tags from the return statement
    search_start = return_pos + len(return_pattern)
    
    # Find the matching closing pattern
    # Look for the pattern:
    #     </div>
    #   )
    
    # Find all occurrences of "    </div>"
    div_pattern = '    </div>'
    paren_pattern = '  )'
    
    # Look for the pattern where </div> is followed by )
    div_positions = []
    pos = search_start
    while True:
        pos = content.find(div_pattern, pos)
        if pos == -1:
            break
        div_positions.append(pos)
        pos += len(div_pattern)
    
    print(f"📍 Found {len(div_positions)} possible closing divs")
    
    # For each div, check if it's followed by ')' at the right indentation level
    correct_end_pos = None
    for div_pos in div_positions:
        # Look for the pattern: </div>\n  )
        check_pos = div_pos + len(div_pattern)
        if (check_pos + 4 < len(content) and 
            content[check_pos:check_pos+4] == '\\n  )'):
            correct_end_pos = check_pos + 4
            print(f"📍 Found correct JSX end at position: {correct_end_pos}")
            break
    
    if correct_end_pos:
        # Construct the clean ending
        clean_ending = '''
}

export default TenderDetail'''
        
        new_content = content[:correct_end_pos] + clean_ending
        
        print(f"📁 Original length: {len(content):,}")
        print(f"📁 New length: {len(new_content):,}")
        
        # Write the clean file
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        print("✅ Created clean file ending!")
        
        # Show the last few lines
        lines = new_content.split('\\n')
        print("\\n📋 Final lines:")
        for i, line in enumerate(lines[-8:], len(lines)-8):
            print(f"{i+1:3d}: {repr(line)}")
    
    else:
        print("❌ Could not find the correct JSX ending pattern")
        print("🔍 Showing all found closing divs:")
        for i, div_pos in enumerate(div_positions):
            context_start = max(0, div_pos - 50)
            context_end = min(len(content), div_pos + 50)
            context = content[context_start:context_end].replace('\\n', '\\\\n')
            print(f"   {i+1}: ...{context}...")
        
except Exception as e:
    print(f"❌ Error: {e}")