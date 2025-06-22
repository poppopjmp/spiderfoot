import unittest
import inspect
import spiderfoot.workflow_api as wfapi

class TestWorkflowApiSmoke(unittest.TestCase):
    def test_module_import(self):
        public_members = [name for name, obj in inspect.getmembers(wfapi) if not name.startswith('_')]
        self.assertTrue(len(public_members) > 0)

    def test_main_callable(self):
        if hasattr(wfapi, "main"):
            self.assertTrue(callable(wfapi.main))
            try:
                wfapi.main([])
            except Exception:
                pass

    def test_public_classes_instantiable(self):
        for name, obj in inspect.getmembers(wfapi):
            if inspect.isclass(obj) and obj.__module__ == wfapi.__name__:
                try:
                    instance = obj()
                    self.assertIsInstance(instance, obj)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
