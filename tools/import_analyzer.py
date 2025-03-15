#!/usr/bin/env python3
import os
import re
import sys
from collections import defaultdict

def extract_imports(file_path):
    """Extract all imports from a Python file."""
    imports = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Match import statements
    import_pattern = r'^import\s+([\w\.]+)|^from\s+([\w\.]+)\s+import'
    for line in content.split('\n'):
        match = re.search(import_pattern, line.strip())
        if match:
            module = match.group(1) or match.group(2)
            imports.append(module)
            
    return imports

def find_circular_imports(directory):
    """Find circular imports in a directory."""
    module_imports = {}
    file_to_module = {}
    
    # First pass: collect all imports
    for root, _, files in os.walk(directory):
        for filename in files:
            if not filename.endswith('.py'):
                continue
                
            file_path = os.path.join(root, filename)
            module_name = os.path.splitext(filename)[0]
            
            # Store mapping from filename to module
            file_to_module[file_path] = module_name
            
            # Store imports for this module
            module_imports[module_name] = extract_imports(file_path)
    
    # Second pass: check for circular imports
    circular_refs = []
    
    def check_circular(module, visited=None, path=None):
        if visited is None:
            visited = set()
        if path is None:
            path = []
            
        if module in visited:
            circular_path = path + [module]
            circular_refs.append(" -> ".join(circular_path))
            return True
            
        if module not in module_imports:
            return False
            
        visited.add(module)
        path.append(module)
        
        for imported in module_imports[module]:
            # Check only direct imports from this project
            base_module = imported.split('.')[0]
            if base_module in module_imports:
                if check_circular(base_module, visited.copy(), path.copy()):
                    return True
        
        return False
    
    # Check each module
    for module in module_imports:
        check_circular(module)
    
    return circular_refs

def analyze_async_issues(directory):
    """Find potential async issues that might cause tests to hang."""
    potential_issues = []
    
    async_patterns = {
        'unresolved_promise': r'(new\s+Promise|promise\s*\(|async\s+def|async\s+function|\.then\()',
        'missing_await': r'(await|async)',
        'timeout': r'(setTimeout|time\.sleep)'
    }
    
    for root, _, files in os.walk(directory):
        for filename in files:
            if not (filename.endswith('.py') or filename.endswith('.js')):
                continue
                
            file_path = os.path.join(root, filename)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            file_issues = []
            
            # Check for async patterns
            for pattern_name, pattern in async_patterns.items():
                matches = re.findall(pattern, content)
                if matches and 'missing_await' not in pattern_name:
                    # Check if file has await if it has async promises
                    if pattern_name == 'unresolved_promise' and 'missing_await' in async_patterns:
                        await_matches = re.findall(async_patterns['missing_await'], content)
                        if not await_matches:
                            file_issues.append(f"Potential unresolved promise: async code without await")
                    else:
                        file_issues.append(f"Potential {pattern_name} issue")
            
            # Check for test completion issues in Python
            if filename.endswith('.py') and ('unittest' in content or 'pytest' in content):
                if 'tearDown' in content and not re.search(r'super\(\)\.tearDown\(\)', content):
                    file_issues.append("Missing super().tearDown() call")
            
            # Check for test completion issues in JavaScript
            if filename.endswith('.js') and ('describe(' in content or 'it(' in content):
                if 'done' in content and not re.search(r'done\(\)', content):
                    file_issues.append("Potential uncalled done() callback")
            
            # NEW: Check for uncleaned event listeners
            if re.search(r'(addEventListener|on\(|\.\s*on\s*=|emitter\.on|events\.on)', content):
                if not re.search(r'(removeEventListener|removeAllListeners|off\(|\.\s*off)', content):
                    file_issues.append("Event listeners added but not removed")
            
            # NEW: Check for uncaught exceptions in async code
            if re.search(r'(async|promise|then)', content, re.IGNORECASE):
                if not re.search(r'(try\s*{|try:|\.catch\(|except\s+|finally\s*{|finally:)', content):
                    file_issues.append("Async code without proper error handling")
            
            # NEW: Check for potential infinite loops
            if re.search(r'while\s*\(\s*true\s*\)|while\s+True:', content):
                if not re.search(r'(break|return|sys\.exit|process\.exit)', content):
                    file_issues.append("Potential infinite loop detected")
            
            # NEW: Check for recursive functions without clear exit condition
            if re.search(r'def\s+(\w+).*?:\s*.*?\1\s*\(|function\s+(\w+).*?{.*?\2\s*\(', content, re.DOTALL):
                file_issues.append("Recursive function - check for proper termination condition")
                
            # NEW: Check for unclosed resources
            if filename.endswith('.py'):
                # Look for opened files/connections without context manager
                if re.search(r'open\s*\(', content) and not re.search(r'with\s+open', content):
                    file_issues.append("File opened without context manager (with statement)")
                if re.search(r'socket\.\w+\s*\(', content) and not re.search(r'\.close\(\)', content):
                    file_issues.append("Socket usage without explicit close()")
            
            # NEW: Check for process termination
            if re.search(r'(sys\.exit|exit\(\)|process\.exit|os\._exit)', content):
                file_issues.append("Process termination found - could cause test runner to exit prematurely")
            
            # NEW: Check for mocks not being reset
            if re.search(r'(mock\.|Mock\(|patch\.|MagicMock)', content, re.IGNORECASE):
                if not re.search(r'(\.reset_mock\(\)|\.stop\(\))', content):
                    file_issues.append("Mocks created but potentially not reset/stopped")
            
            if file_issues:
                potential_issues.append(f"{file_path}:\n  - " + "\n  - ".join(file_issues))
    
    return potential_issues

