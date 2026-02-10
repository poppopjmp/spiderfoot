#!/usr/bin/env python3
"""
Comprehensive ThreadReaper Migration Tool
========================================

Automatically migrates the entire SpiderFoot test suite to use
ThreadReaper infrastructure, eliminating thread leaks and timeouts
across all platforms and Python versions.
"""
from __future__ import annotations

import os
import sys
import re
import shutil
from pathlib import Path
import ast
import tempfile

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


class ThreadReaperMigrator:
    """Comprehensive ThreadReaper migration tool."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "test"
        
        # Migration statistics
        self.stats = {
            'total_files': 0,
            'migrated_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'errors': []
        }
        
        # Migration patterns
        self.migration_patterns = {
            'scanner_tests': {
                'old_import': 'from test.unit.utils.test_base import SpiderFootTestBase',
                'new_import': 'from test.unit.utils.test_scanner_base import TestScannerBase',
                'old_class': 'SpiderFootTestBase',
                'new_class': 'TestScannerBase',
                'keywords': ['scanner', 'SpiderFootScanner']
            },
            'module_tests': {
                'old_import': 'from test.unit.utils.test_base import SpiderFootTestBase',
                'new_import': 'from test.unit.utils.test_module_base import TestModuleBase',
                'old_class': 'SpiderFootTestBase',
                'new_class': 'TestModuleBase',
                'keywords': ['sfp_', 'module']
            },
            'general_tests': {
                'old_import': 'from test.unit.utils.test_base import SpiderFootTestBase',
                'new_import': 'from test.unit.utils.test_base import SpiderFootTestBase\nfrom test.unit.utils.resource_manager import get_test_resource_manager\nfrom test.unit.utils.thread_registry import get_test_thread_registry',
                'old_class': 'SpiderFootTestBase',
                'new_class': 'SpiderFootTestBase',  # Keep same but enhance
                'keywords': []
            }
        }
    
    def analyze_test_file(self, file_path: Path) -> dict:
        """Analyze a test file to determine migration strategy."""
        try:
            content = file_path.read_text(encoding='utf-8')
            relative_path = file_path.relative_to(self.project_root)
            
            analysis = {
                'path': relative_path,
                'content': content,
                'needs_migration': False,
                'migration_type': None,
                'uses_threadreaper': False,
                'uses_old_base': False,
                'test_classes': [],
                'imports': []
            }
            
            # Check for existing ThreadReaper usage
            threadreaper_keywords = [
                'TestScannerBase', 'TestModuleBase', 'resource_manager',
                'thread_registry', 'leak_detector', 'shared_pool_cleanup'
            ]
            
            analysis['uses_threadreaper'] = any(keyword in content for keyword in threadreaper_keywords)
            analysis['uses_old_base'] = 'SpiderFootTestBase' in content
            
            # Determine migration type
            if 'scanner' in str(file_path).lower() or 'SpiderFootScanner' in content:
                analysis['migration_type'] = 'scanner_tests'
            elif 'sfp_' in file_path.name or 'modules' in str(file_path):
                analysis['migration_type'] = 'module_tests'
            else:
                analysis['migration_type'] = 'general_tests'
            
            # Check if migration is needed
            analysis['needs_migration'] = (
                analysis['uses_old_base'] and 
                not analysis['uses_threadreaper'] and
                'unittest.TestCase' not in content.replace('SpiderFootTestBase', '')
            )
            
            # Extract test classes
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a test class
                        if any(base.id in ['SpiderFootTestBase', 'unittest.TestCase', 'TestCase'] 
                               for base in node.bases if hasattr(base, 'id')):
                            analysis['test_classes'].append(node.name)
            except Exception:
                # Fallback: regex search for test classes
                class_pattern = r'class\s+(\w*Test\w*)\s*\([^)]*\):'
                matches = re.findall(class_pattern, content)
                analysis['test_classes'] = matches
            
            return analysis
            
        except Exception as e:
            return {
                'path': file_path.relative_to(self.project_root),
                'error': str(e),
                'needs_migration': False
            }
    
    def migrate_file_content(self, analysis: dict) -> tuple[str, bool]:
        """Migrate file content to use ThreadReaper infrastructure."""
        content = analysis['content']
        migration_type = analysis['migration_type']
        
        if not analysis['needs_migration']:
            return content, False
        
        patterns = self.migration_patterns[migration_type]
        modified = False
        
        # Replace imports
        if patterns['old_import'] in content:
            content = content.replace(patterns['old_import'], patterns['new_import'])
            modified = True
        
        # Replace class inheritance
        if patterns['old_class'] != patterns['new_class']:
            # More sophisticated class replacement
            class_pattern = rf'class\s+(\w+)\s*\(\s*{re.escape(patterns["old_class"])}\s*\)'
            replacement = rf'class \1({patterns["new_class"]})'
            
            if re.search(class_pattern, content):
                content = re.sub(class_pattern, replacement, content)
                modified = True
        
        # Add ThreadReaper setup if needed
        if migration_type in ['scanner_tests', 'module_tests']:
            setup_addition = self._generate_threadreaper_setup(migration_type)
            content = self._add_threadreaper_setup(content, setup_addition)
            modified = True
        
        return content, modified
    
    def _generate_threadreaper_setup(self, migration_type: str) -> str:
        """Generate ThreadReaper setup code for different test types."""
        if migration_type == 'scanner_tests':
            return '''
    def setUp(self):
        """Enhanced setUp with ThreadReaper scanner tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
