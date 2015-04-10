import csv
from collections import defaultdict
import re
import pprint
import os
from numpy import mean

class GDFParser():
    def __init__(self, app, version, ignore_path=""):
        self.builditems = defaultdict()
        self.paths = list()
        self.app = app
        self.version = version
        self.ignore_path = ignore_path

    def parse_file(self, f):
        self.parse_builditems(f)

        # take averages for build times from all traces
        self.take_averages(f)


        # assume for now all dependencies are the same throughout the different traces for each version

        print "Generating stack traces"
        # calculate all triggered_buildtime
        for b in self.builditems.itervalues():
            # print "\n\n--------------\nbuilding trace for %s" % b.name
            # print "(dependencies: %s)" % b.dependencies
            self.find_deps(b)
            self.reset_is_built()
            self.current_trace_time = 0

        print "Done generating stack traces"
        print "Building directory flame graph..."
        self.write_directory_flamegraph_data()
        print "Done"

        print "Building flamegraphs for each node (this may take a while)"
        # self.write_flamegraph_data()
        print "Done"

    def take_averages(self, f):
        # get path
        dir = os.path.dirname(f)
        for l in os.listdir(dir):
            ext = os.path.splitext(l)[1]
            if ext == ".gdf":
                print "parsing: %s" % os.path.join(dir, l)
                self.parse_builditems(os.path.join(dir, l), True)

        # see if there are other trace files
        # process

    def parse_builditems(self, f, avg=False):
        parsing_depencies = False
        with open(f, 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='|')
            # skip headers
            next(reader)
            for row in reader:
                if row[0] == "edgedef> node1":
                    parsing_depencies = True
                elif not parsing_depencies:
                    self.parse_nodedef(row, avg)
                elif row[6] == "0" and not avg:
                    self.parse_dependencies(row[1], row[0])


    def parse_nodedef(self, r, avg=False):
        if self.ignore_path != "":
            dir = r[9].replace(self.ignore_path, "")
        else:
            dir = r[9]
        # totalelapsedtime:
        bt_total_str = r[14]
        # ownelapsedtime:
        bt_str = r[17]

        # or appending the average buildtime
        if avg:
            if r[0] in self.builditems:
                item = self.builditems[r[0]]
            else:
                print "%s not found in first trace file" % r[0]
                return


            # print "averaging total: %d, %d" % (self.str_to_buildtime(bt_total_str), item.triggered_buildtime)
            item.triggered_buildtime = mean([self.str_to_buildtime(bt_total_str), item.triggered_buildtime])
            # print "averaging total: %d, %d" % (self.str_to_buildtime(bt_str), item.buildtime)
            item.buildtime = mean([self.str_to_buildtime(bt_str), item.buildtime])

        # are we creating a builditem
        else:
            item = BuildItem(r[0])
            item.dir = dir

            item.triggered_buildtime = self.str_to_buildtime(bt_str)
            item.buildtime = self.str_to_buildtime(bt_str)
            self.builditems[r[0]] = item

        return

    def str_to_buildtime(self, bt_str):
        if bt_str == "[]":
            bt = 0
        else:
            bt_hms = bt_str.replace("[", "").replace("]", "").split(";")
            for b in bt_hms:
                bt = self.hms_to_seconds(b)
        return bt

    def parse_dependencies(self, obj, triggers):
        self.builditems[obj].dependencies.append(triggers)

    def find_deps(self, obj):
        self.find_dependencies(obj, [], 0)


    def find_dependencies(self, obj, path, buildtime):
        node_name = self.format_name(obj)
        if obj.is_built:
            path.append(node_name + "(BUILT)")
            self.paths.append(Trace(path, buildtime))
            return
        path.append(node_name)

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
            # let's skip the 'all' node for now.. as the complete flamegraph should represent the all node
            if b.name == "all":
                continue
            if len(b.dependencies) == 0:
                buildtime = b.triggered_buildtime + b.buildtime
            else:
                buildtime = b.buildtime
            node_name = self.format_name(b)
            self.outputfile.write("%s;%s %d\n" % (b.dir.replace("/", ";"), node_name, buildtime))

        self.outputfile.close()
        os.system("cat %s | ../../flamegraphdiff/FlameGraph/flamegraph.pl > %s.svg" % (filename, filename))


    def write_flamegraph_data(self):
        for p in self.paths:
            filename = "../output/%s_%s_%s" % (app, version, p.trace[0])
            self.outputfile = open(filename, 'w')
            self.outputfile.write("%s %d\n" % (';'.join(p.trace), p.buildtime))
            self.outputfile.close()
            os.system("cat %s | ../../flamegraphdiff/FlameGraph/flamegraph.pl > %s.svg" % (filename, filename))


    def format_name(self, b):
        return b.name[b.name.find('_') + 1:]


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
    for version in sorted(os.listdir(datadir)):
        if not os.path.isdir(os.path.join(datadir, version)):
            continue
        ignore_path = "/home/adan/source/rbCode/%s/" % version

        file = "%s/%s/trace1.gdf" % (datadir, version)
        parser = GDFParser(app, version, ignore_path)
        parser.parse_file(file)

    # generate DFGs
    print "Generating DFGs"
    i = 0
    for version in sorted(os.listdir(datadir)):
        if i == 0:
            old = version
            i = i + 1
            continue
        new = version
        # make DFG from old, new
        outputdir = "../buildsysperf/output/"


        filename_old_new = "%s_%s-%s" % (app, old, new)
        filename_new_old = "%s_%s-%s" % (app, new, old)
        filename_diff = "diff_%s" % filename_new_old
        set_directory = os.path.join(outputdir, "%s-set" % filename_diff)
        oldfile = "%s_%s" % (app, old)
        newfile = "%s_%s" % (app, new)
        os.system("cd ../../flamegraphdiff/ && mkdir -p %s" % set_directory)
        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl %s %s | FlameGraph/flamegraph.pl -title='%s' > %s.svg"
                  % (os.path.join(outputdir, newfile), os.path.join(outputdir, oldfile), filename_old_new, os.path.join(set_directory, filename_old_new)))

        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl %s %s | FlameGraph/flamegraph.pl -title='%s'  > %s.svg"
                  % (os.path.join(outputdir, oldfile), os.path.join(outputdir, newfile), filename_new_old, os.path.join(set_directory, filename_new_old)))

        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl -d %s %s | FlameGraph/flamegraph.pl -title='%s' > %s.svg"
                  % (os.path.join(outputdir, oldfile), os.path.join(outputdir, newfile), filename_diff, os.path.join(set_directory, filename_diff)))

        os.system("cd ../../flamegraphdiff/ && graphs/generate_dfg_report.sh %s.svg %s.svg %s.svg %s"
                  % (filename_old_new, filename_new_old, filename_diff, set_directory))
        print "%s - %s" % (old, new)
        old = version


# FlameGraph/difffolded.pl demos/rsync/rsync_v2.txt demos/rsync/rsync_v1.txt | FlameGraph/flamegraph.pl > demos/rsync/rsync_dfg1.svg
# $ FlameGraph/difffolded.pl demos/rsync/rsync_v1.txt demos/rsync/rsync_v2.txt | FlameGraph/flamegraph.pl > demos/rsync/rsync_dfg2.svg
# $ FlameGraph/difffolded.pl -d demos/rsync/rsync_v1.txt demos/rsync/rsync_v2.txt | FlameGraph/flamegraph.pl > demos/rsync/rsync_dfg_diff.svg