def check_for_global_state_modifications(directory):
    """Check for modifications to global state that might not be reset."""
    global_state_issues = []
    
    for root, _, files in os.walk(directory):
        for filename in files:
            if not filename.endswith('.py'):
                continue
                
            file_path = os.path.join(root, filename)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_issues = []
            
            # Check for global variables being modified
            if re.search(r'global\s+\w+', content):
                file_issues.append("Global variables modified - check for cleanup")
            
            # Check for environment variables being set but not restored
            if re.search(r'os\.environ\[\s*[\'"]\w+[\'"]\s*\]\s*=', content):
                if not re.search(r'(setUp|tearDown|fixture)', content):
                    file_issues.append("Environment variables modified without clear teardown")
            
            # Check for monkey patching without restoration
            if re.search(r'(monkeypatch|patch|setattr\s*\(\s*\w+)', content):
                if not re.search(r'(tearDown|with|context|restore)', content):
                    file_issues.append("Monkey patching detected - check for restoration")
            
            if file_issues:
                global_state_issues.append(f"{file_path}:\n  - " + "\n  - ".join(file_issues))
    
    return global_state_issues

def find_thread_issues(directory):
    """Find issues with threads or processes that might not terminate."""
    thread_issues = []
    
    for root, _, files in os.walk(directory):
        for filename in files:
            if not filename.endswith('.py'):
                continue
                
            file_path = os.path.join(root, filename)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            file_issues = []
            
            # Check for thread creation
            if re.search(r'(Thread\(|Process\(|multiprocessing|threading\.)', content):
                # Check for daemon setting or join()
                if not re.search(r'(daemon\s*=\s*True|\.setDaemon\(True\)|\.join\()', content):
                    file_issues.append("Thread/Process created without daemon=True or join()")
            
            if file_issues:
                thread_issues.append(f"{file_path}:\n  - " + "\n  - ".join(file_issues))
    
    return thread_issues

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    
    print("Analyzing imports for circular dependencies...")
    circular_refs = find_circular_imports(directory)
    
    if circular_refs:
        print("\nFound circular imports:")
        for ref in circular_refs:
            print(f"  {ref}")
    else:
        print("\nNo circular imports found.")
    
    print("\nAnalyzing potential async issues...")
    async_issues = analyze_async_issues(directory)
    
    if async_issues:
        print("\nPotential async issues that might cause tests to hang:")
        for issue in async_issues:
            print(f"\n{issue}")
    else:
        print("\nNo obvious async issues found.")
    
    # NEW: Check for global state modifications
    print("\nChecking for global state modifications...")
    global_state_issues = check_for_global_state_modifications(directory)
    
    if global_state_issues:
        print("\nPotential global state modification issues:")
        for issue in global_state_issues:
            print(f"\n{issue}")
    else:
        print("\nNo obvious global state issues found.")
    
    # NEW: Check for thread/process issues
    print("\nChecking for thread/process issues...")
    thread_issues = find_thread_issues(directory)
    
    if thread_issues:
        print("\nPotential thread/process issues:")
        for issue in thread_issues:
            print(f"\n{issue}")
    else:
        print("\nNo obvious thread/process issues found.")
    
    print("\nAnalysis complete!")
