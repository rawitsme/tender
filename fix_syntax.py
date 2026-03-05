#!/usr/bin/env python3
"""
Fix JavaScript syntax errors in TenderDetail.jsx
"""

file_path = '/Users/rahulwealthdiscovery.in/Code/Tender/frontend/src/pages/TenderDetail.jsx'

print("🔧 FIXING JAVASCRIPT SYNTAX")
print("=" * 30)

try:
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    print(f"📁 Total lines: {len(lines)}")
    
    # Check for common issues around line 545
    issue_found = False
    
    for i, line in enumerate(lines):
        line_num = i + 1
        
        # Look for duplicate closing braces or other issues
        if line_num >= 540 and line_num <= 550:
            print(f"{line_num:3d}: {line.rstrip()}")
            
        # Check for unmatched braces
        if line.strip() == '}' and line_num >= 540:
            # Check if this is an extra brace
            prev_line = lines[i-1].strip() if i > 0 else ''
            if prev_line == ')':
                print(f"🔍 Possible extra brace at line {line_num}")
    
    # Try to validate the overall structure by counting braces
    open_braces = 0
    for i, line in enumerate(lines):
        open_braces += line.count('{')
        open_braces -= line.count('}')
        
        if open_braces < 0:
            print(f"❌ Too many closing braces at line {i+1}: {line.strip()}")
            issue_found = True
            break
    
    if open_braces > 0:
        print(f"❌ Missing {open_braces} closing braces")
        issue_found = True
    elif open_braces < 0:
        print(f"❌ {abs(open_braces)} extra closing braces")
        issue_found = True
    else:
        print("✅ Brace count is balanced")
    
    # Check parentheses too
    open_parens = 0
    for i, line in enumerate(lines):
        open_parens += line.count('(')
        open_parens -= line.count(')')
        
        if open_parens < 0:
            print(f"❌ Too many closing parentheses at line {i+1}: {line.strip()}")
            issue_found = True
            break
    
    if open_parens > 0:
        print(f"❌ Missing {open_parens} closing parentheses")
        issue_found = True
    elif open_parens < 0:
        print(f"❌ {abs(open_parens)} extra closing parentheses")
        issue_found = True
    else:
        print("✅ Parentheses count is balanced")
    
    if not issue_found:
        print("✅ No obvious syntax issues found")
        print("💡 The error might be more subtle - checking for specific patterns...")
        
        # Look for common JSX patterns that might be broken
        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()
            
            # Check for incomplete JSX tags
            if '<' in stripped and '>' not in stripped and '/>' not in stripped:
                print(f"🔍 Possible incomplete tag at line {line_num}: {stripped}")
            
            # Check for missing commas in object literals
            if stripped.endswith('}') and line_num < len(lines) - 1:
                next_line = lines[i+1].strip()
                if next_line.startswith("'") or next_line.startswith('"'):
                    print(f"🔍 Possible missing comma at line {line_num}")
        
except Exception as e:
    print(f"❌ Error: {e}")