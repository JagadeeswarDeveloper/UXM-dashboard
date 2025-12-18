import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import pandas as pd
from datetime import datetime
from ingest_happysignals import HappySignalsIngester

class TestHappySignalsIngester:
    @pytest.fixture
    def ingester(self):
        return HappySignalsIngester("dummy_conn", dry_run=True)

    def test_survey_id_generation_determinism(self, ingester):
        row = {
            'ticket_id': 'INC123',
            'created_date': datetime(2023, 1, 1, 12, 0, 0),
            'respondent_email': 'test@example.com',
            'comment': 'Test comment'
        }
        id1 = ingester.generate_survey_id(row)
        id2 = ingester.generate_survey_id(row)
        assert id1 == id2
        assert id1.startswith("HS-INC123-20230101120000-")

    def test_validation_score_range(self, ingester):
        data = [
            {'Score': 11, 'Ticket': 'A'}, # Invalid
            {'Score': -1, 'Ticket': 'B'}, # Invalid
            {'Score': 5, 'Ticket': 'C'}   # Valid
        ]
        df = pd.DataFrame(data)
        valid_df = ingester.validate_and_normalize(df)
        
        assert len(valid_df) == 1
        assert valid_df.iloc[0]['ticket_id'] == 'C'
        assert ingester.stats['rows_failed'] == 2

    def test_validation_lost_time(self, ingester):
        data = [
            {'Score': 5, 'Lost time': -5}, # Invalid
            {'Score': 5, 'Lost time': 10}  # Valid
        ]
        df = pd.DataFrame(data)
        valid_df = ingester.validate_and_normalize(df)
        
        assert len(valid_df) == 1
        assert valid_df.iloc[0]['lost_time_minutes'] == 10

    def test_email_normalization(self, ingester):
        data = [
            {'Score': 5, 'respondent_email': '  test@example.com  '},
            {'Score': 5, 'respondent_email': 'invalid-email'},
            {'Score': 5, 'respondent_email': None}
        ]
        df = pd.DataFrame(data)
        valid_df = ingester.validate_and_normalize(df)
        
        assert len(valid_df) == 3 # All valid, but email might be None
        assert valid_df.iloc[0]['respondent_email'] == 'test@example.com'
        assert valid_df.iloc[1]['respondent_email'] is None
        assert valid_df.iloc[2]['respondent_email'] is None

    def test_date_parsing(self, ingester):
        data = [
            {'Score': 5, 'Created': '2023-10-01', 'Sent Date': '2023-10-02'}
        ]
        df = pd.DataFrame(data)
        valid_df = ingester.validate_and_normalize(df)
        
        assert isinstance(valid_df.iloc[0]['created_date'], datetime)
        # load_date is date object
        assert valid_df.iloc[0]['load_date'].strftime('%Y-%m-%d') == '2023-10-02'

