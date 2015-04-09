import csv
from collections import defaultdict
import re
import pprint
import os


class GDFParser():
    def __init__(self, app, version):
        self.builditems = defaultdict()
        self.paths = list()
        self.app = app
        self.version = version

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
                    self.parse_nodedef(row)
                elif row[6] == "0":
                    self.parse_dependencies(row[1], row[0])

        print "Generating stack traces"
        # calculate all triggered_buildtime
        for b in self.builditems.itervalues():
            print "\n\n--------------\nbuilding trace for %s" % b.name
            print "(dependencies: %s)" % b.dependencies
            # b.tracestring = self.parse_dependencies_trace(b)
            # print self.parse_dependencies_lambda(b)
            self.find_deps(b)
            self.reset_is_built()
            self.current_trace_time = 0




            # print "\n\n----------------\ncalculating triggered buildtime for %s" % b.name
            # b.triggered_buildtime = self.calc_triggered_buildtime(b)
        print "Done generating stack traces"
        print "Building directory flame graph..."
        self.write_directory_flamegraph_data()
        print "Done"

        print "Building flamegraphs for each node (this may take a while)"
        # self.write_flamegraph_data()
        print "Done"



    def parse_nodedef(self, r):
        item = BuildItem(r[0])

        # parse directory:
        dir = r[9]
        item.dir = dir
        print "Dir: %s" % dir
        # totalelapsedtime:
        bt_str = r[14]
        item.triggered_buildtime = self.str_to_buildtime(bt_str)

        # ownelapsedtime:
        bt_str = r[17]

        item.buildtime = self.str_to_buildtime(bt_str)
        self.builditems[r[0]] = item

        return

    def str_to_buildtime(self, bt_str):
        if bt_str == "[]":
            bt = 0
        else:
            print bt_str
            bt_hms = bt_str.replace("[", "").replace("]", "").split(";")
            for b in bt_hms:
                bt = self.hms_to_seconds(b)
        return bt

    def parse_dependencies(self, obj, triggers):
        self.builditems[obj].dependencies.append(triggers)

    def find_deps(self, obj):
        self.find_dependencies(obj, [], 0)


    def find_dependencies(self, obj, path, buildtime):
        if obj.is_built:
            path.append(obj.name + "(BUILT)")
            self.paths.append(Trace(path, buildtime))
            return
        path.append(obj.name)

        if len(obj.dependencies) == 0:
            buildtime = obj.triggered_buildtime + buildtime
            self.paths.append(Trace(path, buildtime))
        else:
            # not sure if buildtimes are 100% correct.. I'd like to use ownelapsedtime everywhere but
            # 'all' requires totalelapsedtime
            buildtime = obj.buildtime + buildtime
            for n in obj.dependencies:
                dep = self.builditems[n]
                self.find_dependencies(dep, list(path), buildtime)
                dep.is_built = True

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

    def write_directory_flamegraph_data(self):
        filename = "../output/%s_%s" % (app, version)
        self.outputfile = open(filename, 'w')

        for b in self.builditems.itervalues():
            if len(b.dependencies) == 0:
                buildtime = b.triggered_buildtime + b.buildtime
            else:
                buildtime = b.buildtime
            self.outputfile.write("%s;%s %d\n" % (b.dir.replace("/", ";"), b.name, buildtime))

        self.outputfile.close()
        os.system("cat %s | ../../flamegraphdiff/FlameGraph/flamegraph.pl > %s.svg" % (filename, filename))


    def write_flamegraph_data(self):
        for p in self.paths:
            filename = "../output/%s_%s_%s" % (app, version, p.trace[0])
            self.outputfile = open(filename, 'w')
            self.outputfile.write("%s %d\n" % (';'.join(p.trace), p.buildtime))
            self.outputfile.close()
            os.system("cat %s | ../../flamegraphdiff/FlameGraph/flamegraph.pl > %s.svg" % (filename, filename))





class BuildItem():
    def __init__(self, name):
        self.name = name
        self.dir = ""
        self.buildtime = 0
        self.triggered_buildtime = -1
        self.dependencies = []
        # self.nodes = []
        self.trace = []
        self.traces_definitive = False
        self.is_built = False

class Trace():
    def __init__(self, trace, buildtime):
        self.trace = trace
        self.buildtime = buildtime

    def __str__(self):
        return "%s (%d)\n" % (self.trace, self.buildtime)


if __name__ == "__main__":
    datadir = "../data/glib"
    app = "glib"
    for x in os.listdir(datadir):
        if not os.path.isdir(os.path.join(datadir, x)):
            continue
        version = x

        file = "%s/%s/trace1.gdf" % (datadir, version)
        parser = GDFParser(app, version)
        parser.parse_file(file)
        # parser.print_dependencies()
