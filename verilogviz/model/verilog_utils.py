# Copyright (c) 2013 Dave McCoy (dave.mccoy@cospandesign.com)
#
# This file is part of Nysa.
#
#       (http://wiki.cospandesign.com/index.php?title=Nysa.org)
#
# Nysa is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# any later version.
#
# Nysa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Nysa; If not, see <http://www.gnu.org/licenses/>.

"""Utilities used to generate and extract information from Verilog cores"""

__author__ = 'dave.mccoy@cospandesign.com (Dave McCoy)'
import os
import sys
import string
import json
import arbiter
import re

import utils
from utils import ModuleError
import preprocessor

def get_eol(total, index):
    if index < total:
        return ","
    return ""


def get_module_buffer_tags(buf, bus = "", keywords = [], user_paths = [], project_tags = {}, debug = False):
    raw_buf = buf
    tags = {}
    tags["keywords"] = {}
    tags["ports"] = {}
    tags["module"] = ""
    tags["parameters"] = {}
    tags["arbiter_masters"] = []

    in_task = False
    end_module = False

    ports = [
        "input",
        "output",
        "inout"
    ]


    #XXX only working with verilog at this time, need to extend to VHDL
    #print "filename: %s" % filename

    #find all the metadata
    for key in keywords:
        index = buf.find (key)
        if (index == -1):
            if debug:
                print "didn't find substring for " + key
            continue
        if debug:
          print "found substring for " + key

        substring = buf.__getslice__(index, len(buf)).splitlines()[0]
        if debug:
            print "substring: " + substring


        if debug:
            print "found " + key + " substring: " + substring

        substring = substring.strip()
        substring = substring.strip("//")
        substring = substring.strip("/*")
        tags["keywords"][key] = substring.partition(":")[2]



    #remove all the comments from the code
    buf = utils.remove_comments(buf)
    #print "no comments: \n\n" + buf

    for substring in buf.splitlines():
        if (len(substring.partition("module")[1]) == 0):
            continue
        module_string = substring.partition("module")[2]
        module_string = module_string.strip(" ")
        module_string = module_string.strip("(")
        module_string = module_string.strip("#")
        index = module_string.find(" ")

        if (index != -1):
            tags["module"] = module_string.__getslice__(0, index)
        else:
            tags["module"] = module_string

        if debug:
            print "module name: " + module_string
            print tags["module"]
        break

    #find all the ports
    #find the index of all the processing block
    substrings = buf.splitlines()

    input_count = buf.count("input")
    output_count = buf.count("output")
    inout_count = buf.count("inout")

    ldebug = debug
    define_dict = preprocessor.generate_define_table(raw_buf, user_paths, ldebug)
    if 'defines' in project_tags:
        for d in project_tags["defines"]:
            define_dict[d] = project_tags["defines"][d]

    #find all the USER_PARAMETER declarations
    user_parameters = []
    substrings = raw_buf.splitlines()
    for substring in substrings:
        substring = substring.strip()
        if "USER_PARAMETER" in substring:
            name = substring.partition(":")[2].strip()
            user_parameters.append(name)


    param_dict = {}
    #find all the parameters
    substrings = buf.splitlines()
    for substring in substrings:
        substring = substring.strip()
        if ("parameter" in substring):
            if debug:
                print "found parameter!"
            substring = substring.partition("parameter")[2].strip()
            parameter_name = substring.partition("=")[0].strip()
            parameter_value = substring.partition("=")[2].strip()
            parameter_value = parameter_value.partition(";")[0].strip()
            parameter_value = parameter_value.strip(',')
            if debug:
                print "parameter name: " + parameter_name
                print "parameter value: " + parameter_value
            if parameter_name not in user_parameters:
                tags["parameters"][parameter_name] = parameter_value
                param_dict[parameter_name] = parameter_value



    #find all the IO's
    for io in ports:
        end_module = False
        in_task = False

        tags["ports"][io] = {}
        substrings = buf.splitlines()
        for substring in substrings:
            substring = substring.strip()
            if substring.startswith("endmodule"):
                end_module = True
                continue
            #Only count one module per buffer
            if end_module:
                continue

            if substring.startswith("task"):
                #Sub tasks and functions declare inputs and outputs, don't count these
                in_task = True
                continue
            if substring.startswith("function"):
                in_task = True
                continue

            if substring.startswith("endtask"):
                in_task = False
                continue

            if substring.startswith("endfunction"):
                in_task = False
                continue

            if in_task:
                continue

            #if line doesn't start with an input/output or inout
            if (not substring.startswith(io)):
                continue
            #if the line does start with input/output or inout but is used in a name then bail
            if (not substring.partition(io)[2][0].isspace()):
                continue
            #one style will declare the port names after the ports list
            if (substring.endswith(";")):
                substring = substring.rstrip(";")
            #the other stile will include the entire port definition within the port declaration
            if (substring.endswith(",")):
                substring = substring.rstrip(",")
            if debug:
                print "substring: " + substring
            substring = substring.partition(io)[2]
            if (len(substring.partition("reg")[1]) != 0):
                if (len(substring.partition("reg")[0]) > 0) and  \
                        (substring.partition("reg")[0][-1].isspace()):
                    #print "Substring: %s" % substring
                    substring = substring.partition("reg")[2]
            substring = substring.strip()
            max_val = -1
            min_val = -1
            if (len(substring.partition("]")[2]) != 0):
                #we have a range to work with?
                length_string = substring.partition("]")[0] + "]"
                substring = substring.partition("]")[2]
                substring = substring.strip()
                length_string = length_string.strip()
                if "wire" in length_string:
                    length_string = length_string.partition("wire")[2].strip()
                length_string = length_string.strip()

                #if debug:
                #print "length string: " + length_string

                ldebug = debug
                
                #print "module name: %s" % tags["module"]
                #print "parameters: %s" % str(param_dict)

                length_string = preprocessor.resolve_defines(length_string, define_dict, param_dict, debug=ldebug)
                length_string = preprocessor.evaluate_range(length_string)

                length_string = length_string.partition("]")[0]
                length_string = length_string.strip("[")
                if debug:
                    print "length string: " + length_string
                max_val = string.atoi(length_string.partition(":")[0])
                min_val = string.atoi(length_string.partition(":")[2])

            tags["ports"][io][substring] = {}

            if (max_val != -1):
                tags["ports"][io][substring]["max_val"] = max_val
                tags["ports"][io][substring]["min_val"] = min_val
                tags["ports"][io][substring]["size"] = (max_val + 1) - min_val
            else:
                tags["ports"][io][substring]["size"] = 1


    tags["arbiter_masters"] = arbiter.get_number_of_arbiter_hosts(tags)


    if debug:
        print "input count: " + str(input_count)
        print "output count: " + str(output_count)
        print "inout count: " + str(inout_count)
        print "\n"

    if debug:
        print "module name: " + tags["module"]
        for key in tags["keywords"].keys():
            print "key: " + key + ":" + tags["keywords"][key]
        for io in ports:
            for item in tags["ports"][io].keys():
                print io + ": " + item
                for key in tags["ports"][io][item].keys():
                    value = tags["ports"][io][item][key]
                    if (isinstance( value, int)):
                        value = str(value)
                    print "\t" + key + ":" + value

    return tags




