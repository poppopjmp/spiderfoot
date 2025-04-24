import pytest

def pytest_configure():
    pass

def pytest_unconfigure():
    pass

@pytest.fixture(scope='session')
def common_setup():
    pass

@pytest.fixture
def setup_module():
    pass

@pytest.fixture
def teardown_module():
    pass