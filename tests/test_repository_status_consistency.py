from scripts.check_repository_status_consistency import main

def test_repository_status_consistency_passes():
    assert main() == 0