def get_module_tags(filename="", bus="", keywords = [], user_paths = [], project_tags = {}, debug=False):
    """Gets the tags for the module within the specified filename

    Given a module within a filename search through the module and
    find:
      metadata
        \"SDB_CORE_ID\"
      ports: Inputs/Outputs of this module
      module: Name of the module
      parameters: Configuration parameters within the module
      arbiter_masters: Any arbiter masters within the module

    Args:
      filename: Name of the module to interrogate
      bus: A string declaring the bus type, this can be
        \"wishbone\" or \"axie\"
      keywords:
        Besides the standard metadata any additional values to search for

    Returns:
      A dictionary of module tags

    Raises
      Nothing
    """
    buf = ""
    with open(filename) as slave_file:
        buf = slave_file.read()

    return get_module_buffer_tags(buf = buf,
                                  keywords = keywords,
                                  user_paths = user_paths,
                                  project_tags = project_tags,
                                  debug = debug)


def generate_module_port_signals(invert_reset,
                                 name = "",
                                 prename = "",
                                 slave_tags = {},
                                 module_tags = {},
                                 wishbone_slave = False,
                                 debug = False):

    buf = ""
    if ("parameters" in module_tags) and \
            len(module_tags["parameters"].keys()) > 0:
        buf = "%s #(\n" % module_tags["module"]
        num_params = len(module_tags["parameters"])
        param_count = 1
        for param in module_tags["parameters"]:
            buf += "\t.{0:<20}({1:<18}){2}\n".format(param,
                                                 module_tags["parameters"][param],
                                                 get_eol(num_params, param_count))
            param_count += 1

        buf += ")%s (\n" % name

    else:
        buf = "%s %s(\n" % (module_tags["module"], name)

    if not wishbone_slave:
        IF_WIRES = []

    #Keep track of the port count so the last one won't have a comma
    port_max = get_port_count(module_tags)
    port_count = 0

    input_ports = []
    output_ports = []
    inout_ports = []
    if "input" in module_tags["ports"]:
        input_ports = module_tags["ports"]["input"].keys()
    if "output" in module_tags["ports"]:
        output_ports = module_tags["ports"]["output"].keys()
    if "inout" in module_tags["ports"]:
        inout_ports = module_tags["ports"]["inout"].keys()

    #Add the port declarations
    if "clk" in input_ports:
        buf += "\t.{0:<20}({1:<20}),\n".format("clk", "clk")
    if "rst" in input_ports:
        if invert_reset:
            buf += "\t.{0:<20}({1:<20}),\n".format("rst", "rst_n")
        else:
            buf += "\t.{0:<20}({1:<20}),\n".format("rst", "rst")



    ports = sorted(input_ports, cmp = port_cmp)
    buf += "\n"
    buf += "\t//inputs\n"

    for port in ports:
        port_count += 1
        line = ""
        if port == "rst":
            continue
        if port == "clk":
            continue

        #Check to see if this is one of the pre-defined wires
        wire = ""
        if wishbone_slave:
            for w in IF_WIRES:
                if w.endswith(port[2:]):
                    wire = "%s" % w[2:]
                    break

        #Not Pre-defines
        if len(wire) == 0:
            if len(prename) > 0:
                wire = "%s_%s" % (prename, port)
            else:
                wire = "%s" % port

        line = "\t.{0:<20}({1:<20})".format(port, wire)
        if port_count == port_max:
            buf += "%s\n" % line
        else:
            buf += "%s,\n" % line


    ports = sorted(output_ports, cmp = port_cmp)
    buf += "\n"
    buf += "\t//outputs\n"

    for port in ports:
        port_count += 1
        line = ""
        #Check to see if this is one of the pre-defined wires
        wire = ""
        if wishbone_slave:
            for w in IF_WIRES:
                if w.endswith(port[2:]):
                    wire = "%s" % w[2:]
                    break

        #Not Pre-defines
        if len(wire) == 0:
            if len(prename) > 0:
                wire = "%s_%s" % (prename, port)
            else:
                wire = "%s" % port

        line = "\t.{0:<20}({1:<20})".format(port, wire)
        if port_count == port_max:
            buf += "%s\n" % line
        else:
            buf += "%s,\n" % line

    ports = sorted(inout_ports, cmp = port_cmp)

    if len(ports) > 0:
        buf += "\n"
        buf += "\t//inouts\n"


    for port in ports:
        port_count += 1
        line = ""
        found = False
        #Special Case, we need to tie the specific signal directly to this port
        for key in sorted(slave_tags["bind"], cmp = port_cmp):
            bname = key.partition("[")[0]
            bname.strip()
            if bname == port:
                found = True
                loc = slave_tags["bind"][key]["loc"]
                if port_count == port_max:
                    buf += "\t.{0:<20}({1:<20})\n".format(port, loc)
                else:
                    buf += "\t.{0:<20}({1:<20}),\n".format(port, loc)

        if not found:
            buf += "\t.{0:<20}({1:<20}){2}\n".format(port, port, get_eol(port_max, port_count))


    buf += ");"
    return string.expandtabs(buf, 2)

