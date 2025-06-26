import os

doc_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'documentation')
expected_files = [
    'overview.md',
    'getting_started.md',
    'installation.md',
    'quickstart.md',
    'configuration.md',
    'user_guide.md',
    'modules.md',
    'api_reference.md',
    'advanced.md',
    'developer_guide.md',
    'faq.md',
    'troubleshooting.md',
]

print('Checking documentation/ for missing files:')
missing = False
for fname in expected_files:
    fpath = os.path.join(doc_folder, fname)
    if not os.path.isfile(fpath):
        print(f'  MISSING: {fname}')
        missing = True
    else:
        print(f'  OK:      {fname}')
if not missing:
    print('All documentation files are present.')
else:
    print('Some documentation files are missing. Please add them to documentation/.')
