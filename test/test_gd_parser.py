import unittest
from gdf_parser import GDFParser
from nose.tools.nontrivial import raises


class TestGDFParser(unittest.TestCase):
    def test_hms_to_seconds(self):
        self.parser = GDFParser()
        assert self.parser.hms_to_seconds("") == 0
        assert self.parser.hms_to_seconds("00:00.00") == 0
        assert self.parser.hms_to_seconds("00:00.10") == 10
        assert self.parser.hms_to_seconds("00:01.00") == 60
        assert self.parser.hms_to_seconds("01:00.00") == 3600
        assert self.parser.hms_to_seconds("01:01.10") == 3670
        assert self.parser.hms_to_seconds("00.00") == 0
        assert self.parser.hms_to_seconds("00.10") == 10
        assert self.parser.hms_to_seconds("01.00") == 60
        assert self.parser.hms_to_seconds("01.10") == 70
        assert self.parser.hms_to_seconds("01.10") == 70
        pass

    @raises(ValueError)
    def test_hms_to_seconds_exc(self):
        self.parser = GDFParser()
        self.parser.hms_to_seconds("01:10")