def get_port_count(module_tags = {}):
    port_count = 0
    if "inout" in module_tags["ports"]:
        port_count += len(module_tags["ports"]["inout"])
    if "output" in module_tags["ports"]:
        port_count += len(module_tags["ports"]["output"])
    if "input" in module_tags["ports"]:
        port_count += len(module_tags["ports"]["input"])
    return port_count



def create_reg_buf_from_dict(name, d):
    size = d["size"]
    if size == 1:
        return create_reg_buf(name, 1, 0, 0)
    else:
        return create_reg_buf(name, size, d["max_val"], d["min_val"])

def create_reg_buf(name, size, max_val, min_val):
    line = ""
    if size > 1:
        size_range = "[%d:%d]" % (max_val, min_val)
        line = "reg\t{0:20}{1};\n".format(size_range, name)
    else:
        line = "reg\t{0:20}{1};\n".format("", name)
    return string.expandtabs(line, 2)



def create_wire_buf_from_dict(name, d):
    size = d["size"]
    if size == 1:
        return create_wire_buf(name, 1, 0, 0)
    else:
        return create_wire_buf(name, size, d["max_val"], d["min_val"])

def create_wire_buf(name, size, max_val, min_val):
    line = ""
    if size > 1:
        size_range = "[%d:%d]" % (max_val, min_val)
        line = "wire\t{0:18}{1};\n".format(size_range, name)
    else:
        line = "wire\t{0:18}{1};\n".format("", name)
    return string.expandtabs(line, 2)

