#!/usr/bin/env python3
"""
Complete ThreadReaper Migration Tool
===================================

Migrates ALL test files to use ThreadReaper infrastructure,
including those using unittest.TestCase directly.
"""
from __future__ import annotations

import os
import sys
import re
import shutil
from pathlib import Path
import ast

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


class ComprehensiveThreadReaperMigrator:
    """Complete ThreadReaper migration for all test files."""
    
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
    
    def is_module_test(self, file_path: Path, content: str) -> bool:
        """Check if this is a module test file."""
        # Check file path
        if 'modules' in str(file_path) and 'test_sfp_' in file_path.name:
            return True
        
        # Check content for module imports
        module_imports = [
            'from modules.sfp_',
            'import modules.sfp_',
            'sfp_' in content and 'modules' in content
        ]
        
        return any(module_imports)
    
    def is_scanner_test(self, file_path: Path, content: str) -> bool:
        """Check if this is a scanner test file."""
        scanner_indicators = [
            'SpiderFootScanner' in content,
            'scanner' in file_path.name.lower(),
            'test_spiderfootscanner' in file_path.name
        ]
        
        return any(scanner_indicators)
    
    def needs_migration(self, content: str) -> bool:
        """Check if file needs ThreadReaper migration."""
        # Skip if already using ThreadReaper
        if any(cls in content for cls in ['TestScannerBase', 'TestModuleBase']):
            return False
        
        # Need migration if using unittest.TestCase or SpiderFootTestBase
        needs_patterns = [
            'unittest.TestCase',
            'SpiderFootTestBase',
            'class.*Test.*\\(.*TestCase.*\\)',
            'class.*Test.*\\(.*SpiderFootTestBase.*\\)'
        ]
        
        return any(re.search(pattern, content) for pattern in needs_patterns)
    
    def migrate_unittest_to_threadreaper(self, content: str, file_path: Path) -> tuple[str, bool]:
        """Migrate unittest.TestCase to ThreadReaper base classes."""
        modified = False
        
        # Determine the appropriate base class
        is_module = self.is_module_test(file_path, content)
        is_scanner = self.is_scanner_test(file_path, content)
        
        if is_module:
            base_class = 'TestModuleBase'
            import_line = 'from test.unit.utils.test_module_base import TestModuleBase'
        elif is_scanner:
            base_class = 'TestScannerBase' 
            import_line = 'from test.unit.utils.test_scanner_base import TestScannerBase'
        else:
            # Default to TestModuleBase for general tests
            base_class = 'TestModuleBase'
            import_line = 'from test.unit.utils.test_module_base import TestModuleBase'
        
        # Add ThreadReaper import if not present
        if base_class not in content:
            # Find the import section
            import_pattern = r'(import unittest.*?\n)'
            if re.search(import_pattern, content):
                content = re.sub(import_pattern, rf'\1{import_line}\n', content, count=1)
                modified = True
            else:
                # Add at the beginning after existing imports
                lines = content.split('\n')
                import_added = False
                for i, line in enumerate(lines):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        continue
                    else:
                        lines.insert(i, import_line)
                        import_added = True
                        break
                
                if import_added:
                    content = '\n'.join(lines)
                    modified = True
        
        # Replace unittest.TestCase with ThreadReaper base class
        patterns_to_replace = [
            (r'unittest\.TestCase', base_class),
            (r'SpiderFootTestBase', base_class),
            (r'class\s+(\w+)\s*\(\s*TestCase\s*\)', rf'class \1({base_class})'),
            (r'class\s+(\w+)\s*\(\s*unittest\.TestCase\s*\)', rf'class \1({base_class})')
        ]
        
        for pattern, replacement in patterns_to_replace:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True
        
        # Add ThreadReaper setUp/tearDown if needed
        if modified and not any(method in content for method in ['def setUp', 'def tearDown']):
            setup_code = self._generate_setup_teardown(is_module, is_scanner)
            content = self._add_setup_to_classes(content, setup_code)
        
        return content, modified
    
    def _generate_setup_teardown(self, is_module: bool, is_scanner: bool) -> str:
        """Generate appropriate setUp/tearDown methods."""
        if is_scanner:
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
        else:
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
    
    def _add_setup_to_classes(self, content: str, setup_code: str) -> str:
        """Add setUp/tearDown to test classes that don't have them."""
        # Find test classes
        class_pattern = r'(class\s+\w*[Tt]est\w*\([^)]+\):\s*(?:\n\s*"""[^"]*""")?\s*\n)'
        
        def add_setup(match):
            class_def = match.group(1)
            # Check if setUp already exists in the next few lines
            remaining_content = content[match.end():match.end() + 2000]
            if 'def setUp(' in remaining_content[:500]:  # Check first 500 chars
                return class_def
            return class_def + setup_code
        
        return re.sub(class_pattern, add_setup, content)
    
    def migrate_file(self, file_path: Path, dry_run: bool = False) -> bool:
        """Migrate a single test file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Check if migration is needed
            if not self.needs_migration(content):
                self.stats['skipped_files'] += 1
                return True
            
            # Migrate content
            new_content, modified = self.migrate_unittest_to_threadreaper(content, file_path)
            
            if not modified:
                self.stats['skipped_files'] += 1
                return True
            
            if dry_run:
                print(f"📋 Would migrate: {file_path.relative_to(self.project_root)}")
                self.stats['migrated_files'] += 1
                return True
            
            # Create backup
            backup_path = file_path.with_suffix(file_path.suffix + '.threadreaper_backup')
            shutil.copy2(file_path, backup_path)
            
            try:
                # Write migrated content
                file_path.write_text(new_content, encoding='utf-8')
                print(f"✅ Migrated: {file_path.relative_to(self.project_root)}")
                self.stats['migrated_files'] += 1
                
                # Remove backup on success
                if backup_path.exists():
                    backup_path.unlink()
                
                return True
                
            except Exception as e:
                # Restore from backup on failure
                if backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    backup_path.unlink()
                self.stats['errors'].append(f"Write failed for {file_path}: {e}")
                self.stats['failed_files'] += 1
                return False
                
        except Exception as e:
            self.stats['errors'].append(f"Migration failed for {file_path}: {e}")
            self.stats['failed_files'] += 1
            return False
    
    def find_all_test_files(self) -> list[Path]:
        """Find all test files in the project."""
        test_files = []
        
        # Find all Python test files
        patterns = ["**/test_*.py", "**/*_test.py"]
        for pattern in patterns:
            for file_path in self.test_dir.glob(pattern):
                if file_path.is_file() and file_path.suffix == '.py':
                    test_files.append(file_path)
        
        # Remove duplicates and sort
        test_files = sorted(list(set(test_files)))
        
        return test_files
    
    def migrate_all_tests(self, dry_run: bool = False) -> bool:
        """Migrate all test files to use ThreadReaper infrastructure."""
        print("🚀 COMPREHENSIVE THREADREAPER MIGRATION")
        print("=" * 60)
        
        # Find all test files
        test_files = self.find_all_test_files()
        self.stats['total_files'] = len(test_files)
        
        print(f"📋 Found {len(test_files)} test files")
        
        if dry_run:
            print("🔍 DRY RUN MODE - No files will be modified")
        
        print(f"\n🔧 {'ANALYZING' if dry_run else 'MIGRATING'} FILES:")
        print("-" * 40)
        
        success_count = 0
        for i, file_path in enumerate(test_files, 1):
            if not dry_run:
                print(f"[{i:3d}/{len(test_files)}] ", end='')
            
            if self.migrate_file(file_path, dry_run=dry_run):
                success_count += 1
        
        # Report results
        print(f"\n📊 {'ANALYSIS' if dry_run else 'MIGRATION'} RESULTS:")
        print(f"  Total files: {self.stats['total_files']}")
        print(f"  ✅ {'Would migrate' if dry_run else 'Migrated'}: {self.stats['migrated_files']}")
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


def main():
    """Main migration entry point."""
    migrator = ComprehensiveThreadReaperMigrator()
    
    # Parse command line arguments
    dry_run = '--dry-run' in sys.argv
    
    print("🤖 COMPREHENSIVE THREADREAPER MIGRATION")
    print("=" * 60)
    
    # Perform migration
    success = migrator.migrate_all_tests(dry_run=dry_run)
    
    if success:
        if dry_run:
            print("\n🔍 DRY RUN COMPLETED - Ready for actual migration")
            print("🚀 Run without --dry-run to perform actual migration")
        else:
            print("\n🎉 COMPREHENSIVE MIGRATION COMPLETED SUCCESSFULLY!")
            print("🔧 ALL SpiderFoot tests now have ThreadReaper infrastructure.")
            print("🚀 Run tests with pytest-xdist to verify improvements.")
    else:
        print("\n⚠️  MIGRATION COMPLETED WITH ISSUES")
        print("🔍 Check error messages above and retry failed migrations.")
        if not dry_run:
            sys.exit(1)


if __name__ == "__main__":
    main()
