"""Audit script to find for-loops in module handleEvent methods missing self.checkForStop()."""
import os
import re

modules_dir = 'modules'
results = []

for fname in sorted(os.listdir(modules_dir)):
    if not fname.endswith('.py') or fname.startswith('__'):
        continue
    fpath = os.path.join(modules_dir, fname)
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    in_handle_event = False
    method_indent = None

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Track if we're in handleEvent or similar processing methods
        m = re.match(r'^(\s+)def (handleEvent|queryDomain|queryIP|query|enrichTarget|process)\s*\(', line)
        if m:
            in_handle_event = True
            method_indent = len(m.group(1))
        elif in_handle_event:
            dm = re.match(r'^(\s+)def \w+\s*\(', line)
            if dm:
                cur_indent = len(dm.group(1))
                if cur_indent <= method_indent:
                    in_handle_event = False

        # Look for for loops
        for_match = re.match(r'^(\s+)(for\s+.+\s+in\s+.+):\s*$', stripped)
        if not for_match:
            for_match = re.match(r'^(\s+)(for\s+.+\s+in\s+.+):\s*#.*$', stripped)

        if for_match and in_handle_event:
            loop_indent_len = len(for_match.group(1))
            loop_header = for_match.group(2).strip()
            loop_start = i + 1  # 1-indexed

            # Scan the body of this for loop
            has_check_for_stop = False
            loop_end = i + 1
            body_lines = 0
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                next_stripped = next_line.rstrip()
                if next_stripped == '':
                    j += 1
                    loop_end = j
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= loop_indent_len and next_stripped != '':
                    break
                body_lines += 1
                if 'self.checkForStop()' in next_line:
                    has_check_for_stop = True
                loop_end = j + 1
                j += 1

            # Only flag loops with substantial bodies (>=5 lines) missing checkForStop
            if body_lines >= 5 and not has_check_for_stop:
                # Skip loops over small fixed literal lists
                skip = False
                if re.search(r'in\s+\[', loop_header):
                    # Count items in literal list
                    bracket_start = loop_header.index('[')
                    bracket_content = loop_header[bracket_start:]
                    if bracket_content.count(',') < 4:
                        skip = True
                if re.search(r'in\s+range\(\d+\)', loop_header):
                    range_match = re.search(r'range\((\d+)\)', loop_header)
                    if range_match and int(range_match.group(1)) < 5:
                        skip = True
                # Skip loops over small known fixed sets
                if re.search(r'in\s+\(.*,.*\)\s*$', loop_header) and loop_header.count(',') < 4:
                    skip = True

                if not skip:
                    results.append({
                        'file': fname,
                        'line_start': loop_start,
                        'line_end': loop_end,
                        'header': loop_header,
                        'body_lines': body_lines,
                        'has_check': has_check_for_stop
                    })
        i += 1

# Print results
for r in results:
    print("FILE: " + r['file'])
    print("  Lines: {}-{} ({} body lines)".format(r['line_start'], r['line_end'], r['body_lines']))
    print("  Loop:  " + r['header'])
    print("  checkForStop: " + ('PRESENT' if r['has_check'] else 'MISSING'))
    print()
print("Total loops flagged: {}".format(len(results)))