def generate_assigns_buffer(invert_reset, bindings, internal_bindings, debug=False):
    buf = ""
    if len(internal_bindings) > 0:
        buf += "//Internal Bindings\n"
        for key in internal_bindings:
            if key == "clk":
                continue
            if key == "rst":
                continue
            if key == internal_bindings[key]["signal"]:
                continue

            buf += "assign\t{0:<20}=\t{1};\n".format(key, internal_bindings[key]["signal"])

    buf += "\n\n"
    if len(bindings) > 0:
        buf += "//Bindings\n"
        for key in bindings:
            if key == "clk":
                continue
            if key == "rst":
                continue
            if key == bindings[key]["loc"]:
                continue

            if bindings[key]["direction"] == "input":
                buf += "assign\t{0:<20}=\t{1};\n".format(key, bindings[key]["loc"])
            elif bindings[key]["direction"] == "output":
                buf += "assign\t{0:<20}=\t{1};\n".format(bindings[key]["loc"], key)

    if invert_reset:
        buf += "\n"
        buf += "//Invert Reset for this board\n"
        buf += "assign\t{0:<20}=\t{1};\n".format("rst_n", "~rst")

    return string.expandtabs(buf, 2)

def port_cmp(x, y):
    if re.search("[0-9]", x) and re.search("[0-9]", y):
        x_name = x.strip(string.digits)
        y_name = y.strip(string.digits)
        if x_name == y_name:
            #print "%s == %s" % (x_name, y_name)
            x_temp = x.strip(string.letters)
            x_temp = x_temp.strip("[")
            x_temp = x_temp.strip("]")

            y_temp = y.strip(string.letters)
            y_temp = y_temp.strip("[")
            y_temp = y_temp.strip("]")



            x_num = int(x_temp, 10)
            y_num = int(y_temp, 10)
            #print "x:%s, y:%s, x_num:%d, y_num:%d" % (x, y, x_num, y_num)
            if x_num < y_num:
                #print "\tx < y"
                return -1
            if x_num == y_num:
                #print "\tx == y"
                return 0
            if x_num > y_num:
                #print "\tx > y"
                return 1

    #print "normal search: %s:%s" % (x, y)
    if x < y:
        return -1
    if x == y:
        return 0
    else:
        return 1

def has_dependencies(self, filename, debug = False):
    """has_dependencies

    returns true if the file specified has dependencies

    Args:
        filename: search for dependencies with this filename

    Return:
        True: The file has dependencies.
        False: The file doesn't have dependencies

    Raises:
        IOError
    """

    if debug:
        print "input file: " + filename
    #filename needs to be a verilog file
    if (filename.partition(".")[2] != "v"):
        if debug:
            print "File is not a recognized verilog source"
        return False

    fbuf = ""

    #the name is a verilog file, try and open is
    try:
        filein = open(filename)
        fbuf = filein.read()
        filein.close()
    except IOError as err:
        if debug:
          print "the file is not a full path, searching RTL... ",
        #didn't find with full path, search for it
        try:
            #print "self.user_paths: %s" % (self.user_paths)
            filepath = utils.find_rtl_file_location(filename, self.user_paths)

            filein = open(filepath)
            fbuf = filein.read()
            filein.close()
        except ModuleError as err:
            fbuf = ""
        except IOError as err_int:
            if debug:
                print "couldn't find file in the RTL directory"
            ModuleFactoryError("Couldn't find file %s in the RTL directory" % filename)


    #we have an open file!
    if debug:
        print "found file!"

    #strip out everything we can't use
    fbuf = utils.remove_comments(fbuf)

    #modules have lines that start with a '.'
    str_list = fbuf.splitlines()

    for item in str_list:
        item = item.strip()
        if (item.startswith(".")):
            if debug:
                print "found a module!"
            return True
    return False