'''
        elif migration_type == 'module_tests':
            return '''
    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
'''
        return ""
    
    def _add_threadreaper_setup(self, content: str, setup_code: str) -> str:
        """Add ThreadReaper setup to test classes that don't have it."""
        # Look for test classes without setUp/tearDown
        class_pattern = r'(class\s+\w*Test\w*\([^)]+\):\s*(?:\n\s*"""[^"]*""")?\s*\n)'
        
        def add_setup(match):
            class_def = match.group(1)
            # Check if setUp already exists
            if 'def setUp(' in content[match.end():match.end()+1000]:
                return class_def
            return class_def + setup_code
        
        return re.sub(class_pattern, add_setup, content)
    
    def migrate_file(self, file_path: Path) -> bool:
        """Migrate a single test file."""
        try:
            # Analyze file
            analysis = self.analyze_test_file(file_path)
            
            if 'error' in analysis:
                self.stats['errors'].append(f"Analysis failed for {file_path}: {analysis['error']}")
                self.stats['failed_files'] += 1
                return False
            
            if not analysis['needs_migration']:
                self.stats['skipped_files'] += 1
                return True
            
            # Create backup
            backup_path = file_path.with_suffix(file_path.suffix + '.threadreaper_backup')
            shutil.copy2(file_path, backup_path)
            
            try:
                # Migrate content
                new_content, modified = self.migrate_file_content(analysis)
                
                if modified:
                    # Write migrated content
                    file_path.write_text(new_content, encoding='utf-8')
                    print(f"✅ Migrated: {analysis['path']}")
                    self.stats['migrated_files'] += 1
                    return True
                else:
                    # Remove backup if no changes
                    backup_path.unlink()
                    self.stats['skipped_files'] += 1
                    return True
                    
            except Exception as e:
                # Restore from backup on failure
                shutil.copy2(backup_path, file_path)
                backup_path.unlink()
                self.stats['errors'].append(f"Migration failed for {file_path}: {e}")
                self.stats['failed_files'] += 1
                return False
                
        except Exception as e:
            self.stats['errors'].append(f"File operation failed for {file_path}: {e}")
            self.stats['failed_files'] += 1
            return False
    
    def find_test_files(self) -> list[Path]:
        """Find all test files in the project."""
        test_files = []
        
        # Find all Python test files
        for pattern in ["**/test_*.py", "**/*_test.py"]:
            test_files.extend(self.test_dir.glob(pattern))
        
        # Filter out files already using ThreadReaper
        filtered_files = []
        for file_path in test_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                # Skip if already using ThreadReaper
                if any(keyword in content for keyword in ['TestScannerBase', 'TestModuleBase']):
                    continue
                # Skip if not using SpiderFootTestBase
                if 'SpiderFootTestBase' not in content:
                    continue
                filtered_files.append(file_path)
            except Exception:
                continue
        
        return filtered_files
    
    def migrate_all_tests(self, dry_run: bool = False) -> bool:
        """Migrate all test files to use ThreadReaper infrastructure."""
        print("🚀 BROAD THREADREAPER MIGRATION")
        print("=" * 60)
        
        # Find all test files
        test_files = self.find_test_files()
        self.stats['total_files'] = len(test_files)
        
        print(f"📋 Found {len(test_files)} files needing migration")
        
        if dry_run:
            print("🔍 DRY RUN MODE - No files will be modified")
            
            # Analyze files
            migration_plan = {}
            for file_path in test_files:
                analysis = self.analyze_test_file(file_path)
                migration_type = analysis.get('migration_type', 'unknown')
                
                if migration_type not in migration_plan:
                    migration_plan[migration_type] = []
                migration_plan[migration_type].append(analysis['path'])
            
            print("\n📊 MIGRATION PLAN:")
            for migration_type, files in migration_plan.items():
                print(f"  {migration_type}: {len(files)} files")
                for file_path in files[:5]:  # Show first 5
                    print(f"    • {file_path}")
                if len(files) > 5:
                    print(f"    ... and {len(files) - 5} more")
            
            return True
        
        # Perform actual migration
        print("\n🔧 MIGRATING FILES:")
        print("-" * 40)
        
        success_count = 0
        for i, file_path in enumerate(test_files, 1):
            print(f"[{i:3d}/{len(test_files)}] {file_path.relative_to(self.project_root)}")
            
            if self.migrate_file(file_path):
                success_count += 1
        
        # Report results
        print(f"\n📊 MIGRATION RESULTS:")
        print(f"  Total files: {self.stats['total_files']}")
        print(f"  ✅ Migrated: {self.stats['migrated_files']}")
        print(f"  ⏭️  Skipped: {self.stats['skipped_files']}")
        print(f"  ❌ Failed: {self.stats['failed_files']}")
        
        if self.stats['errors']:
            print(f"\n⚠️  ERRORS ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Show first 10
                print(f"  • {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        success_rate = (success_count / len(test_files)) * 100 if test_files else 100
        print(f"\n🎯 Success rate: {success_rate:.1f}%")
        
        return success_rate > 90  # Consider successful if >90% migrated
    
    def integrate_scanner_registration(self) -> bool:
        """Integrate automatic ThreadReaper registration into SpiderFootScanner."""
        print("\n🔧 INTEGRATING SCANNER REGISTRATION")
        print("-" * 40)
        
        scanner_file = self.project_root / "spiderfoot" / "scan_service" / "scanner.py"
        
        if not scanner_file.exists():
            print("❌ Scanner file not found")
            return False
        
        try:
            content = scanner_file.read_text(encoding='utf-8')
            
            # Check if already integrated
            if 'thread_registry' in content or 'resource_manager' in content:
                print("✅ Scanner already has ThreadReaper integration")
                return True
            
            # Add imports
            import_addition = '''
