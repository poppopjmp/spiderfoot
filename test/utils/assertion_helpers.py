"""
Custom assertion helpers for SpiderFoot tests.
"""
def assert_lists_equal_ignore_order(list1, list2):
    assert sorted(list1) == sorted(list2)
