import csv
from collections import defaultdict
import re


class GDFParser():
    def __init__(self):
        self.builditems = defaultdict()
        self.outputfile = open("traces", 'w')

    def parse_file(self, f):
        parsing_depencies = False
        with open(f, 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='|')
            # skip headers
            next(reader)
            for row in reader:
                if row[0] == "edgedef> node1":
                    parsing_depencies = True
                elif not parsing_depencies:
                    self.parse_buildtime(row)

                elif row[6] == "0":
                    self.parse_dependencies(row[1], row[0])

        print "Generating stack traces"
        # calculate all triggered_buildtime
        for b in self.builditems.itervalues():
            print "\n\n--------------\nbuilding trace for %s" % b.name
            print "(dependencies: %s)" % b.dependencies
            b.tracestring = self.parse_dependencies_trace(b)
            self.reset_is_built()

            # print "\n\n----------------\ncalculating triggered buildtime for %s" % b.name
            # b.triggered_buildtime = self.calc_triggered_buildtime(b)
        print "Done generating stack traces"
        for b in self.builditems.itervalues():
            print "%s: %d" % (b.name, len(b.tracestring))
            self.outputfile.write("%s \n" % b.tracestring)
            # self.outputfile.write("%s \n" % self.formatted_tracestring(b.tracestring))


    def parse_buildtime(self, r):
        item = BuildItem(r[0])
        bt_str = r[14]
        if bt_str == "[]":
            bt = 0
        else:
            print bt_str
            bt_hms = bt_str.replace("[", "").replace("]", "").split(";")
            for b in bt_hms:
                bt = self.hms_to_seconds(b)
        item.buildtime = bt
        self.builditems[r[0]] = item

        return

    def parse_dependencies(self, obj, triggers):
        self.builditems[obj].dependencies.append(triggers)

    # parse the string containing the 'trace' for build items
    # still broken... check at home again
    def parse_dependencies_trace(self, obj):
        # obj.traces_definitive indicates we have calculated all traces for obj
        # if False we have to calculate them
        if len(obj.dependencies) == 0:
            return [obj.name]
        if not obj.traces_definitive:
            # obj does not have dependencies: leaf of tree
            # store name in obj trace string and return it
            obj.tracestring.append(obj.name)
            for d in obj.dependencies:
                dep = self.builditems[d]
            # obj.tracestring.append(obj.name)
            # trace = obj.name + "->" + self.parse_dependencies_trace(dep)
                dep_deps = self.parse_dependencies_trace(dep)
                if len(dep_deps) > 0:
                    obj.tracestring.append(dep_deps)
            obj.traces_definitive = True
        return obj.tracestring

        # else:
        #    return obj.tracestring
        # obj.traces_definitive = True
        # return ["%s (BUILT ALREADY)" % obj.name]
        # return ["%s" % obj.name]

    # broken
    def calc_triggered_buildtime(self, obj):
        buildtime = 0
        print "calculating dependencies for %s: %s" % (obj.name, obj.dependencies)
        if obj.triggered_buildtime > -1:
            return obj.triggered_buildtime
        for b in obj.dependencies:
            buildtime += self.builditems[b].buildtime
            buildtime += self.calc_triggered_buildtime(self.builditems[b])
        obj.triggered_buildtime = buildtime
        print "triggered buildtime calculated: %d for %s" % (buildtime, obj.name)
        return buildtime

    def reset_is_built(self):
        for b in self.builditems.itervalues():
            b.is_built = False
            # b.traces_definitive = False


    def print_dependencies(self):
        for d in self.builditems.itervalues():
            print "%s (buildtime: %s) triggers: %s (buildtime: %s)" % (d.name, d.buildtime, d.dependencies, d.triggered_buildtime)

    def hms_to_seconds(self, t):
        if t == "":
            return 0

        # 00:00.00 format
        hms_regex = re.compile("^\d{1,2}:\d{2}.\d{2}$")
        ms_regex = re.compile("^\d{1,2}.\d{2}$")
        if hms_regex.match(t):
            h, ms = [str(i) for i in t.split(':')]
            m, s = [str(i) for i in ms.split('.')]
            return 3600 * int(h) + 60 * int(m) + int(s)
        # 0.00 format
        elif ms_regex.match(t):
            m, s = [str(i) for i in t.split('.')]
            return 60 * int(m) + int(s)
        else:
            raise ValueError
            print "Unknown time format: %s (using 0 instead)" % t
            return 0



class BuildItem():
    def __init__(self, name):
        self.name = name
        self.buildtime = 0
        self.triggered_buildtime = -1
        self.dependencies = []
        self.tracestring = []
        self.traces_definitive = False
        self.is_built = False

if __name__ == "__main__":
    filename = "../data/glib/glib-2.24.0/trace1.gdf"
    parser = GDFParser()
    parser.parse_file(filename)
    # parser.print_dependencies()
