import csv
from collections import defaultdict
import re
import os
from numpy import mean
import errno

class GDFParser():
    def __init__(self, app, version, output_dir, ignore_path=""):
        self.builditems = defaultdict()
        self.paths = list()
        self.app = app
        self.version = version
        self.ignore_path = ignore_path
        self.output_dir = output_dir

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
        filename = os.path.join(self.output_dir, "%s_%s" % (app, version))
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
        self.svg = "%s.svg" % filename

    def write_flamegraph_data(self):
        for p in self.paths:
            filename = os.path.join(self.output_dir, "%s_%s_%s" % (app, version, p.trace[0]))
            self.outputfile = open(filename, 'w')
            self.outputfile.write("%s %d\n" % (';'.join(p.trace), p.buildtime))
            self.outputfile.close()
            os.system("cat %s | ../../flamegraphdiff/FlameGraph/flamegraph.pl > %s.svg" % (filename, filename))
            self.svg = "%s.svg" % filename


    def format_name(self, b):
        return b.name[b.name.find('_') + 1:]

    def parse_total_time(self):
        """ A bit hackety-hack to retrieve the calculated total buildtimes from the svg file.
        There may be more elements named 'all' so check for the largest one (which should be the one on the
        bottom of the graph) 
        TODO integrate this with FlameGraph lib """
        with open(self.svg, 'rb') as svgfile:
            str = svgfile.read()
            needle = r"<title>all .* samples"
            results = re.findall(needle, str)
            samples = 0
            for r in results:
                result = re.search('<title>all \((.*) samples', r)
                s = result.group(1).replace(",", "")
                if int(s) > samples:
                    samples = int(s)
            
            self.outputfile = open(os.path.join(self.output_dir, "total_buildtimes.csv"), 'a')
            self.outputfile.write("%s %d\n" % (self.version, samples))
            self.outputfile.close()    
            svgfile.close()

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

def clear_total_time_file(output_dir):
    f = os.path.join(output_dir, "total_buildtimes.csv")
    if os.path.isfile(f):
        with open(f, 'w') as outputfile:
            outputfile.write("")
         

def make_total_time_graph(output_dir):
    with open(os.path.join(output_dir, "total_buildtimes.csv"), 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=' ')
        times = []
        data_str = ""
        label_str = ""
        row_nr = 1
        for row in reader:
            times.append({"version": row[0], "buildtime": row[1]})
            data_str = "%s,['%s', %s]" % (data_str, row[0], row[1])
            label_str = "%s, [%d, '%s']" % (label_str, row_nr, row[0])
            row_nr = row_nr+1
         
        num_x_ticks = len(times)   
        num_y_ticks = 10 
     
    links_str = ""
    for dfg in sorted(os.listdir(output_dir)): 
        if not os.path.isdir(os.path.join(output_dir, dfg)):
            continue
        links_str = "%s\n<a href=\"%s/dfg-set.html\">%s</a><br>" % (links_str, dfg, dfg)
        
        
    graph = """<!DOCTYPE html >
<html>
<head>
    <style type="text/css">
body { font-family: Verdana, Arial, sans-serif; font-size: 12px; }
#placeholder { width: 450px; height: 200px; }
</style>
    
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.3/jquery.flot.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.3/jquery.flot.categories.js"></script>
    <script src="https://raw.githubusercontent.com/markrcote/flot-tickrotor/master/jquery.flot.tickrotor.js"></script>
    <script>
    var d1 = [%DATA%];
 
$(document).ready(function () {
    $.plot($("#placeholder"), [d1], {
        series: {
            bars: {
                show: true,
                barWidth: 0.6,
                align: "center"
            },
            highlightColor: 'rgb(190,232,216)'
        },
        grid: {
            hoverable: true
        },
        xaxis: {
            mode: "categories",
            tickLength: 0,
            rotateTicks: 135
            }
        }
    );

    $("<div id='tooltip'></div>").css({
            position: "absolute",
            display: "none",
            border: "1px solid #fdd",
            padding: "2px",
            "background-color": "#fee",
            opacity: 0.80
        }).appendTo("body");
    
    $("#placeholder").bind("plothover", function (event, pos, item) {
        if (item) {
            var x = item.series.data[item.dataIndex][0],
                y = item.datapoint[1].toFixed(2);
                
                $("#tooltip").html(x + " = " + y)
                    .css({top: item.pageY+5, left: item.pageX+5})
                .fadeIn(200);
        } else {
            $("#tooltip").hide();
        }
    });
});

    
</script>
</head>
<body>
<div id="placeholder"></div>
<br><br>
%LINKS%
</body></html>"""
    graph = graph.replace("%DATA%", data_str)
    graph = graph.replace("%NUMXTICKS%", str(num_x_ticks))
    graph = graph.replace("%NUMYTICKS%", str(num_y_ticks))
    graph = graph.replace("%LABELS%", label_str)
    graph = graph.replace("%LINKS%", links_str)
    
    with open(os.path.join(output_dir, "total_buildtimes.html"), 'w') as outputfile:
        outputfile.write(graph)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise         

