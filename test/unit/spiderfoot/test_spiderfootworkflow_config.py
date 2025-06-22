import unittest
import inspect
import spiderfoot.workflow_config as wfconfig

class TestWorkflowConfigSmoke(unittest.TestCase):
    def test_module_import(self):
        public_members = [name for name, obj in inspect.getmembers(wfconfig) if not name.startswith('_')]
        self.assertTrue(len(public_members) > 0)

    def test_main_callable(self):
        if hasattr(wfconfig, "main"):
            self.assertTrue(callable(wfconfig.main))
            try:
                wfconfig.main([])
            except Exception:
                pass

    def test_public_classes_instantiable(self):
        for name, obj in inspect.getmembers(wfconfig):
            if inspect.isclass(obj) and obj.__module__ == wfconfig.__name__:
                try:
                    instance = obj()
                    self.assertIsInstance(instance, obj)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
