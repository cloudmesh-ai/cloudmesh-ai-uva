import pytest
from cloudmesh.ai.uva import Uva

def test_get_default_partition_global(monkeypatch):
    # Mock the partitions.yaml data
    mock_data = {
        'cloudmesh': {
            'ai': {
                'dafault': {
                    'partition': 'cloudmesh.ai.partition.uva.a100-dgx'
                },
                'partition': {
                    'uva': {
                        'a100-dgx': {'partition': 'gpu'},
                        'v100': {'partition': 'gpu'}
                    }
                }
            }
        }
    }
    
    # We need to mock the loading of the yaml file in Uva.__init__
    # Since Uva reads the file directly, we can mock the open call or 
    # just manually set the attributes after initialization.
    uva = Uva()
    uva.ai_config = mock_data['cloudmesh']['ai']
    uva.directive = mock_data['cloudmesh']['ai']['partition']
    
    default = uva.get_default_partition('uva')
    assert default == 'a100-dgx', f"Expected 'a100-dgx', got {default}"

def test_get_partition_table_data_asterisk(monkeypatch):
    mock_data = {
        'cloudmesh': {
            'ai': {
                'dafault': {
                    'partition': 'cloudmesh.ai.partition.uva.a100-dgx'
                },
                'partition': {
                    'uva': {
                        'a100-dgx': {'partition': 'gpu'},
                        'v100': {'partition': 'gpu'}
                    }
                }
            }
        }
    }
    
    uva = Uva()
    uva.ai_config = mock_data['cloudmesh']['ai']
    uva.directive = mock_data['cloudmesh']['ai']['partition']
    
    header, choices = uva.get_partition_table_data('uva')
    
    # Find the row for a100-dgx
    a100_row = next((c for c in choices if c['value'] == 'a100-dgx'), None)
    v100_row = next((c for c in choices if c['value'] == 'v100'), None)
    
    assert a100_row is not None
    assert v100_row is not None
    
    # The first column (Default) should have '*' for a100-dgx and ' ' for v100
    assert a100_row['name'].startswith('*'), f"Expected a100-dgx row to start with '*', got {a100_row['name']}"
    assert not v100_row['name'].startswith('*'), f"Expected v100 row NOT to start with '*', got {v100_row['name']}"

def test_get_default_partition_host_specific(monkeypatch):
    mock_data = {
        'cloudmesh': {
            'ai': {
                'dafault': {
                    'partition': 'cloudmesh.ai.partition.uva.a100-dgx'
                },
                'partition': {
                    'uva': {
                        'default': {'partition': 'v100'},
                        'a100-dgx': {'partition': 'gpu'},
                        'v100': {'partition': 'gpu'}
                    }
                }
            }
        }
    }
    
    uva = Uva()
    uva.ai_config = mock_data['cloudmesh']['ai']
    uva.directive = mock_data['cloudmesh']['ai']['partition']
    
    default = uva.get_default_partition('uva')
    assert default == 'v100', f"Expected host-specific default 'v100', got {default}"