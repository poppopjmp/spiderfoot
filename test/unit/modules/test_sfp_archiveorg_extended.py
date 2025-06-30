import unittest
from unittest.mock import MagicMock, patch
from modules.sfp_archiveorg import sfp_archiveorg
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent

class TestModuleArchiveorgExtended(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({})
        self.module = sfp_archiveorg()
        self.default_opts = {
            'farback': '1',
            'intfiles': True,
            'passwordpages': True,
            'formpages': True,
            'flashpages': True,
            'javapages': True,
            'staticpages': True,
            'uploadpages': True,
            'webframeworkpages': True,
            'javascriptpages': True,
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTest',
        }
        self.module.setup(self.sf, self.default_opts)
        self.module.__class__.__name__ = 'sfp_archiveorg'

    def _run_event(self, event_type, event_data='example.com', response=None):
        evt = SpiderFootEvent(event_type, event_data, 'sfp_archiveorg', None)
        if response is not None:
            self.sf.fetchUrl = MagicMock(return_value=response)
        else:
            self.sf.fetchUrl = MagicMock(return_value={'content': None})
        with patch.object(self.module, 'notifyListeners') as mock_notify:
            self.module.handleEvent(evt)
            return mock_notify

    def test_event_emission_for_all_types(self):
        event_types = [
            'INTERESTING_FILE', 'URL_PASSWORD', 'URL_FORM', 'URL_FLASH',
            'URL_STATIC', 'URL_JAVA_APPLET', 'URL_UPLOAD', 'URL_WEB_FRAMEWORK', 'URL_JAVASCRIPT'
        ]
        fake_response = {
            'content': '{"archived_snapshots": {"closest": {"url": "https://web.archive.org/web/20210101000000/example.com"}}}'
        }
        for event_type in event_types:
            # Re-instantiate plugin for each event type to reset results
            module = sfp_archiveorg()
            module.setup(self.sf, self.default_opts)
            mock_notify = None
            evt = SpiderFootEvent(event_type, 'example.com', 'sfp_archiveorg', None)
            self.sf.fetchUrl = MagicMock(return_value=fake_response)
            with patch.object(module, 'notifyListeners') as mock_notify:
                module.handleEvent(evt)
                # Print actual event types and module names for debugging
                for call_args in mock_notify.call_args_list:
                    print('Emitted:', call_args[0][0].eventType, call_args[0][0].module)
                self.assertTrue(any(event_type + '_HISTORIC' == call_args[0][0].eventType for call_args in mock_notify.call_args_list))

    def test_option_filtering(self):
        # Disable all options, no events should be emitted
        opts = self.default_opts.copy()
        for key in ['intfiles', 'passwordpages', 'formpages', 'flashpages', 'javapages', 'staticpages', 'uploadpages', 'webframeworkpages', 'javascriptpages']:
            opts[key] = False
        self.module.setup(self.sf, opts)
        event_types = [
            'INTERESTING_FILE', 'URL_PASSWORD', 'URL_FORM', 'URL_FLASH',
            'URL_STATIC', 'URL_JAVA_APPLET', 'URL_UPLOAD', 'URL_WEB_FRAMEWORK', 'URL_JAVASCRIPT'
        ]
        fake_response = {
            'content': '{"archived_snapshots": {"closest": {"url": "https://web.archive.org/web/20210101000000/example.com"}}}'
        }
        for event_type in event_types:
            mock_notify = self._run_event(event_type, response=fake_response)
            self.assertEqual(len(mock_notify.call_args_list), 0)

    def test_error_handling_malformed_json(self):
        fake_response = {'content': '{not json}'}
        mock_notify = self._run_event('INTERESTING_FILE', response=fake_response)
        self.assertEqual(len(mock_notify.call_args_list), 0)

    def test_error_handling_no_snapshots(self):
        fake_response = {'content': '{"archived_snapshots": {}}'}
        mock_notify = self._run_event('INTERESTING_FILE', response=fake_response)
        self.assertEqual(len(mock_notify.call_args_list), 0)

    def test_error_handling_fetch_error(self):
        mock_notify = self._run_event('INTERESTING_FILE', response={'content': None})
        self.assertEqual(len(mock_notify.call_args_list), 0)

if __name__ == '__main__':
    unittest.main()
