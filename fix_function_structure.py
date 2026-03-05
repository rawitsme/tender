#!/usr/bin/env python3
"""
Fix the broken TenderDetail function structure
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🔧 FIXING TENDERDETAIL FUNCTION STRUCTURE")
print("=" * 45)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📁 Original size: {len(content):,} characters")
    
    # Find where the TenderDetail function starts
    function_start = content.find('function TenderDetail() {')
    if function_start == -1:
        print("❌ Could not find TenderDetail function")
        exit(1)
        
    print(f"📍 TenderDetail function starts at position: {function_start}")
    
    # Find where the broken code is (where link.click() ends)
    link_click_pos = content.find('link.click()')
    if link_click_pos != -1:
        # Find the end of this block (should be followed by proper function closing)
        search_start = link_click_pos + len('link.click()')
        
        # Look for the pattern where the function should close
        # After link.click(), we should close the downloadDetailFile and then the TenderDetail function
        
        # Find the next closing brace after link.click()
        closing_brace_pos = content.find('}', search_start)
        
        if closing_brace_pos != -1:
            print(f"📍 Found closing brace after link.click() at position: {closing_brace_pos}")
            
            # Insert the proper function closing brace right after this brace
            insertion_point = closing_brace_pos + 1
            
            # Find the end of the line
            while insertion_point < len(content) and content[insertion_point] in ['\n', ' ', '\t']:
                insertion_point += 1
            
            # We need to wrap everything from the TenderDetail function in proper braces
            # The issue is that the statements after line 200 should be inside the function
            
            # Find where the early returns are
            early_return1 = content.find('if (loading) return')
            early_return2 = content.find('if (!tender) return')
            
            if early_return1 != -1:
                print(f"📍 Found early returns at positions: {early_return1}, {early_return2}")
                
                # Everything from the early returns to the final export should be inside the function
                # Add a closing brace before the export default line
                export_pos = content.find('export default TenderDetail')
                
                if export_pos != -1:
                    # Insert closing brace before export
                    new_content = content[:export_pos] + '}\n\n' + content[export_pos:]
                    
                    print("✅ Added missing closing brace for TenderDetail function")
                    
                    # Write the fixed content
                    with open(file_path, 'w') as f:
                        f.write(new_content)
                    
                    print(f"📁 New size: {len(new_content):,} characters")
                    print("✅ Function structure should now be fixed!")
                    
                else:
                    print("❌ Could not find export statement")
            else:
                print("❌ Could not find early return statements")
        else:
            print("❌ Could not find closing brace after link.click()")
    else:
        print("❌ Could not find link.click() statement")
        
except Exception as e:
    print(f"❌ Error: {e}")