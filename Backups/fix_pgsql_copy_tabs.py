#!/usr/bin/env python3
"""
PostgreSQL COPY Block Fixer for Employee Management System
Fixes tab/space formatting issues in PostgreSQL dump files

Usage: python fix_pgsql_copy_tabs.py currentFileName.sql newFileName.sql
"""
import re
import sys
import logging
from datetime import datetime

def fix_copy_blocks(input_file, output_file):
    """
    Fix COPY FROM stdin blocks in PostgreSQL dump files
    Converts space-separated data to tab-separated format
    """
    logging.info(f"Starting COPY block fix: {input_file} -> {output_file}")
    
    inside_copy = False
    col_count = 0
    lines_processed = 0
    lines_fixed = 0
    
    with open(input_file, 'r', encoding='utf8') as fin, \
         open(output_file, 'w', encoding='utf8') as fout:
        
        for line_num, line in enumerate(fin, 1):
            lines_processed += 1
            
            # Detect COPY block start
            copy_match = re.match(r'^COPY\s+(\S+)\s*\(([^)]+)\)\s+FROM\s+stdin;', 
                                line, re.IGNORECASE)
            if copy_match:
                inside_copy = True
                table_name = copy_match.group(1)
                cols = [c.strip() for c in copy_match.group(2).split(',')]
                col_count = len(cols)
                logging.debug(f"Found COPY block for table {table_name} with {col_count} columns")
                fout.write(line)
                continue

            # Detect COPY block end
            if inside_copy and line.strip() == r'\.':
                inside_copy = False
                col_count = 0
                logging.debug(f"End of COPY block at line {line_num}")
                fout.write(line)
                continue

            # Fix data lines inside COPY blocks
            if inside_copy and line.strip() and not line.strip().startswith('--'):
                original_line = line.rstrip('\n')
                parts = original_line.split(maxsplit=col_count-1)
                
                if len(parts) == col_count:
                    fixed_line = '\t'.join(parts) + '\n'
                    if fixed_line != line:
                        lines_fixed += 1
                        logging.debug(f"Fixed line {line_num}: {original_line[:50]}...")
                    fout.write(fixed_line)
                else:
                    fout.write(line)
            else:
                fout.write(line)
    
    logging.info(f"Processing complete: {lines_processed} lines processed, {lines_fixed} lines fixed")
    return lines_processed, lines_fixed

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) != 3:
        print("PostgreSQL COPY Block Fixer")
        print("Usage: python fix_pgsql_copy_tabs.py input.sql output.sql")
        print("\nFixes formatting issues in PostgreSQL dump files")
        sys.exit(1)
    
    input_file, output_file = sys.argv[1], sys.argv[2]
    
    try:
        lines_processed, lines_fixed = fix_copy_blocks(input_file, output_file)
        print(f"✅ Success! Fixed {lines_fixed} lines out of {lines_processed} total")
        print(f"📁 Fixed file written to: {output_file}")
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)