if __name__ == "__main__":
    data_dir = "/home/corpaul/workspace/datasets/glib"
    output_dir = "/home/corpaul/workspace/output/buildsysperf/glib"
    app = "glib"
    
    mkdir_p(output_dir)
    clear_total_time_file(output_dir)
    
    for version in sorted(os.listdir(data_dir)):
        if not os.path.isdir(os.path.join(data_dir, version)):
            continue
        ignore_path = "/home/adan/source/rbCode/%s/" % version

        file = "%s/%s/trace1.gdf" % (data_dir, version)
        parser = GDFParser(app, version, output_dir, ignore_path)
        
        svg = "/home/corpaul/workspace/output/buildsysperf/glib/glib_glib-2.24.0.svg"
        parser.parse_file(file)
        parser.parse_total_time()
     
    make_total_time_graph(output_dir)
       

    # generate DFGs
    print "Generating DFGs"
    i = 0
    for version in sorted(os.listdir(data_dir)):
        if i == 0:
            old = version
            i = i + 1
            continue
        new = version
        # make DFG from old, new
        

        filename_old_new = "%s_%s-%s" % (app, old, new)
        filename_new_old = "%s_%s-%s" % (app, new, old)
        filename_diff = "diff_%s" % filename_old_new
        set_directory = os.path.join(output_dir, "%s-set" % filename_diff)
        oldfile = "%s_%s" % (app, old)
        newfile = "%s_%s" % (app, new)
        os.system("cd ../../flamegraphdiff/ && mkdir -p %s" % set_directory)
        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl %s %s | FlameGraph/flamegraph.pl -title='%s' > %s.svg"
                  % (os.path.join(output_dir, newfile), os.path.join(output_dir, oldfile), filename_old_new, os.path.join(set_directory, filename_old_new)))

        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl %s %s | FlameGraph/flamegraph.pl -title='%s'  > %s.svg"
                  % (os.path.join(output_dir, oldfile), os.path.join(output_dir, newfile), filename_new_old, os.path.join(set_directory, filename_new_old)))

        os.system("cd ../../flamegraphdiff/ && FlameGraph/difffolded.pl -d %s %s | FlameGraph/flamegraph.pl -title='%s' > %s.svg"
                  % (os.path.join(output_dir, oldfile), os.path.join(output_dir, newfile), filename_diff, os.path.join(set_directory, filename_diff)))

        os.system("cd ../../flamegraphdiff/ && graphs/generate_dfg_report.sh %s.svg %s.svg %s.svg %s"
                  % (filename_old_new, filename_new_old, filename_diff, set_directory))
        print "%s - %s" % (old, new)
        old = version

    make_total_time_graph(output_dir)