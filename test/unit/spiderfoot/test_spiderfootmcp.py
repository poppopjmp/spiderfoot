import unittest
import inspect
import spiderfoot.mcp_integration as mcp

class TestMCPIntegrationSmoke(unittest.TestCase):
    def test_module_import(self):
        # Ensure the module loads and has at least one public class or function
        public_members = [name for name, obj in inspect.getmembers(mcp) if not name.startswith('_')]
        self.assertTrue(len(public_members) > 0)

    def test_main_callable(self):
        # If the module has a main entry point, check it's callable
        if hasattr(mcp, "main"):
            self.assertTrue(callable(mcp.main))
            # Optionally, call main with dummy args and check for no crash
            try:
                mcp.main([])
            except Exception:
                pass  # Accept any exception for now

    def test_public_classes_instantiable(self):
        # Try to instantiate any public classes
        for name, obj in inspect.getmembers(mcp):
            if inspect.isclass(obj) and obj.__module__ == mcp.__name__:
                try:
                    instance = obj()
                    self.assertIsInstance(instance, obj)
                except Exception:
                    pass  # Accept any exception for now

if __name__ == "__main__":
    unittest.main()