def resolve_dependencies(filename, debug = True):
    """resolve_dependencies

    given a filename determine if there are any modules it depends on,
    recursively search for any files found in order to extrapolate all
    dependencies

    Args:
      filename: The filename to resolve dependencies for

    Return:
      Nothing

    Raises:
      ModuleFactoryError
    """

    result = True
    ldebug = debug
    if debug:
        print "in resolve dependencies"
    local_file_list = []
    if debug:
        print "working on filename: " + filename
    if (has_dependencies(filename, debug = ldebug)):
        if debug:
            print "found dependencies!"
        deps = get_list_of_dependencies(filename, debug = ldebug)
        for d in deps:
            try:
                dep_filename = utils.find_module_filename(d, user_paths, debug = ldebug)
            except ModuleError as ex:
                print "Dependency Warning: %s" % (str(ex))
                print "Module Name: %s" % (d)
                print "This warning may be due to:"
                print "\tIncluding a simulation only module"
                print "\tIncluding a vendor specific module"
                print "\tA module that was not found"
                continue

            if debug:
                print "found the filename: " + dep_filename
            #check this file out for dependecies, then append that on to the local list
            resolve_dependencies(dep_filename, debug = ldebug)
            if debug:
                print "found all sub dependencies for: " + dep_filename
            local_file_list.append(dep_filename)

    #go through the local file list and add anything found to the list of dependencies or verilog files
    for f in local_file_list:
        if f not in verilog_dependency_list and f not in verilog_file_list:

            if debug:
                print "found dependency: " + f
            verilog_dependency_list.append(f)
    return

def get_list_of_dependencies(self, filename, debug=False):
    """get_list_of_dependencies

    return a list of the files that this file depends on

    Args:
      filename: the name of the file to analyze

    Return:
      A list of files that specify the dependenies

    Raises:
      IOError
    """
    deps = []
    if debug:
        print "input file: " + filename
    #filename needs to be a verilog file
    if (filename.partition(".")[2] != "v"):
        if debug:
            print "File is not a recognized verilog source"
        return False

    fbuf = ""
    #the name is a verilog file, try and open is
    try:
        filein = open(filename)
        fbuf = filein.read()
        filein.close()
    except IOError as err:
        #if debug:
        #  print "the file is not a full path... searching RTL"
        #didn't find with full path, search for it
        try:
            filepath = utils.find_rtl_file_location(filename, self.user_paths)

            filein = open(filepath)
            fbuf = filein.read()
            filein.close()
        except IOError as err_int:
            ModuleFactoryError("Couldn't find file %s in the RTL directory" % filename)


    #we have an open file!
    if debug:
        print "found file!"

    #strip out everything we can't use
    fbuf = utils.remove_comments(fbuf)

    include_fbuf = fbuf
    #search for `include
    while (not len(include_fbuf.partition("`include")[2]) == 0):
        ifile_name = include_fbuf.partition("`include")[2]
        ifile_name = ifile_name.splitlines()[0]
        ifile_name = ifile_name.strip()
        ifile_name = ifile_name.strip("\"")
        if debug:
            print "found an include " + ifile_name + " ",
        if (not self.verilog_dependency_list.__contains__(ifile_name) and
            not self.verilog_file_list.__contains__(ifile_name)):
            self.verilog_dependency_list.append(ifile_name)
            if debug:
                print "adding " + ifile_name + " to the dependency list"
        else:
            if debug:
                print "... already in have it"
        include_fbuf = include_fbuf.partition("`include")[2]

    #remove the ports list and the module name
    fbuf = fbuf.partition(")")[2]

    #modules have lines that start with a '.'
    str_list = fbuf.splitlines()

    module_token = ""
    done = False
    while (not done):
        module_token = ""
        parameter_found = False
        parameter_flag = False
        parameter_debt = None
        for i in range (0, len(str_list)):
            line = str_list[i]
            #remove white spaces
            line = line.strip()
            if "#" in line:
                line = line.partition("#")[2]
                parameter_found = True

            if parameter_found:
                if parameter_debt == 0:
                    parameter_found = False
                    parameter_flag = True
                while ("(" in line) or (")" in line):
                    if "(" in line:
                        line = line.partition("(")[2]
                        if parameter_debt is None:
                            parameter_debt = 1
                        else:
                            parameter_debt += 1
                    else:
                        line = line.partition("(")[2]
                        parameter_debt -= 1

            if (line.startswith(".") and line.endswith(",")):
                #if debug:
                #  print "found a possible module... with token: " + line
                module_token = line
                continue
            if ";" in line and len(module_token) > 0:
                break
            #check if we reached the last line
            if (i >= len(str_list) - 1):
                done = True

        if (not done):
            module_string = fbuf.partition(module_token)[0]
            fbuf = fbuf.partition(module_token)[2]
            fbuf = fbuf.partition(";")[2]
            str_list = fbuf.splitlines()

            #get rid of everything before the possible module
            while (len(module_string.partition(";")[2]) > 0):
                module_string = module_string.partition(";")[2].strip()

            #Now we have a string that contains the module_type and name
            module_string = module_string.partition("(")[0].strip()
            m_name = ""
            if parameter_found:
                m_name = module_string.partition("#")[0].strip()
            else:
                m_name = module_string.partition(" ")[0].strip()

            if m_name not in deps:
                if debug:
                    print "adding it to the deps list"
                deps.append(m_name)

    return deps

