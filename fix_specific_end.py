#!/usr/bin/env python3
"""
Fix the specific ending pattern for TenderDetail.jsx
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🎯 FIXING SPECIFIC FILE ENDING")
print("=" * 32)

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for the pattern that includes "Similar Tenders" as this is the last major section
    # before the closing of the main JSX return
    similar_tenders_pattern = '{/* Similar Tenders */}'
    similar_pos = content.find(similar_tenders_pattern)
    
    if similar_pos != -1:
        print(f"📍 Found 'Similar Tenders' section at position: {similar_pos}")
        
        # From this point, find the closing pattern
        # Look for the specific pattern from the debug output: 
        # ))}
        #           </div>
        #         </div>
        #       )}
        #     </div>
        #   )
        # }
        
        # Find the pattern after Similar Tenders
        search_start = similar_pos
        
        # Look for the sequence that ends with:
        # </div>
        # </div>  
        # )}
        # </div>
        # )
        
        patterns_to_find = [
            '))}\\n          </div>\\n        </div>\\n      )}\\n    </div>\\n  )',
            '))}\\n          </div>\\n        </div>\\n      )}\\n    </div>\\n  )'
        ]
        
        found_pattern = None
        pattern_end = None
        
        for pattern in patterns_to_find:
            pattern_pos = content.find(pattern.replace('\\n', '\\n'), search_start)
            if pattern_pos != -1:
                found_pattern = pattern
                pattern_end = pattern_pos + len(pattern.replace('\\n', '\\n'))
                print(f"📍 Found ending pattern at position: {pattern_pos}")
                break
        
        if pattern_end:
            # Create the clean ending
            clean_ending = '''
}

export default TenderDetail'''
            
            new_content = content[:pattern_end] + clean_ending
            
            # Write the corrected file
            with open(file_path, 'w') as f:
                f.write(new_content)
            
            print("✅ Applied clean ending!")
            print(f"📁 Original: {len(content):,} chars")
            print(f"📁 New: {len(new_content):,} chars")
            
            # Show final lines
            lines = new_content.split('\\n')
            print("\\n📋 Final 10 lines:")
            for i, line in enumerate(lines[-10:], len(lines)-9):
                print(f"{i:3d}: {repr(line)}")
                
        else:
            print("❌ Could not find the specific ending pattern")
            
            # Fallback: manually construct from the debug output
            # Use the last pattern we saw: item 41
            export_pos = content.find('export default TenderDetail')
            if export_pos != -1:
                # Go backwards to find the JSX closing
                search_back = export_pos
                while search_back > 0 and content[search_back:search_back+2] != ')\\n':
                    search_back -= 1
                
                if search_back > 0:
                    end_pos = search_back + 2
                    clean_ending = '''
}

export default TenderDetail'''
                    new_content = content[:end_pos] + clean_ending
                    
                    with open(file_path, 'w') as f:
                        f.write(new_content)
                    
                    print("✅ Applied fallback fix!")
                    
    else:
        print("❌ Could not find 'Similar Tenders' section")
        
except Exception as e:
    print(f"❌ Error: {e}")