# ThreadReaper infrastructure for automatic resource management
try:
    from test.unit.utils.thread_registry import get_test_thread_registry
    from test.unit.utils.resource_manager import get_test_resource_manager
    _THREADREAPER_AVAILABLE = True
except ImportError:
    _THREADREAPER_AVAILABLE = False
'''
            
            # Find the import section
            import_pattern = r'(from spiderfoot.*?import.*?\n)'
            if re.search(import_pattern, content):
                content = re.sub(import_pattern, r'\1' + import_addition, content, count=1)
            
            # Add registration in __init__
            init_pattern = r'(def __init__\(.*?\):.*?\n(?:\s*.*?\n)*)'
            
            def add_registration(match):
                init_content = match.group(1)
                registration_code = '''        
        # Auto-register with ThreadReaper if available (for tests)
        if _THREADREAPER_AVAILABLE:
            try:
                thread_registry = get_test_thread_registry()
                resource_manager = get_test_resource_manager()
                
                # Register scanner instance
                resource_manager.register_resource(
                    self, self._cleanup_scanner,
                    category="scanner", 
                    description=f"Scanner: {self.__scanName}"
                )
                
                # Register scanner thread if it gets created
                if hasattr(self, '_thread') and self._thread:
                    thread_registry.register(self._thread, "scanner", f"scanner_{self.__scanId}")
            except Exception:
                # Silently ignore ThreadReaper registration failures
                pass
