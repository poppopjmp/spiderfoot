"""
Filesystem fixtures for SpiderFoot tests.
Provides temporary directories and file system mocks.
"""
import tempfile
import pytest
from unittest.mock import patch, mock_open

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def mock_file_read():
    """Mock open() for reading files with dummy data."""
    with patch('builtins.open', mock_open(read_data='dummy data')) as m:
        yield m

@pytest.fixture
def mock_os_remove():
    """Mock os.remove to prevent actual file deletion."""
    with patch('os.remove') as m:
        yield m

@pytest.fixture
def mock_os_path_exists():
    """Mock os.path.exists to always return True."""
    with patch('os.path.exists', return_value=True) as m:
        yield m

@pytest.fixture
def mock_os_makedirs():
    """Mock os.makedirs to prevent actual directory creation."""
    with patch('os.makedirs') as m:
        yield m

@pytest.fixture
def mock_os_listdir():
    """Mock os.listdir to return a fixed list of files."""
    with patch('os.listdir', return_value=['file1.txt', 'file2.txt']) as m:
        yield m

@pytest.fixture
def mock_shutil_copyfile():
    """Mock shutil.copyfile to prevent actual file copying."""
    with patch('shutil.copyfile') as m:
        yield m

@pytest.fixture
def mock_os_rename():
    """Mock os.rename to prevent actual file renaming."""
    with patch('os.rename') as m:
        yield m

@pytest.fixture
def mock_os_chmod():
    """Mock os.chmod to prevent actual permission changes."""
    with patch('os.chmod') as m:
        yield m

@pytest.fixture
def mock_os_stat():
    """Mock os.stat to return a dummy stat result."""
    class DummyStat:
        st_mode = 0o777
        st_ino = 0
        st_dev = 0
        st_nlink = 1
        st_uid = 1000
        st_gid = 1000
        st_size = 1024
        st_atime = 0
        st_mtime = 0
        st_ctime = 0
    with patch('os.stat', return_value=DummyStat()) as m:
        yield m

@pytest.fixture
def mock_os_symlink():
    """Mock os.symlink to prevent actual symlink creation."""
    with patch('os.symlink') as m:
        yield m

@pytest.fixture
def mock_os_rmdir():
    """Mock os.rmdir to prevent actual directory removal."""
    with patch('os.rmdir') as m:
        yield m

@pytest.fixture
def mock_os_walk():
    """Mock os.walk to return a fixed directory structure."""
    with patch('os.walk', return_value=[('/tmp', ['subdir'], ['file1.txt', 'file2.txt'])]) as m:
        yield m

@pytest.fixture
def mock_os_getcwd():
    """Mock os.getcwd to return a fixed directory path."""
    with patch('os.getcwd', return_value='/mocked/path') as m:
        yield m

@pytest.fixture
def mock_os_environ():
    """Mock os.environ to provide a controlled environment dict."""
    with patch.dict('os.environ', {'SPIDERFOOT_ENV': 'test'}, clear=True):
         yield
