#!/usr/bin/python
"""
Automatically distribute task to host running, add timeout, process
management and html format log function 
"""

import datetime
import logging
import multiprocessing
import os
import optparse
import re
import select
import signal
import subprocess
import sys
import time

from xml.sax import saxutils
#from telnetlib import theNULL

class Template_mixin(object):
    """
    Define a HTML template for report customerization and generation.

    Overall structure of an HTML report

    HTML
    +------------------------+
    |<html>                  |
    |  <head>                |
    |                        |
    |   STYLESHEET           |
    |   +----------------+   |
    |   |                |   |
    |   +----------------+   |
    |                        |
    |  </head>               |
    |                        |
    |  <body>                |
    |                        |
    |   HEADING              |
    |   +----------------+   |
    |   |                |   |
    |   +----------------+   |
    |                        |
    |   REPORT               |
    |   +----------------+   |
    |   |                |   |
    |   +----------------+   |
    |                        |
    |   ENDING               |
    |   +----------------+   |
    |   |                |   |
    |   +----------------+   |
    |                        |
    |  </body>               |
    |</html>                 |
    +------------------------+
    """

    STATUS = {
        0:'pass',
        1:'fail',
        2:'error',
        }

    DEFAULT_TITLE = 'Unit Test Report'
    DEFAULT_DESCRIPTION = ''

    # ------------------------------------------------------------------------
    # HTML Template

    HTML_TMPL = r"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>%(title)s</title>
    <meta name="generator" content="%(generator)s"/>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
    %(stylesheet)s
</head>
<body>
<script language="javascript" type="text/javascript"><!--
output_list = Array();

/* level - 0:Summary; 1:Failed; 2:All */
function showCase(level) {
    trs = document.getElementsByTagName("tr");
    for (var i = 0; i < trs.length; i++) {
        tr = trs[i];
        id = tr.id;
        if (id.substr(0,2) == 'ft') {
            if (level < 1) {
                tr.className = 'hiddenRow';
            }
            else {
                tr.className = '';
            }
        }
        if (id.substr(0,2) == 'pt') {
            if (level > 1) {
                tr.className = '';
            }
            else {
                tr.className = 'hiddenRow';
            }
        }
    }
}


function showClassDetail(cid, count) {
    var id_list = Array(count);
    var toHide = 1;
    for (var i = 0; i < count; i++) {
        tid0 = 't' + cid.substr(1) + '.' + (i+1);
        tid = 'f' + tid0;
        tr = document.getElementById(tid);
        if (!tr) {
            tid = 'p' + tid0;
            tr = document.getElementById(tid);
        }
        id_list[i] = tid;
        if (tr.className) {
            toHide = 0;
        }
    }
    for (var i = 0; i < count; i++) {
        tid = id_list[i];
        if (toHide) {
            document.getElementById('div_'+tid).style.display = 'none'
            document.getElementById(tid).className = 'hiddenRow';
        }
        else {
            document.getElementById(tid).className = '';
        }
    }
}


function showTestDetail(div_id){
    var details_div = document.getElementById(div_id)
    var displayState = details_div.style.display
    // alert(displayState)
    if (displayState != 'block' ) {
        displayState = 'block'
        details_div.style.display = 'block'
    }
    else {
        details_div.style.display = 'none'
    }
}


function html_escape(s) {
    s = s.replace(/&/g,'&amp;');
    s = s.replace(/</g,'&lt;');
    s = s.replace(/>/g,'&gt;');
    return s;
}

/* obsoleted by detail in <div>
function showOutput(id, name) {
    var w = window.open("", //url
                    name,
                    "resizable,scrollbars,status,width=800,height=450");
    d = w.document;
    d.write("<pre>");
    d.write(html_escape(output_list[id]));
    d.write("\n");
    d.write("<a href='javascript:window.close()'>close</a>\n");
    d.write("</pre>\n");
    d.close();
}
*/
--></script>

%(heading)s
%(report)s
%(ending)s

</body>
</html>
"""
    # variables: (title, generator, stylesheet, heading, report, ending)


    # ------------------------------------------------------------------------
    # Stylesheet
    #
    # alternatively use a <link> for external style sheet, e.g.
    #   <link rel="stylesheet" href="$url" type="text/css">

    STYLESHEET_TMPL = """
<style type="text/css" media="screen">
body        { font-family: verdana, arial, helvetica, sans-serif; font-size: 80%; }
table       { font-size: 100%; }
pre         { }