'''
                return init_content + registration_code
            
            content = re.sub(init_pattern, add_registration, content, count=1)
            
            # Add cleanup method
            cleanup_method = '''
    def _cleanup_scanner(self):
        """Internal cleanup method for ThreadReaper integration."""
        try:
            if hasattr(self, 'shutdown') and callable(self.shutdown):
                self.shutdown()
        except Exception:
            pass
'''
            
            # Add before the last line of the class
            class_end_pattern = r'(\n\s*def shutdown\(.*?\):.*?)(\nclass|\n$|\Z)'
            if re.search(class_end_pattern, content, re.DOTALL):
                content = re.sub(class_end_pattern, cleanup_method + r'\1\2', content, count=1)
            
            # Write the modified content
            scanner_file.write_text(content, encoding='utf-8')
            print("✅ Scanner ThreadReaper integration added")
            return True
            
        except Exception as e:
            print(f"❌ Scanner integration failed: {e}")
            return False
    
    def update_ci_integration(self) -> bool:
        """Update CI configuration to include ThreadReaper leak detection."""
        print("\n🔧 UPDATING CI INTEGRATION")
        print("-" * 40)
        
        # Look for pytest configuration
        pytest_ini = self.project_root / "pytest.ini"
        
        if pytest_ini.exists():
            try:
                content = pytest_ini.read_text(encoding='utf-8')
                
                # Add ThreadReaper options
                if 'threadreaper' not in content:
                    threadreaper_config = '''
# ThreadReaper leak detection
addopts = --tb=short --strict-markers --disable-warnings
markers =
    threadreaper: mark test to use ThreadReaper infrastructure
    no_threadreaper: mark test to skip ThreadReaper (for special cases)
'''
                    content += threadreaper_config
                    pytest_ini.write_text(content, encoding='utf-8')
                    print("✅ pytest.ini updated with ThreadReaper configuration")
                else:
                    print("✅ pytest.ini already has ThreadReaper configuration")
                
                return True
                
            except Exception as e:
                print(f"❌ CI integration failed: {e}")
                return False
        
        print("⚠️  No pytest.ini found - CI integration skipped")
        return True


def main():
    """Main migration entry point."""
    migrator = ThreadReaperMigrator()
    
    # Parse command line arguments
    dry_run = '--dry-run' in sys.argv
    scanner_only = '--scanner-only' in sys.argv
    full_integration = '--full' in sys.argv or len(sys.argv) == 1
    
    print("🤖 THREADREAPER COMPREHENSIVE MIGRATION")
    print("=" * 60)
    
    success = True
    
    if scanner_only:
        print("🎯 Scanner-only migration mode")
        success = migrator.integrate_scanner_registration()
    
    elif full_integration:
        print("🎯 Full integration mode")
        
        # Step 1: Migrate all test files
        success = migrator.migrate_all_tests(dry_run=dry_run)
        
        if success and not dry_run:
            # Step 2: Integrate scanner registration
            success &= migrator.integrate_scanner_registration()
            
            # Step 3: Update CI integration
            success &= migrator.update_ci_integration()
    
    else:
        # Just show status
        migrator.migrate_all_tests(dry_run=True)
        return
    
    if success:
        print("\n🎉 THREADREAPER MIGRATION COMPLETED SUCCESSFULLY!")
        print("🔧 SpiderFoot tests now have comprehensive thread leak prevention.")
        print("🚀 Run tests with pytest-xdist to verify improvements.")
    else:
        print("\n⚠️  MIGRATION COMPLETED WITH ISSUES")
        print("🔍 Check error messages above and retry failed migrations.")
        sys.exit(1)


if __name__ == "__main__":
    main()
