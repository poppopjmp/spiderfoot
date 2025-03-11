import unittest
from unittest.mock import patch, MagicMock


class SpiderFootModuleTestCase(unittest.TestCase):
    """
    Base class for SpiderFoot module test cases.
    Handles common test setup and provides default options.
    """

    # Default options for all modules
    default_options = {
        "_debug": False,
        "__logging": True,
        "_datadir": "data",
        "_useragent": "SpiderFoot",
        "_api_key": "test_api_key",
    }

    def setUp(self):
        """Set up test case."""
        self.sf = None
        self.module = None
        self.opts = self.default_options.copy()

        # Create a mock for any logging calls that can be used by subclasses
        self.log_mock = MagicMock()

    def __init__(self, *args, **kwargs):
        super(SpiderFootModuleTestCase, self).__init__(*args, **kwargs)

        # Common options used by module tests
        self.default_options.update(
            {
                "__outputfilter": None,
                "__blocknotif": False,
                "_fatalerrors": False,
                "_useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0",
                "_dnsserver": "",
                "_fetchtimeout": 5,
                "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
                "_internettlds_cache": 72,
                "_genericusers": "abuse,admin,billing,compliance,devnull,dns,ftp,hostmaster,inoc,ispfeedback,ispsupport,list-request,list,maildaemon,marketing,noc,no-reply,noreply,null,peering,peering-notify,peering-request,phish,phishing,postmaster,privacy,registrar,registry,root,routing-registry,rr,sales,security,spam,support,sysadmin,tech,undisclosed-recipients,unsubscribe,usenet,uucp,webmaster,www",
                "__version__": "3.0",
                "__database": "spiderfoot.test.db",
                "_socks1type": "",
                "_socks2addr": "",
                "_socks3port": "",
                "_socks4user": "",
                "_socks5pwd": "",
                "_torctlport": 9051,
                "_password_list": "./spiderfoot/dicts/passwords.txt",
                "_tos_is_acceptable": False,
                "_cache_period": 24,
                "__modules__": {},
            }
        )

    def assertIsOk(self, condition):
        """Assert that the condition evaluates to True."""
        self.assertTrue(
            condition, "Expected condition to be True, but got False")

    def assertEventData(self, event, expected_type, expected_data):
        """Assert that an event has the expected type and data."""
        self.assertEqual(
            event.eventType,
            expected_type,
            f"Expected event type '{expected_type}', but got '{event.eventType}'",
        )
        self.assertEqual(
            event.data,
            expected_data,
            f"Expected event data '{expected_data}', but got '{event.data}'",
        )

    def assertErrorState(self, module, expected_state=True):
        """Assert that the module's error state matches the expected state."""
        self.assertEqual(
            module.errorState,
            expected_state,
            f"Expected module.errorState to be {expected_state}, but got {module.errorState}",
        )

    def setup_module(self, module_class):
        """Set up a module for testing with default options."""
        from sflib import SpiderFoot

        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module, sf

    def generate_event(self, event_type, event_data, module_name="", source_event=None):
        """Generate a SpiderFoot event for testing."""
        from spiderfoot import SpiderFootEvent

        return SpiderFootEvent(event_type, event_data, module_name, source_event)

    def set_module_target(self, module, target_value, target_type="INTERNET_NAME"):
        """Set the target for a module."""
        from spiderfoot import SpiderFootTarget

        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        return target

    def execute_module_test(
        self,
        module_class,
        event_type,
        event_data,
        module_name="test_module",
        target_value="example.com",
        target_type="INTERNET_NAME",
    ):
        """
        Helper method to execute a standard test for a module with the given event.
        Returns the module instance and event after handling.
        """
        from sflib import SpiderFoot

        sf = SpiderFoot(self.default_options)

        module = module_class()
        module.setup(sf, dict())

        target = self.set_module_target(module, target_value, target_type)

        root_event = self.generate_event("ROOT", "root event data")
        evt = self.generate_event(
            event_type, event_data, module_name, root_event)

        return module, module.handleEvent(evt)

    def mock_module_response(self, module, new_response):
        """Modify a module to return a predetermined response."""

        def mock_fetch_url(url, *args, **kwargs):
            return new_response

        module.sf.fetchUrl = mock_fetch_url
        return module

    def capture_module_events(self, module):
        """
        Override a module's notifyListeners method to capture events.
        Returns a list to store events and the new notifyListeners function.
        """
        events = []

        def new_notify_listeners(event):
            events.append(event)

        original_notify = module.notifyListeners
        module.notifyListeners = new_notify_listeners.__get__(
            module, module.__class__)

        return events, original_notify

    def restore_module_notify_listeners(self, module, original_notify):
        """Restore the original notifyListeners method to a module."""
        module.notifyListeners = original_notify

    def assert_module_produces_events_from(
        self, module_class, event_data, expected_types
    ):
        """
        Assert that a module produces events of the expected types when given an event.
        Returns the generated events for further inspection.
        """
        module, sf = self.setup_module(module_class)

        self.set_module_target(module, "example.com")

        events, _ = self.capture_module_events(module)

        root_event = self.generate_event("ROOT", "root event data")
        evt = self.generate_event(
            "LINKED_URL_INTERNAL", event_data, "test_module", root_event
        )

        module.handleEvent(evt)

        # Check that we got the right number of events
        self.assertEqual(
            len(events),
            len(expected_types),
            f"Expected {len(expected_types)} events, got {len(events)}",
        )

        # Check event types
        actual_types = [e.eventType for e in events]
        for expected_type in expected_types:
            self.assertIn(
                expected_type,
                actual_types,
                f"Expected event type {expected_type} not found in {actual_types}",
            )

        return events

    def setup_module_with_mocks(self, module_class):
        """Set up a module for testing with default options and mocked logging."""
        from sflib import SpiderFoot

        sf = SpiderFoot(self.default_options)

        # Use a patch context to create the module
        with patch(
            f"modules.{module_class.__module__}.logging", MagicMock()
        ) as mock_logging:
            module = module_class()
            module.setup(sf, dict())
            return module, sf, mock_logging

    def create_module_with_mocks(self, module_path):
        """Create a module instance with mocked logging."""
        with patch(f"{module_path}.logging", MagicMock()) as mock_logging:
            # Import the module dynamically
            module_name = module_path.split(".")[-1]
            module_class = getattr(
                __import__(module_path, fromlist=[module_name]), module_name
            )
            return module_class(), mock_logging

    def patch_logging_methods(self, test_func):
        """Decorator to patch all logging methods for a test function."""
        patches = [
            patch("logging.Logger.debug"),
            patch("logging.Logger.info"),
            patch("logging.Logger.warning"),
            patch("logging.Logger.error"),
        ]
        for p in patches:
            test_func = p(test_func)
        return test_func

    def setup_module_with_patched_logging(self, module_class):
        """Set up a module for testing with patched logging."""
        from sflib import SpiderFoot

        with (
            patch("logging.Logger.debug"),
            patch("logging.Logger.info"),
            patch("logging.Logger.warning"),
            patch("logging.Logger.error"),
        ):
            sf = SpiderFoot(self.default_options)
            module = module_class()
            module.setup(sf, self.default_options)
            return module, sf

    def setup_test_module(self, module_class):
        """
        Set up a module for testing with patched logging.
        This should be the preferred way to create module instances in tests.
        """
        from sflib import SpiderFoot

        sf = SpiderFoot(self.default_options)

        with patch("logging.getLogger", return_value=self.log_mock):
            module = module_class()
            module.setup(sf, self.default_options)
            return module, sf

    def create_test_module_subclass(self, module_class, init_attributes=None):
        """
        Dynamically create a subclass of the module to test that skips problematic initialization.

        Args:
            module_class: The SpiderFoot module class to subclass
            init_attributes: Dictionary of attributes to set during initialization

        Returns:
            A class that can be instantiated for testing
        """
        if init_attributes is None:
            init_attributes = {}

        # Define the test class
        class TestModuleClass(module_class):
            def __init__(self_inner):
                # Basic attributes needed for all modules
                self_inner.thread = None
                self_inner._log = None
                self_inner.sharedThreadPool = None
                self_inner.__name__ = module_class.__name__
                self_inner.sf = None
                self_inner.errorState = False
                self_inner.results = dict()

                # Copy original opts and optdescs when available
                try:
                    instance = module_class.__new__(module_class)
                    instance.__init__ = lambda *args, **kwargs: None

                    # Try to access attributes without triggering __init__
                    if hasattr(module_class, "opts"):
                        self_inner.opts = module_class.opts.copy()
                    else:
                        self_inner.opts = {}

                    if hasattr(module_class, "optdescs"):
                        self_inner.optdescs = module_class.optdescs.copy()
                    else:
                        self_inner.optdescs = {}
                except Exception:
                    self_inner.opts = {}
                    self_inner.optdescs = {}

                # Set additional attributes
                self_inner.options = None
                self_inner.registry = []

                # Set any custom attributes
                for attr, value in init_attributes.items():
                    setattr(self_inner, attr, value)

        return TestModuleClass

    def create_module_wrapper(
        self, module_class, name_prefix="Sfp", module_attributes=None
    ):
        """
        Create a test-friendly wrapper of a module class that avoids initialization problems.

        Args:
            module_class: The SpiderFoot module class to wrap
            name_prefix: Prefix for the wrapper class name
            module_attributes: Dictionary of additional attributes to set

        Returns:
            A wrapper class that can be instantiated without issues
        """
        if module_attributes is None:
            module_attributes = {}

        class_name = f"{name_prefix}{module_class.__name__.replace('sfp_', '')}Wrapper"

        # Define a proper __init__ that sets up all needed attributes
        def wrapper_init(self):
            self.thread = None
            self._log = None
            self.sharedThreadPool = None
            self.sf = None
            self.results = {}
            self.errorState = False
            # Ensure option-related attributes are properly initialized
            self.opts = {}
            self.optdescs = {}
            self.options = {}
            self.registry = []
            # Now apply all custom attributes
            for attr, value in module_attributes.items():
                setattr(self, attr, value)

        # Define a setup method that properly initializes options
        def wrapper_setup(self, sf, userOpts=dict()):
            """Setup the module properly for testing."""
            self.sf = sf

            # Make sure options is a dictionary
            if not hasattr(self, "options") or self.options is None:
                self.options = {}

            # Ensure opts is a dictionary
            if not hasattr(self, "opts") or self.opts is None:
                self.opts = {}

            # Convert existing options
            try:
                # Convert opts to options
                self.options.update(sf.optValueToData(self.opts))

                # Apply user-provided options
                for opt in userOpts.keys():
                    self.options[opt] = userOpts[opt]
            except Exception as e:
                print(f"Error initializing module options: {e}")
                # At least ensure debug option is set
                self.options["_debug"] = userOpts.get("_debug", False)

        # Create the wrapper class
        wrapper_class = type(
            class_name,
            (module_class,),
            {"__init__": wrapper_init, "setup": wrapper_setup},
        )

        return wrapper_class
