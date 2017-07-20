import os

import pytest
from qordoba.strategies import Extension

@pytest.fixture
def valid_extension():
    filename = 'this.is.a.json'
    assert Extension.find(filename) == "JSON"
