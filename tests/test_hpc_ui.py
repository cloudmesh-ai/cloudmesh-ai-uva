import pytest
from cloudmesh.ai.uva import Uva

def test_get_default_partition():
    uva = Uva()
    # Test with default host 'uva'
    default = uva.get_default_partition("uva")
    assert default is not None
    # If 'default' key exists in partitions.yaml, it should return 'default'
    if "default" in uva.directive.get("uva", {}):
        assert default == "default"

def test_get_partition_table_data():
    uva = Uva()
    header, choices = uva.get_partition_table_data("uva")
    
    assert header is not None
    assert isinstance(choices, list)
    assert len(choices) > 0
    
    # Verify choice structure
    first_choice = choices[0]
    assert "name" in first_choice
    assert "value" in first_choice
    assert isinstance(first_choice["value"], str)
    
    # Verify header contains 'Key'
    assert "Key" in header

def test_get_partition_table_data_invalid_host():
    uva = Uva()
    header, choices = uva.get_partition_table_data("non_existent_host")
    assert header is None
    assert choices is None

def test_get_default_partition_invalid_host():
    uva = Uva()
    default = uva.get_default_partition("non_existent_host")
    assert default is None