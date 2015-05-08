import unittest
from gdf_parser import GDFParser
from nose.tools.nontrivial import raises


class TestGDFParser(unittest.TestCase):
    def test_hms_to_seconds(self):
        self.parser = GDFParser("glib", "x.x", "/tmp")
        assert self.parser.hms_to_seconds("") == 0
        assert self.parser.hms_to_seconds("00:00.00") == 0
        assert self.parser.hms_to_seconds("00:00.10") == 100
        assert self.parser.hms_to_seconds("00:01.00") == 1000
        assert self.parser.hms_to_seconds("01:00.00") == 60000
        assert self.parser.hms_to_seconds("01:01.10") == 61100
        assert self.parser.hms_to_seconds("00.00") == 0
        assert self.parser.hms_to_seconds("00.10") == 100
        assert self.parser.hms_to_seconds("01.00") == 1000
        assert self.parser.hms_to_seconds("01.10") == 1100
        pass

    def str_to_buildtime(self):
        self.parser = GDFParser("glib", "x.x", "/tmp")
        assert self.parser.str_to_buildtime("[0:00.25;0:01.00]") == 1.25 

    @raises(ValueError)
    def test_hms_to_seconds_exc(self):
        self.parser = GDFParser("glib", "x.x", "/tmp")
        self.parser.hms_to_seconds("01:10")
