import unittest
from jinja2 import Template
import os


class TestSpiderFootTemplates(unittest.TestCase):
    
    def setUp(self):
        self.template_dir = os.path.join(os.path.dirname(__file__), '../../spiderfoot/templates')

    def render_template(self, template_name, **context):
        template_path = os.path.join(self.template_dir, template_name)
        with open(template_path, 'r') as file:
            template = Template(file.read())
        return template.render(context)

    def test_error_template(self):
        rendered = self.render_template('error.tmpl', error_message='Test Error')
        self.assertIn('Test Error', rendered)

    def test_footer_template(self):
        rendered = self.render_template('FOOTER.tmpl')
        self.assertIn('footer', rendered.lower())

    def test_header_template(self):
        rendered = self.render_template('HEADER.tmpl')
        self.assertIn('header', rendered.lower())

    def test_newscan_template(self):
        rendered = self.render_template('newscan.tmpl')
        self.assertIn('new scan', rendered.lower())

    def test_opts_template(self):
        rendered = self.render_template('opts.tmpl')
        self.assertIn('options', rendered.lower())

    def test_scaninfo_template(self):
        rendered = self.render_template('scaninfo.tmpl')
        self.assertIn('scan info', rendered.lower())

    def test_scanlist_template(self):
        rendered = self.render_template('scanlist.tmpl')
        self.assertIn('scan list', rendered.lower())


if __name__ == '__main__':
    unittest.main()