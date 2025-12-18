import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import pandas as pd
from datetime import datetime
from ingest_epeat import EPEAHIngester

class TestEPEATIngester:
    @pytest.fixture
    def ingester(self):
        # Dry run with mock inventory
        ing = EPEAHIngester("dummy_conn", dry_run=True)
        ing.inventory = ["latitude 7420", "thinkpad x1 carbon", "macbook pro 14"]
        return ing

    def test_clean_model_name(self, ingester):
        assert ingester.clean_model_name("Latitude 7420!") == "latitude 7420"
        assert ingester.clean_model_name("  MacBook   Pro  ") == "macbook   pro" # Logic in script allows spaces but strips outer

    def test_fuzzy_matching_exact(self, ingester):
        match = ingester.find_best_match("Latitude 7420")
        assert match == "latitude 7420"

    def test_fuzzy_matching_fuzzy(self, ingester):
        # "Latitud 7420" should match "latitude 7420"
        match = ingester.find_best_match("Latitud 7420")
        assert match == "latitude 7420"
        
        # "ThinkPad Carbon" might partial match "thinkpad x1 carbon"
        match = ingester.find_best_match("ThinkPad X1 Carbon Gen 9")
        assert match == "thinkpad x1 carbon"

    def test_validation_normalization(self, ingester):
        data = [
            {"Product Name": "Latitude 7420", "Manufacturer": "Dell", "EPEAT Tier": "Gold"},
            {"Product Name": "Unknown Device", "Manufacturer": "", "EPEAT Tier": "Gold"}, # Missing manufacturer
            {"Product Name": "Bad Tier", "Manufacturer": "Dell", "EPEAT Tier": "Plutonium"} # Invalid Tier
        ]
        df = pd.DataFrame(data)
        valid = ingester.validate_and_normalize(df)
        
        assert len(valid) == 1
        assert valid.iloc[0]['device_model'] == "Latitude 7420"
        assert valid.iloc[0]['epeat_rating'] == "Gold"
        assert ingester.stats['rows_skipped'] == 2

