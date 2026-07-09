from pathlib import Path

from ml.prepare_plantnet_subset import sanitize_species_name


def test_sanitize_species_name():
    assert sanitize_species_name("Ficus lyrata") == "Ficus_lyrata"
    assert sanitize_species_name("Monstera deliciosa (L.)") == "Monstera_deliciosa_L"
    assert sanitize_species_name("  Sansevieria trifasciata  ") == "Sansevieria_trifasciata"
