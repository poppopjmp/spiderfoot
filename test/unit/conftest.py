import pytest


@pytest.fixture
def default_options():
    """
    Provides default options for SpiderFootScanner tests.
    """
    return {
        '__modules__': {},
        '_socks1type': '',
        '_socks2addr': '',
        '_socks3port': '',
        '_socks4user': '',
        '_socks5pwd': '',
        'modulesenabled': '',
        'maxthreads': '10',
        'maxresults': '1000',
        'maxscancshifts': '',
        'logsize': '10',
        'cors_origins': '',
    }
