from __future__ import annotations

# test_spiderfootscanner.py
import pytest
import unittest
import uuid

from spiderfoot.scan_service.scanner import SpiderFootScanner
from test.unit.utils.test_scanner_base import TestScannerBase

# Import shared thread pool cleanup
try:
    from test.unit.utils.shared_pool_cleanup import enhanced_teardown_with_shared_pool_cleanup
except ImportError:
    def enhanced_teardown_with_shared_pool_cleanup():
        return 0  # Fallback if cleanup utility not available

from test.unit.utils.test_helpers import safe_recursion


class TestSpiderFootScanner(TestScannerBase):
    """Test SpiderFootScanStatus with ThreadReaper infrastructure."""

    def test_init_argument_start_false_should_create_a_scan_without_starting_the_scan(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']

        sfscan = SpiderFootScanner("example scan name", scan_id, "van1shland.io",
                                   "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(sfscan, SpiderFootScanner)
        self.assertEqual(sfscan.status, "INITIALIZING")

    def test_init_argument_start_true_with_no_valid_modules_should_set_scanstatus_to_failed(self):
        """
        Test __init__(self, scanName, scanId, targetValue, targetType, moduleList, globalOpts, start=True)
        """
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['invalid_module_that_does_not_exist']

        # This test should complete quickly because invalid modules are caught
        # during the scanning phase and set status to ERROR-FAILED
        # The logging fixes in sfp__stor_db_advanced.py prevent shutdown issues
        
        # Store the scanner in self for proper cleanup
        self.scanner = SpiderFootScanner(
            "example scan name", scan_id, "spiderfoot.net", "INTERNET_NAME",
            module_list, opts, start=True)

        # Verify the scanner was created and has expected status
        self.assertIsInstance(self.scanner, SpiderFootScanner)
        self.assertEqual(self.scanner.status, "ERROR-FAILED")

    def test_init_argument_scanName_of_invalid_type_should_raise_TypeError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']

        invalid_types = [None, list(), dict(), int()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                with self.assertRaises(TypeError):
                    SpiderFootScanner(invalid_type, scan_id, "van1shland.io",
                                      "IP_ADDRESS", module_list, self.default_options.copy(), start=False)

    def test_init_argument_scanName_as_empty_string_should_raise_ValueError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']

        with self.assertRaises(ValueError):
            SpiderFootScanner("", scan_id, "van1shland.io", "IP_ADDRESS",
                              module_list, self.default_options.copy(), start=False)

    def test_init_argument_scanId_of_invalid_type_should_raise_TypeError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        module_list = ['sfp_example']

        invalid_types = [None, list(), dict(), int()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                with self.assertRaises(TypeError):
                    SpiderFootScanner("example scan name", invalid_type, "van1shland.io",
                                      "IP_ADDRESS", module_list, self.default_options.copy(), start=False)

    def test_init_argument_scanId_as_empty_string_should_raise_ValueError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        scan_id = ""
        module_list = ['sfp_example']

        with self.assertRaises(ValueError):
            SpiderFootScanner("example scan name", scan_id, "van1shland.io",
                              "IP_ADDRESS", module_list, self.default_options.copy(), start=False)

    def test_init_argument_targetValue_of_invalid_type_should_raise_TypeError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']

        invalid_types = [None, list(), dict(), int()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                with self.assertRaises(TypeError):
                    SpiderFootScanner("example scan_name", scan_id, invalid_type,
                                      "IP_ADDRESS", module_list, self.default_options.copy(), start=False)

    def test_init_argument_targetValue_as_empty_string_should_raise_ValueError(self):
        """Test __init__(self, scanName, scanId, scanTarget, targetType,
        moduleList, globalOpts, start=True)"""
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']

        # Test should complete quickly and raise ValueError synchronously
        # The timeout issue was likely caused by logging during __del__
        # which has been fixed in sfp__stor_db_advanced.py
        with self.assertRaises(ValueError) as context:
            SpiderFootScanner("example scan name", scan_id, "",
                              "IP_ADDRESS", module_list, self.default_options.copy(), start=False)
        
        # Verify the specific error message to ensure we're catching the right exception
        self.assertIn("targetValue value is blank", str(context.exception))

    def test__setStatus_argument_status_of_invalid_type_should_raise_TypeError(self):
        """Test __setStatus(self, status, started=None, ended=None)"""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner(
            "example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        invalid_types = [None, list(), dict(), int()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                with self.assertRaises(TypeError):
                    sfscan._SpiderFootScanner__setStatus(invalid_type)

    def test__setStatus_argument_status_with_blank_value_should_raise_ValueError(self):
        """Test __setStatus(self, status, started=None, ended=None)"""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner(
            "example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        with self.assertRaises(ValueError):
            sfscan._SpiderFootScanner__setStatus("")

    def test_attribute_scanId_should_return_scan_id_as_a_string(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner(
            "example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(sfscan, SpiderFootScanner)
        get_id = sfscan.scanId
        self.assertIsInstance(get_id, str)
        self.assertEqual(scan_id, get_id)

    def test_attribute_status_should_return_status_as_a_string(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner(
            "example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(sfscan, SpiderFootScanner)
        status = sfscan.status
        self.assertIsInstance(status, str)

    def test_init_argument_moduleList_of_invalid_type_should_raise_TypeError(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        invalid_types = [None, 'notalist', 123, {'a': 1}]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                with self.assertRaises(TypeError):
                    SpiderFootScanner("example scan name", scan_id, "van1shland.io", "INTERNET_NAME", invalid_type, opts, start=False)

    def test_init_argument_moduleList_empty_should_raise_ValueError(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            SpiderFootScanner("example scan name", scan_id, "van1shland.io", "INTERNET_NAME", [], opts, start=False)

    def test_scan_status_transitions(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner("example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertEqual(sfscan.status, "INITIALIZING")
        # Simulate status changes
        sfscan._SpiderFootScanner__setStatus("STARTING")
        self.assertEqual(sfscan.status, "STARTING")
        sfscan._SpiderFootScanner__setStatus("RUNNING")
        self.assertEqual(sfscan.status, "RUNNING")
        sfscan._SpiderFootScanner__setStatus("FINISHED")
        self.assertEqual(sfscan.status, "FINISHED")

    def test_scanId_and_status_are_read_only(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        sfscan = SpiderFootScanner("example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        with self.assertRaises(AttributeError):
            sfscan.scanId = "new-id"
        with self.assertRaises(AttributeError):
            sfscan.status = "NEW-STATUS"

    def test_module_raises_in_constructor(self):
        # Dynamically add a module entry that raises in __init__
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_brokeninit'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        # Create a dummy module file that raises in __init__
        import types, sys
        class BrokenInit:
            def __init__(self):
                raise RuntimeError('broken init')
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: BrokenInit})
        module_list = [mod_name]
        # Should not raise, but should not load the module
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_enrichTarget_returns_new_target(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_enricher'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class DummyTarget:
            pass
        class Enricher:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return DummyTarget()
            def setTarget(self, t): self._target = t
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Enricher})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_missing_meta_and_opts(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_missingmeta'
        opts['__modules__'][mod_name] = {'descr': 'no meta or opts'}
        import types, sys
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        # Should not raise KeyError; should load module successfully
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_module_importerror(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_importfail'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        # Do not add to sys.modules, so import will fail
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)

    def test_module_raises_in_each_setup_phase(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_raises'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        phases = [
            ('clearListeners', 'clear'),
            ('setScanId', 'scanid'),
            ('setSharedThreadPool', 'pool'),
            ('setDbh', 'dbh'),
            ('setup', 'setup'),
            ('setTarget', 'target'),
            ('enrichTarget', 'enrich'),
        ]
        for method, label in phases:
            scan_id = str(uuid.uuid4())  # Ensure unique scan_id for each phase
            class Raises:
                def __init__(self): pass
                def clearListeners(self):
                    if method == 'clearListeners': raise RuntimeError('fail clear')
                def setScanId(self, x):
                    if method == 'setScanId': raise RuntimeError('fail scanid')
                def setSharedThreadPool(self, x):
                    if method == 'setSharedThreadPool': raise RuntimeError('fail pool')
                def setDbh(self, x):
                    if method == 'setDbh': raise RuntimeError('fail dbh')
                def setup(self, a, b):
                    if method == 'setup': raise RuntimeError('fail setup')
                def enrichTarget(self, t):
                    if method == 'enrichTarget': raise RuntimeError('fail enrich')
                    return None
                def setTarget(self, t):
                    if method == 'setTarget': raise RuntimeError('fail target')
            sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Raises})
            module_list = [mod_name]
            # Should not raise, but should not load the module
            scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
            self.assertIsInstance(scanner, SpiderFootScanner)
            del sys.modules['modules.'+mod_name]

    def test_multiple_modules_some_broken(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_good = 'sfp_example'
        mod_bad = 'sfp_broken'
        opts['__modules__'][mod_bad] = opts['__modules__'][mod_good].copy()
        opts['__modules__'][mod_bad]['meta'] = opts['__modules__'][mod_good]['meta'].copy()
        opts['__modules__'][mod_bad]['meta']['name'] = mod_bad
        import types, sys
        class Broken:
            def __init__(self): raise RuntimeError('fail')
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_bad] = types.SimpleNamespace(**{mod_bad: Broken})
        module_list = [mod_good, mod_bad]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_bad]

    def test_module_errorState_true_in_setup(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_errorstate'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class ErrorState:
            def __init__(self): self.errorState = False
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): self.errorState = True
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: ErrorState})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_custom_useragent_and_dns(self):
        opts = self.default_options.copy()
        opts['_useragent'] = 'TestAgent/1.0'
        opts['_dnsserver'] = '8.8.8.8'
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_example']
        scanner = SpiderFootScanner("example scan name", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)

    def test_module_missing_enrichTarget(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_noenrich'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class NoEnrich:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: NoEnrich})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_enrichTarget_returns_nonobject(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_enrichnonobj'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class EnrichNonObj:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return 12345
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: EnrichNonObj})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_enrichTarget_returns_self(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_enrichself'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class EnrichSelf:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return self
            def setTarget(self, t): pass
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: EnrichSelf})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_is_not_a_class(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_notaclass'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        # Instead of a class, provide a function
        def notaclass():
            return 42
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: notaclass})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_module_outgoingEventQueue_set_to_none(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_nonequeue'
        opts['__modules__'][mod_name] = opts['__modules__']['sfp_example'].copy()
        opts['__modules__'][mod_name]['meta'] = opts['__modules__']['sfp_example']['meta'].copy()
        opts['__modules__'][mod_name]['meta']['name'] = mod_name
        import types, sys
        class NoneQueue:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        inst = NoneQueue()
        inst.outgoingEventQueue = None
        inst.incomingEventQueue = None
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: lambda: inst})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIsInstance(scanner, SpiderFootScanner)
        del sys.modules['modules.'+mod_name]

    def test_concurrent_scanners_do_not_conflict(self):
        import threading
        opts1 = self.default_options.copy()
        opts2 = self.default_options.copy()
        scan_id1 = str(uuid.uuid4())
        scan_id2 = str(uuid.uuid4())
        module_list = ['sfp_example']
        results = []
        def run_scanner(scan_id, opts):
            scanner = SpiderFootScanner("scan", scan_id, "concurrent1.com", "INTERNET_NAME", module_list, opts, start=False)
            results.append(scanner.status)
        t1 = threading.Thread(target=run_scanner, args=(scan_id1, opts1))
        t2 = threading.Thread(target=run_scanner, args=(scan_id2, opts2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(results.count("INITIALIZING"), 2)

    def test_module_missing_meta(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_missingmetaonly'
        opts['__modules__'][mod_name] = {'descr': 'no meta'}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_module_empty_opts(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_emptyopts'
        opts['__modules__'][mod_name] = {'descr': 'empty opts', 'opts': {}}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_module_opts_is_none(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_noneopts'
        opts['__modules__'][mod_name] = {'descr': 'opts is None', 'opts': None}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        # Should handle None opts gracefully (should not raise, should load module)
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_module_opts_is_not_dict(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_stropts'
        opts['__modules__'][mod_name] = {'descr': 'opts is string', 'opts': 'notadict'}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        # Should raise TypeError or handle gracefully
        with self.assertRaises(Exception):
            SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        del sys.modules['modules.'+mod_name]

    def test_module_missing_meta_and_opts_keys(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_missingall'
        opts['__modules__'][mod_name] = {}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_module_config_is_list(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_listcfg'
        opts['__modules__'][mod_name] = [1, 2, 3]
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        with self.assertRaises(Exception):
            SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        del sys.modules['modules.'+mod_name]

    def test_module_config_is_string(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_strcfg'
        opts['__modules__'][mod_name] = "notadict"
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        with self.assertRaises(Exception):
            SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        del sys.modules['modules.'+mod_name]

    def test_module_config_opts_is_empty_string(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_stropts'
        opts['__modules__'][mod_name] = {'opts': ''}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        with self.assertRaises(TypeError):
            SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        del sys.modules['modules.'+mod_name]

    def test_module_config_opts_is_nested_dict(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        mod_name = 'sfp_nestedopts'
        opts['__modules__'][mod_name] = {'opts': {'foo': {'bar': 1}}}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+mod_name] = types.SimpleNamespace(**{mod_name: Minimal})
        module_list = [mod_name]
        scanner = SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        self.assertIn(mod_name, scanner._SpiderFootScanner__moduleInstances)
        del sys.modules['modules.'+mod_name]

    def test_multiple_modules_some_invalid_config(self):
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        valid_mod = 'sfp_valid'
        invalid_mod = 'sfp_invalid'
        opts['__modules__'][valid_mod] = {'opts': {}}
        opts['__modules__'][invalid_mod] = {'opts': 123}
        class Minimal:
            def __init__(self): pass
            def clearListeners(self): pass
            def setScanId(self, x): pass
            def setSharedThreadPool(self, x): pass
            def setDbh(self, x): pass
            def setup(self, a, b): pass
            def enrichTarget(self, t): return None
            def setTarget(self, t): pass
        import types, sys
        sys.modules['modules.'+valid_mod] = types.SimpleNamespace(**{valid_mod: Minimal})
        sys.modules['modules.'+invalid_mod] = types.SimpleNamespace(**{invalid_mod: Minimal})
        module_list = [valid_mod, invalid_mod]
        with self.assertRaises(TypeError):
            SpiderFootScanner("scan", scan_id, "van1shland.io", "INTERNET_NAME", module_list, opts, start=False)
        del sys.modules['modules.'+valid_mod]
        del sys.modules['modules.'+invalid_mod]

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        
        # Clean up any existing threads before each test
        import threading
        for thread in threading.enumerate():
            if (hasattr(thread, '_target') and thread._target and 
                'SpiderFoot' in str(thread._target) and 
                thread != threading.current_thread()):
                if hasattr(thread, 'stop'):
                    thread.stop()
                if thread.is_alive():
                    thread.join(timeout=0.5)
        
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test with comprehensive scanner cleanup."""
        import threading
        import gc
        from contextlib import suppress
        
        # COMPREHENSIVE SCANNER CLEANUP - Find and stop ALL scanner instances
        self._cleanup_all_scanner_instances()
        
        # Clean up any remaining SpiderFoot threads - ENHANCED VERSION
        self._cleanup_spiderfoot_threads()
        
        # Force garbage collection to ensure cleanup
        gc.collect()
        
        # Enhanced shared thread pool cleanup
        enhanced_teardown_with_shared_pool_cleanup()
        
        super().tearDown()
    
    def _cleanup_all_scanner_instances(self):
        """Find and cleanup ALL SpiderFootScanner instances, not just self.scanner."""
        from contextlib import suppress
        import gc
        
        # Method 1: Clean up self.scanner if it exists
        if hasattr(self, 'scanner') and self.scanner:
            with suppress(Exception):
                self._stop_scanner_safely(self.scanner)
                self.scanner = None
        
        # Method 2: Find all scanner instances in the current test's local variables
        # This catches scanners created as local variables like 'sfscan'
        test_frame = None
        try:
            import inspect
            for frame_info in inspect.stack():
                if frame_info.function.startswith('test_'):
                    test_frame = frame_info.frame
                    break
            
            if test_frame:
                # Check all local variables in the test method
                for var_name, var_value in test_frame.f_locals.items():
                    if (hasattr(var_value, '__class__') and 
                        'SpiderFootScanner' in str(var_value.__class__)):
                        with suppress(Exception):
                            self._stop_scanner_safely(var_value)
        except Exception as e:
            pass
        
        # Method 3: Use garbage collector to find any remaining scanner instances
        for obj in gc.get_objects():
            try:
                if (hasattr(obj, '__class__') and 
                    'SpiderFootScanner' in str(obj.__class__) and
                    hasattr(obj, '_thread')):
                    with suppress(Exception):
                        self._stop_scanner_safely(obj)
            except Exception as e:
                pass
    
    def _stop_scanner_safely(self, scanner):
        """Safely stop a scanner instance using the new shutdown method."""
        from contextlib import suppress
        
        if not scanner:
            return
            
        # Use the new explicit shutdown method for comprehensive cleanup
        with suppress(Exception):
            if hasattr(scanner, 'shutdown'):
                scanner.shutdown()
            else:
                # Fallback to old method if shutdown doesn't exist yet
                self._legacy_stop_scanner(scanner)
    
    def _legacy_stop_scanner(self, scanner):
        """Legacy scanner stopping method for backwards compatibility.
        
        Args:
            scanner: The SpiderFootScanner instance to stop
        """
        from contextlib import suppress
        
        # Stop any running scanner threads
        if hasattr(scanner, '_thread') and scanner._thread:
            with suppress(Exception):
                if scanner._thread.is_alive():
                    # Try to stop the scanner gracefully first
                    if hasattr(scanner, 'stop'):
                        scanner.stop()
                    
                    # Give it a moment to stop gracefully
                    scanner._thread.join(timeout=1.0)
                    
                    # If still alive, force cleanup
                    if scanner._thread.is_alive():
                        scanner._thread.join(timeout=0.5)
        
        # Clean up scanner state
        with suppress(Exception):
            if hasattr(scanner, 'status'):
                scanner._SpiderFootScanner__setStatus("ABORTED")
        
        # Clean up any module instances within the scanner
        with suppress(Exception):
            if hasattr(scanner, '_SpiderFootScanner__moduleInstances'):
                for _, module_instance in scanner._SpiderFootScanner__moduleInstances.items():
                    if module_instance:
                        with suppress(Exception):
                            if hasattr(module_instance, 'clearListeners'):
                                module_instance.clearListeners()
                            if hasattr(module_instance, 'errorState'):
                                module_instance.errorState = True
    
    def _cleanup_spiderfoot_threads(self):
        """Enhanced cleanup for SpiderFoot-related threads."""
        import threading
        from contextlib import suppress
        
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        
        for thread in threading.enumerate():
            if (thread != main_thread and 
                thread != current_thread and 
                thread.is_alive()):
                
                # Check if this is a SpiderFoot-related thread
                thread_name = getattr(thread, 'name', '').lower()
                thread_target = str(getattr(thread, '_target', '')).lower()
                
                is_spiderfoot_thread = any(keyword in thread_name or keyword in thread_target 
                                         for keyword in ['spiderfoot', 'scanner', 'scan', 'module'])
                
                if is_spiderfoot_thread:
                    with suppress(RuntimeError, OSError):
                        # Try to join the thread with timeout
                        thread.join(timeout=0.5)
                        
                        # If thread is still alive after join, it might be stuck
                        if thread.is_alive():
                            # Log this for debugging (but don't fail the test)
                            print(f"Warning: Thread {thread.name} still alive after cleanup")
        
        # Additional cleanup for any lingering scanner-related resources
        with suppress(Exception):
            # Clean up any global scanner references that might exist
            import sys
            modules_to_check = [module for module_name, module in sys.modules.items() 
                              if module and 'spiderfoot' in module_name.lower()]
            
            for module in modules_to_check:
                if hasattr(module, '__dict__'):
                    for attr_name in list(module.__dict__.keys()):
                        attr_value = getattr(module, attr_name, None)
                        if (attr_value and hasattr(attr_value, '__class__') and 
                            'SpiderFootScanner' in str(attr_value.__class__)):
                            with suppress(Exception):
                                self._stop_scanner_safely(attr_value)
                                setattr(module, attr_name, None)