/* -- heading ---------------------------------------------------------------------- */
h1 {
    font-size: 16pt;
    color: gray;
}
.heading {
    margin-top: 0ex;
    margin-bottom: 1ex;
}

.heading .attribute {
    margin-top: 1ex;
    margin-bottom: 0;
}

.heading .description {
    margin-top: 4ex;
    margin-bottom: 6ex;
}

/* -- css div popup ------------------------------------------------------------------------ */
a.popup_link {
}

a.popup_link:hover {
    color: red;
}

.popup_window {
    display: none;
    position: relative;
    left: 0px;
    top: 0px;
    /*border: solid #627173 1px; */
    padding: 10px;
    background-color: #E6E6D6;
    font-family: "Lucida Console", "Courier New", Courier, monospace;
    text-align: left;
    font-size: 8pt;
    width: 500px;
}

}
/* -- report ------------------------------------------------------------------------ */
#show_detail_line {
    margin-top: 3ex;
    margin-bottom: 1ex;
}
#result_table {
    width: 80%;
    border-collapse: collapse;
    border: 1px solid #777;
}
#header_row {
    font-weight: bold;
    color: white;
    background-color: #777;
}
#result_table td {
    border: 1px solid #777;
    padding: 2px;
}
#total_row  { font-weight: bold; }
.passClass  { background-color: #6c6; }
.failClass  { background-color: #c60; }
.errorClass { background-color: #c00; }
.passCase   { color: #6c6; }
.failCase   { color: #c60; font-weight: bold; }
.errorCase  { color: #c00; font-weight: bold; }
.hiddenRow  { display: none; }
.testcase   { margin-left: 2em; }


/* -- ending ---------------------------------------------------------------------- */
#ending {
}

</style>
"""



    # ------------------------------------------------------------------------
    # Heading
    #

    HEADING_TMPL = """<div class='heading'>
<h1>%(title)s</h1>
%(parameters)s
<p class='description'>%(description)s</p>
</div>

""" # variables: (title, parameters, description)

    HEADING_ATTRIBUTE_TMPL = """<p class='attribute'><strong>%(name)s:</strong> %(value)s</p>
""" # variables: (name, value)



    # ------------------------------------------------------------------------
    # Report
    #

    REPORT_TMPL = """
<p id='show_detail_line'>Show
<a href='javascript:showCase(0)'>Summary</a>
<a href='javascript:showCase(1)'>Failed</a>
<a href='javascript:showCase(2)'>All</a>
</p>
<table id='result_table'>
<colgroup>
<col align='left' />
<col align='right' />
<col align='right' />
<col align='right' />
<col align='right' />
<col align='right' />
</colgroup>
<tr id='header_row'>
    <td>Test Module</td>
    <td>Count</td>
    <td>Pass</td>
    <td>Fail</td>
    <td>Timeout</td>
    <td>View</td>
</tr>
%(test_list)s
<tr id='total_row'>
    <td>Total</td>
    <td>%(count)s</td>
    <td>%(Pass)s</td>
    <td>%(fail)s</td>
    <td>%(error)s</td>
    <td>&nbsp;</td>
</tr>
</table>
""" # variables: (test_list, count, Pass, fail, error)

    REPORT_CLASS_TMPL = r"""
<tr class='%(style)s'>
    <td>%(desc)s</td>
    <td>%(count)s</td>
    <td>%(Pass)s</td>
    <td>%(fail)s</td>
    <td>%(error)s</td>
    <td><a href="javascript:showClassDetail('%(cid)s',%(count)s)">Detail</a></td>
</tr>
""" # variables: (style, desc, count, Pass, fail, error, cid)


    REPORT_TEST_WITH_OUTPUT_TMPL = r"""
<tr id='%(tid)s' class='%(Class)s'>
    <td class='%(style)s'><div class='testcase'>%(desc)s</div></td>
    <td colspan='5' align='center'>

    <!--css div popup start-->
    <a class="popup_link" onfocus='this.blur();' href="javascript:showTestDetail('div_%(tid)s')" >
        %(status)s</a>

    <div id='div_%(tid)s' class="popup_window">
        <div style='text-align: right; color:red;cursor:pointer'>
        <a onfocus='this.blur();' onclick="document.getElementById('div_%(tid)s').style.display = 'none' " >
           [x]</a>
        </div>
        <pre>
        %(script)s
<a font=10 href=%(log)s>Case Log Link</a>
        </pre>
    </div>
    <!--css div popup end-->

    </td>
</tr>
""" # variables: (tid, Class, style, desc, status)


    REPORT_TEST_NO_OUTPUT_TMPL = r"""
<tr id='%(tid)s' class='%(Class)s'>
    <td class='%(style)s'><div class='testcase'>%(desc)s</div></td>
    <td colspan='5' align='center'>%(status)s</td>
</tr>
""" # variables: (tid, Class, style, desc, status)


# old code : %(id)s: %(output)s
    REPORT_TEST_OUTPUT_TMPL = r"""
%(output)s
""" # variables: (id, output)



    # ------------------------------------------------------------------------
    # ENDING
    #

    ENDING_TMPL = """<div id='ending'>&nbsp;</div>"""


class HTMLTestRunner(Template_mixin):
    """
    """
    def __init__(self, stream=sys.stdout, verbosity=1, title=None,
                 description=None, start_time=datetime.datetime.now()):
        self.stream = stream
        self.verbosity = verbosity
        if title is None:
            self.title = self.DEFAULT_TITLE
        else:
            self.title = title
        if description is None:
            self.description = self.DEFAULT_DESCRIPTION
        else:
            self.description = description

        self.startTime = start_time
        self.stopTime = datetime.datetime.now()

        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0

    #def run(self, test):
    #    "Run the given test case or test suite."
    #    result = _TestResult(self.verbosity)
    #    test(result)
    #    self.stopTime = datetime.datetime.now()
    #    self.generateReport(test, result)
    #    print >>sys.stderr, '\nTime Elapsed: %s' % (self.stopTime-self.startTime)
    #    return result

    def sortResult(self, result_list):
        # unittest does not seems to run in any particular order.
        # Here at least we want to group them together by class.
        rmap = {}
        classes = []
        for n, t, o, e in result_list:
            cls = t.__class__
            if not rmap.has_key(cls):
                rmap[cls] = []
                classes.append(cls)
            rmap[cls].append((n, t, o, e))
        r = [(cls, rmap[cls]) for cls in classes]
        return r


    def getReportAttributes(self, result):
        """
        Return report attributes as a list of (name, value).
        Override this to add custom attributes.
        """
        startTime = str(self.startTime)[:19]
        duration = str(self.stopTime - self.startTime)
        status = []
        if self.success_count: status.append('Pass %s'    % self.success_count)
        if self.failure_count: status.append('Failure %s' % self.failure_count)
        if self.error_count: status.append('Error %s'   % self.error_count)
        if status:
            status = ' '.join(status)
        else:
            status = 'none'
        return [
            ('Start Time', startTime),
            ('Duration', duration),
            ('Status', status),
        ]


    def generateReport(self, result):

        generator = 'HTMLTestRunner %s' % '111111'
        stylesheet = self._generate_stylesheet()
        report = self._generate_report(result)

        report_attrs = self.getReportAttributes(result)
        heading = self._generate_heading(report_attrs)

        ending = self._generate_ending()
        output = self.HTML_TMPL % dict(
            title=saxutils.escape(self.title),
            generator=generator,
            stylesheet=stylesheet,
            heading=heading,
            report=report,
            ending=ending,
            )
        #self.stream.write(output.encode('utf8'))
        self.stream.write(output)


    def _generate_stylesheet(self):
        return self.STYLESHEET_TMPL


    def _generate_heading(self, report_attrs):
        a_lines = []
        for name, value in report_attrs:
            line = self.HEADING_ATTRIBUTE_TMPL % dict(
                name=saxutils.escape(name),
                value=saxutils.escape(value),
                )
            a_lines.append(line)
        heading = self.HEADING_TMPL % dict(
            title=saxutils.escape(self.title),
            parameters=''.join(a_lines),
            description=saxutils.escape(self.description),
            )
        return heading


    def _generate_report(self, result):
        rows = []
        #sortedResult = self.sortResult(result.result)
        #for cid, (cls, cls_results) in enumerate(sortedResult):
        for cid, cls_results in enumerate(result):
            # subtotal for a class
            np = nf = ne = 0
            for cls_item in cls_results[1]:
                if cls_item['tc_status'].lower() == 'passed':
                    self.success_count += 1
                    np += 1
                elif cls_item['tc_status'].lower() == 'failed':
                    nf += 1
                    self.failure_count += 1
                else:
                    ne += 1
                    self.error_count += 1
            '''
            for n,t,o,e in cls_results:
                if n == 0: np += 1
                elif n == 1: nf += 1
                else: ne += 1
            '''
            # format class description
            '''
            if cls.__module__ == "__main__":
                name = cls.__name__
            else:
                name = "%s.%s" % (cls.__module__, cls.__name__)
            doc = cls.__doc__ and cls.__doc__.split("\n")[0] or ""
            desc = doc and '%s: %s' % (name, doc) or name
            '''
            desc = cls_results[0]
            row = self.REPORT_CLASS_TMPL % dict(
                style=ne > 0 and 'errorClass' or nf > 0 and 'failClass' or 'passClass',
                desc=desc,
                count=np+nf+ne,
                Pass=np,
                fail=nf,
                error=ne,
                cid='c%s' % (cid+1),
            )
            #print 'style',ne > 0 and 'errorClass' or nf > 0 and 'failClass' or 'passClass'
            rows.append(row)
            for tid, cls_items in enumerate(cls_results[1]):
                self._generate_report_test(rows, cid, tid,
                                           cls_items['tc_status'],
                                           cls_items['tc_id'],
                                           cls_items['tc_output'],
                                           cls_items['tc_errout'],
                                           cls_items['tc_return_code'],
                                           cls_items['tc_log'])
            '''
            for tid, (n,t,o,e) in enumerate(cls_results):
                self._generate_report_test(rows, cid, tid, n, t, o, e)
            '''
        report = self.REPORT_TMPL % dict(
            test_list=''.join(rows),
            count=str(self.success_count+self.failure_count+self.error_count),
            Pass=str(self.success_count),
            fail=str(self.failure_count),
            error=str(self.error_count),
        )
        return report


    def _generate_report_test(self, rows, cid, tid, n, t, o, e, r, l):
        # e.g. 'pt1.1', 'ft1.1', etc
        has_output = bool(o or e or r)
        tid = (n == 'passed' and 'p' or 'f') + 't%s.%s' % (cid+1, tid+1)
        '''
        name = t.id().split('.')[-1]
        doc = t.shortDescription() or ""
        desc = doc and ('%s: %s' % (name, doc)) or name
        '''
        desc = t
        tmpl = has_output and self.REPORT_TEST_WITH_OUTPUT_TMPL or self.REPORT_TEST_NO_OUTPUT_TMPL

        # o and e should be byte string because they are collected from stdout and stderr?
        if isinstance(o, str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # uo = unicode(o.encode('string_escape'))
            uo = o.decode('latin-1')
        else:
            uo = o
        if isinstance(e, str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # ue = unicode(e.encode('string_escape'))
            ue = e.decode('latin-1')
        else:
            ue = e
        if isinstance(r, str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # ue = unicode(e.encode('string_escape'))
            ur = r.decode('latin-1')
        else:
            ur = '\nreturn code : ' + str(r)
        script = self.REPORT_TEST_OUTPUT_TMPL % dict(
            id=tid,
            output=saxutils.escape(uo+ue+ur),
        )

        log = l
        row = tmpl % dict(
            tid=tid,
            Class=(n == 0 and 'hiddenRow' or 'none'),
            style=n == 2 and 'errorCase' or (n == 1 and 'failCase' or 'none'),
            desc=desc,
            script=script,
            log=log,
            #status = self.STATUS[n],
            status=n
        )
        rows.append(row)
        if not has_output:
            return

    def _generate_ending(self):
        """Internal function that get ending template
        """
        return self.ENDING_TMPL

################################################################################

def runCMDBlocked(cmd):
    """Run a command line with blocking format
    """
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    (r_stdout, r_stderr) = result.communicate(result)
    #output = "%s\n%s" %(r_stdout, r_stderr)
    return_code = result.returncode

    return (return_code, r_stdout)

def runCMDNonBlocked(cmd, timeout=5):
    """Run command line with non-blocking format
    """
    #print "current param1 :%s \npid is :%s" %(task, os.getpid())

    start_time = datetime.datetime.now()
    #cmd="./test %s" %cmd
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, preexec_fn=os.setpgrp)

    readbuf_msg = ""
    select_rfds = [result.stdout]
    result_buf = ""
    timeout_flag = False

    while len(select_rfds) > 0:
        (rfds, _wfds, _efds) = select.select(select_rfds, [], [], timeout)
        if not rfds:
            #print "kill pid = ",result.pid
            os.kill(-result.pid, signal.SIGKILL)
            timeout_flag = True
            result_buf = "--------timeout--------\nOutput snip :" + result_buf
            return_code = 10
            break
        for rfd in rfds:
            readbuf_msg = rfd.readline()
            result_buf = result_buf + readbuf_msg
            if len(readbuf_msg) == 0:
                select_rfds.remove(result.stdout)

    result.wait()

    end_time = datetime.datetime.now()
    if timeout_flag is False:
        return_code = result.returncode

    return (return_code, result_buf, start_time, end_time)

def _parseOutput(output,
                 start_key="**** Test in progress ****",
                 end_key="**** Test run complete ****"):
    output_list = []
    start_key_index = 0
    end_key_index = 0
    output_list = output.split(os.linesep)
    for index, item in enumerate(output_list):
        if re.search(start_key, item, re.I):
            start_key_index = index
        elif re.search(end_key, item, re.I):
            end_key_index = index
    if not end_key_index:
        end_key_index = index
    if end_key_index == start_key_index:
        return output
    else:
        return "\n".join(output_list[start_key_index, end_key_index+1])


def _installHost(host_ip, ins_type="http", suse_os="sles-11",
                 suse_sp="sp4", bit="64"):
    """Function which reinstalling host by hamsta API
    """
    def _getRepoSource():
        """FUnction which getting reinstalling repository 
        """
        source_name = "source.%s.%s-%s-%s" %(ins_type, suse_os, suse_sp, bit)
        prefix_cmd_get_source = "/usr/share/qa/virtautolib/lib/get-source.sh"

        if not os.path.exists(prefix_cmd_get_source):
            LOGGER.error(("Failed to get repository due to %s does not exist"
                          %prefix_cmd_get_source))
        
            return (1, "Can not run func [%s] which does not exist !!" %prefix_cmd_get_source)

        prefix_cmd_get_source = prefix_cmd_get_source + " -p %s"
        cmd_get_source = prefix_cmd_get_source %(source_name)

        LOGGER.info("Get reporsitory with cmd[%s]" %(cmd_get_source))
        return runCMDBlocked(cmd_get_source)

    return_code, result_buf = _getRepoSource()
    if return_code != 0:
        LOGGER.error("Failed to install host due to :%s" %result_buf)
        return (return_code, "Cause: " + result_buf,
                datetime.datetime.now(), datetime.datetime.now())

    install_repo = result_buf.strip()
    LOGGER.debug("Repo for installing source [%s]"  %(install_repo))
    addon_repo = "http://download.suse.de/ibs/home:/jerrytang/SLE_11_SP4,http://download.suse.de/ibs/Devel:/Virt:/SLE-11-SP4/SLE_11_SP4,http://download.suse.de/ibs/Devel:/Virt:/Tests/SLE_11_SP4/"
    rpms = "qa_test_virtualization"
    pattern = "kvm_server"
    cmd = ("/usr/share/hamsta/feed_hamsta.pl -t 5 --re_url  %(install_repo)s "
           "--re_sdk %(addon_repo)s --pattern %(pattern)s -rpms %(rpms)s -h "
           "%(host_ip)s 127.0.0.1 -w" %dict(install_repo=install_repo,
                                            addon_repo=addon_repo,
                                            rpms=rpms,
                                            pattern=pattern,
                                            host_ip=host_ip,))
    if DEBUG:
        cmd = "./test"
    LOGGER.info(("Start to install host with cmd[%s] on machine %s"
                 %(cmd, host_ip)))
    return runCMDNonBlocked(cmd, timeout=3600)

def _installGuest(host_ip):
    """Function which installing guest by hamsta API
    """
    cmd1 = "scp /root/virt/virt-simple.tcf root@%s:/usr/share/qa/tcf/" %host_ip
    cmd2 = "scp /root/virt/virt-simple-run root@%s:/usr/share/qa/tools/" %host_ip
    cmd3 = "scp /root/virt/source.cn root@%s:/usr/share/qa/virtautolib/data/" %host_ip
    cmd4 = "ssh root@%s \"mkdir /.virtinst\"" %host_ip
    runCMDBlocked(cmd1)
    runCMDBlocked(cmd2)
    runCMDBlocked(cmd3)
    runCMDBlocked(cmd4)

    cmd = ("/usr/share/hamsta/feed_hamsta.pl -x "
           "\"/usr/share/qa/tools/virt-simple-run\" "
           "-h %s 127.0.0.1 -w" %(host_ip))
    if DEBUG:
        cmd = "./test ttttttttttttttttttttttttttt"
    LOGGER.info(("Start to install guest with cmd[%s] on host %s"
                 %(cmd, host_ip)))
    return runCMDNonBlocked(cmd, timeout=7200)

def _upgrateHost(host_ip):
    pass

def runVirtCMD(task, log, queue=None, timeout=5):
    """Run command line with non-blocking format
    """
    LOGGER.info("Task [%s] starts to run now" %task)
    host_ip = queue.get(block=True, timeout=2)

    #TODO, this is not secure when all hosts are hanged
    #the loop running forever!!
    while not AllStaticFuncs.checkIPAddress(host_ip):
        LOGGER.debug("Host [%s] is busy" %host_ip)
        time.sleep(2)
        queue.put(host_ip)
        host_ip = queue.get(block=True, timeout=2)
        LOGGER.debug("Switch another host [%s]" %host_ip)

    LOGGER.debug("Running on host [%s]" %host_ip)
    #print "current param1 :%s \npid is :%s" %(task, os.getpid())
    #cmd = "/root/virt/cmdreinstall"

    return_code, ih_result_buf, start_time, end_time = _installHost(host_ip)
    result_buf = "Parse 1:\n\tStatus :%s\n\tResult :%s\n\n" %(return_code,
                                                              ih_result_buf)
    LOGGER.debug("Parse 1 ,Return output: [%s]" %result_buf)

    if return_code == 0:
        return_code, ig_result_buf, _ig_start_time, end_time = _installGuest(host_ip)
        #Get guest installing info from test result
        ig_result_buf = _parseOutput(ig_result_buf)

        result_buf = result_buf + ("Parse 2:\n\tStatus :%s\n\tResult :%s\n"
                                   %(return_code, ig_result_buf))

        if return_code != 0:
            LOGGER.warn("Failed to install guest on host %s" %host_ip)
    else:
        LOGGER.warn("Failed to reinstall on machine %s" %host_ip)

    queue.put(host_ip)
    AllStaticFuncs.writeLog2File(task, log, return_code, host_ip,
                                 result_buf, end_time-start_time)
    LOGGER.info("Task [%s] finishes now" %task)
    LOGGER.debug("Task %s sleeps 2 seconds for next running" %task)
    time.sleep(2)
    return (task, host_ip, return_code, result_buf, start_time, end_time, log)

class ParseCMDParam(optparse.OptionParser):
    """Class which parses command parameters
    """

    def __init__(self):
        optparse.OptionParser.__init__(self, usage='Usage: %prog [options]')

        self.add_option("-H", "--Host", action="store", type="string",
                        dest="host_list",
                        help=("Add a node or multiple node"))
        self.add_option("-t", "--task", action="store", type="string",
                        dest="task_list",
                        help=("Delete a node or multiple node"))
        LOGGER.debug("Params : " + str(sys.argv))

class AllStaticFuncs(object):
    """Class which contains all staticmethod functions
    """
    def __init__(self):
        pass

    @staticmethod
    def checkIPAddress(ip_address):
        """Check if the host address is available through hamsta command line
        """
        (return_code, output) = runCMDBlocked(
            "/usr/share/hamsta/feed_hamsta.pl -p 127.0.0.1")
        LOGGER.debug("Current all availiable host %s" %output)
        if return_code == 0 and output:
            if len(ip_address.split(".")) == 4 and re.search(ip_address.strip(),
                                                             output, re.I):
                return True
            else:
                return False

    @staticmethod
    def getAvailHost(host_list):
        """Get availiable host list
        """
        tmp_host_list = map(lambda x: x.strip(), host_list)
        tmp_host_list = filter(AllStaticFuncs.checkIPAddress, tmp_host_list)
        LOGGER.info("Available hosts :" + str(tmp_host_list))
        return tmp_host_list

    @staticmethod
    def writeLog2File(task, logname, returncode=0,
                      host="1.1.1.1", content="empty", duration="0"):
        """Write output info of command line to file
        """
        #LOGGER.debug(("Write log to file , params :[task=%s,returncode=%d,"
        #              "logname=%s,host=%s,content=%s]" %(task, returncode,
        #                                                 logname, host, content)))
        if os.path.exists(logname):
            os.remove(logname)
        with open(logname, "a+") as f:
            f.write("Task : %s" %(task) + os.linesep)
            f.write("Host : %s" %(host) + os.linesep)
            if returncode == 0:
                f.write("Status : Passed" + os.linesep)
            elif returncode == 10:
                f.write("Status : Timeout" + os.linesep)
            else:
                f.write("Status : Failed" + os.linesep)

            f.write(os.linesep)
            f.write("Running time : %s" %(duration) + os.linesep)
            f.write("-" * 30 + os.linesep)
            f.write(os.linesep)
            f.write("Output : " + os.linesep +
                    ("\t:%s" %(content.replace(os.linesep, os.linesep+"\t"))))
            f.flush()
            f.close()

    @staticmethod
    def warp_generate_html_report(tcmap, htmllogname="Test_Report.html",
                                  title='Virtulizaiton Automation Test Report',
                                  desc='Automatically finished all automation test work',
                                  start_time=datetime.datetime.now()):
        """Warpper function for generate html report
        """
        filename = os.path.join(AllStaticFuncs.getBuildPath(), htmllogname)
        htmlfp = file(filename, 'wb')
        report = HTMLTestRunner(stream=htmlfp, title=title,
                                description=desc, start_time=start_time)
        LOGGER.info("Generate html repor , url:%s" %AllStaticFuncs.getHtmlReport())
        report.generateReport(tcmap)

    @staticmethod
    def getBuildPath():
        """Get build path, environment WORKSPACE and BUILD_TAG are built-in 
        environment variable of jenkins
        """
        build_path = os.path.join(os.getenv("WORKSPACE", os.getcwd()),
                                   "LOG", os.getenv("BUILD_TAG", ""))
        if not os.path.exists(build_path):
            os.makedirs(build_path)
        return build_path

    @staticmethod
    def getJobURL():
        """Get environment variable JOB_URL which belongs to Jenkins variable
        """
        return os.getenv("JOB_URL", os.getcwd())

    @staticmethod
    def getHtmlReport():
        """Get html report url for displaying it in log
        """
        return os.path.join(AllStaticFuncs.getJobURL(), "HTML_Report/")

    @staticmethod
    def genEnv2File(var_value="", var_name="OUTPUT", file_name="env.file"):
        jobs_path = os.getenv("WORKSPACE", "./")
        env_file_path = os.path.join(jobs_path, file_name)
        if os.path.exists(file_name):
            os.remove(env_file_path)
        with open(file_name, "w+") as ef_f:
            ef_f.write("%s=%s" %(var_name, var_value))

        LOGGER.debug("Wait 2 seconds for finished flush of I/O")
        time.sleep(2)

    @staticmethod
    def compressFile(file_name):
        """Compress log folder/files
        """
        if os.path.exists(file_name):
            if os.path.isfile(file_name):
                basname_file = os.path.basename(file_name)
                dirname_file = os.path.dirname(file_name)
            elif os.path.isdir(file_name):
                if file_name[-1] == os.linesep:
                    basname_file = os.path.basename(file_name[:-1])
                else:
                    basname_file = os.path.basename(file_name)
                dirname_file = os.path.dirname(file_name)

            tar_file_name = file_name + ".tar.gz"
            os.chdir(dirname_file)
            sz_cmd = "tar czf " + tar_file_name + " " + basname_file
            return_code, _output = runCMDBlocked(sz_cmd)
            if return_code != 0:
                LOGGER.warn("Failed to compress log file [%s]" %file_name)
        else:
            LOGGER.error("Log folder/file does not exist")

class MultipleProcessRun(object):
    """Class which supports multiple process running for virtualization
    """

    def __init__(self, host_list, task_list):
        """Initial process pool
        """
        self.host_list = host_list
        self.task_list = task_list
        self.result = []
        self.queue = multiprocessing.Manager().Queue()
        self.all_result = []
        self.logpath = AllStaticFuncs.getBuildPath()
        LOGGER.debug("Get build log path :%s" % self.logpath)
        #Pool size is defined through host number.
        self.pool = multiprocessing.Pool(processes=len(self.host_list))
        LOGGER.debug("Create process pool[%d]" %len(self.host_list))
        self.initialQueue()
        self.execMultipleTask()
        self.closeAndJoinPool()

    def initialQueue(self):
        """Initial queue, add host name to queue
        """
        LOGGER.debug("Initial queue with host name")
        for host in self.host_list:
            self.queue.put(host)

    def execMultipleTask(self):
        """Execute multiple taskes in processes pool
        """
        for task in self.task_list:
            self.result.append([task,
                                self.pool.apply_async(
                                    runVirtCMD,
                                    (task, self.getLogName(task), self.queue)
                                    )])

    def getLogName(self, filename):
        """Get initial log path
        """
        return os.path.join(self.logpath, filename)

    def closeAndJoinPool(self):
        """Close and wait pool
        """
        self.pool.close()
        self.pool.join()

    def getResult(self):
        """Return processes result
        """
        return self.result

    def getResultMap(self):
        """Display result
        """
        LOGGER.info("Get all processes infomation")
        for res in self.result:
            #print res[1]
            #if res[1].successful():
            tc_result = res[1].get()
            tm_tc_map = {}
            tm_tc_map["tc_name"] = tc_result[0]
            tm_tc_map["tc_return_code"] = tc_result[2]

            if tm_tc_map["tc_return_code"] == 0:
                tm_tc_map["tc_status"] = "Passed"
            elif tm_tc_map["tc_return_code"] == 10:
                tm_tc_map["tc_status"] = "Timeout"
            else:
                tm_tc_map["tc_status"] = "Failed"
            tm_tc_map["tc_output"] = tc_result[3]
            tm_tc_map["tc_host"] = tc_result[1]
            tm_tc_map["tc_errout"] = ""
            tm_tc_map["tc_id"] = tc_result[0]
            tm_tc_map["tc_log"] = tc_result[-1]

            if filter(lambda x: x[0] == tm_tc_map["tc_host"], self.all_result):
                for mode_item in self.all_result:
                    if mode_item[0] == tm_tc_map["tc_host"]:
                        mode_item[1].append(tm_tc_map)
                        break
            else:
                self.all_result.append([tm_tc_map["tc_host"], [tm_tc_map]])
        return self.all_result

class LoggerHandling(object):
    """Class which support to add five kind of level info to file
    and standard output 
    """
    def __init__(self, log_file):
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(filename)s[line:%(lineno)d] [%(process)d] %(levelname)-6s | %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename=log_file,
                            filemode='w')

        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s [%(process)d]: %(levelname)-8s %(message)s')
        console.setFormatter(formatter)

        self.logger = logging.getLogger('')
        self.logger.addHandler(console)

    def debug(self, message):
        """Display debug message
        """
        self.logger.debug(message)

    def info(self, message):
        """Display info message
        """
        self.logger.info(message)

    def warn(self, message):
        """Display warning message
        """
        self.logger.warn(message)

    def error(self, message):
        """Display error message
        """
        self.logger.error(message)

    def crit(self, message):
        """Display Criticall message
        """
        self.logger.critical(message)

def main():
    """Main function
    """
    #Parse commandline parameters
    start_time = datetime.datetime.now()

    param_opt = ParseCMDParam()
    options, _args = param_opt.parse_args()

    #Add host address to queue for multiple processes
    host_list = AllStaticFuncs.getAvailHost(options.host_list.split(","))
    task_list = options.task_list.strip().split(",")

    LOGGER.debug("Host List :" + str(host_list))
    LOGGER.debug("Task List :" + str(task_list))

    #Instance for multiple process
    if host_list:
        mpr = MultipleProcessRun(host_list, task_list)

        AllStaticFuncs.warp_generate_html_report(
            tcmap=mpr.getResultMap(),
            htmllogname = os.getenv("BUILD_TAG", "Test_Report") + ".html",
            desc=("Automation test tool is only for installing guest"
                  " on remote server.\n\tFunctions:\n"
                  "\t\t1. Install host server remotely.\n"
                  "\t\t2. Install needed packages of virtualizaiton test\n"
                  "\t\t3. Install guests in parallel on host server\n"
                  "\t\t4. Verify the installing result."),
            start_time=start_time)
        AllStaticFuncs.compressFile(AllStaticFuncs.getBuildPath())
        AllStaticFuncs.genEnv2File("here should add output info")
    else:
        AllStaticFuncs.genEnv2File("here is no available host now")
        LOGGER.warn("There is no available host now")
        sys.exit(5)
    LOGGER.info("End")

DEBUG = False
#DEBUG = True
LOGGER = LoggerHandling(os.path.join(AllStaticFuncs.getBuildPath(), "sys.log"))

if __name__ == "__main__":
    main()