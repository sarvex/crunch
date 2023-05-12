#!/usr/bin/python

import glob
import os
import re
import shutil
import subprocess
import sys

# Configuration in script
##############################################################
if "SCALA_HOME" not in os.environ:
  sys.stderr.write("Environment variable SCALA_HOME must be set\n")
  sys.exit(1)
SCALA_LIB = os.path.join(os.environ["SCALA_HOME"], "lib")

if "HADOOP_HOME" not in os.environ:
  sys.stderr.write("Environment variable HADOOP_HOME must be set\n")
  sys.exit(1)
HADOOP_HOME = os.environ["HADOOP_HOME"]
HADOOP_JARS = ":".join(glob.glob(os.path.join(HADOOP_HOME, "*.jar")))

#Get the absolute path of the original (non-symlink) file.
ORIGINAL_FILE = os.readlink(__file__) if os.path.islink(__file__) else __file__
DIST_ROOT = os.path.abspath(f"{os.path.dirname(ORIGINAL_FILE)}/../")
LIB_DIR = f"{DIST_ROOT}/lib"
TMPDIR = "/tmp"
BUILDDIR = f"{TMPDIR}/script-build"
COMPILE_CMD = f"java -cp {SCALA_LIB}/scala-library.jar:{SCALA_LIB}/scala-compiler.jar -Dscala.home={SCALA_LIB} scala.tools.nsc.Main"
##############################################################

argv = sys.argv[1:]
if len(argv) < 1:
  sys.stderr.write("ERROR: insufficient args.\n")
  sys.exit(1)

JOBFILE = argv.pop(0)

def file_type():
  return m[1] if (m := re.search(r'\.(scala|java)$', JOBFILE)) else None

def is_file():
  return file_type() is not None

PACK_RE = r'package ([^;]+)'
OBJECT_RE = r'object\s+([^\s(]+).*(extends|with)\s+PipelineApp.*'
EXTENSION_RE = r'(.*)\.(scala|java)$'

#Get the name of the job from the file.
#the rule is: last class in the file, or the one that matches the filename
def get_job_name(file):
  package = ""
  job = None
  default = None
  if not (match := re.search(EXTENSION_RE, file)):
    return file
  default = match[1]
  for s in open(file, "r"):
    mp = re.search(PACK_RE, s)
    mo = re.search(OBJECT_RE, s)
    if mp:
      package = f"{mp[1].trim()}."
    elif mo:
      if not job or not default or job.tolower() != default.tolower():
          #use either the last class, or the one with the same name as the file
        job = mo[1]
  if not job:
    raise "Could not find job name"
  return f"{package}{job}"

LIB_PATH = os.path.abspath(LIB_DIR)
if not os.path.exists(LIB_PATH):
  sys.stderr.write("Scrunch distribution lib directory not found; run mvn package to construct a distribution to run examples from.\n")
  sys.exit(1)
LIB_JARS = glob.glob(os.path.join(LIB_PATH, "*.jar"))
LIB_CP = ":".join(LIB_JARS)

JOBPATH = os.path.abspath(JOBFILE)
JOB = get_job_name(JOBFILE)
JOBJAR = f"{JOB}.jar"
JOBJARPATH = os.path.join(TMPDIR, JOBJAR)

def needs_rebuild():
  return not os.path.exists(JOBJARPATH) or os.stat(JOBJARPATH).st_mtime < os.stat(JOBPATH).st_mtime

def build_job_jar():
  sys.stderr.write("compiling " + JOBFILE + "\n")
  if os.path.exists(BUILDDIR):
    shutil.rmtree(BUILDDIR)
  os.makedirs(BUILDDIR)
  cmd = "%s -classpath %s:%s -d %s %s" % (COMPILE_CMD, LIB_CP, HADOOP_JARS, BUILDDIR, JOBFILE)
  print cmd
  if subprocess.call(cmd, shell=True):
    shutil.rmtree(BUILDDIR)
    sys.exit(1)

  jar_cmd = "jar cf %s -C %s ." % (JOBJARPATH, BUILDDIR)
  subprocess.call(jar_cmd, shell=True)
  shutil.rmtree(BUILDDIR)

def hadoop_command():
  return f'HADOOP_CLASSPATH={LIB_CP} ; {HADOOP_HOME}/bin/hadoop jar {JOBJARPATH} {JOB} {" ".join(argv)}'

if is_file() and needs_rebuild():
  build_job_jar()

SHELL_COMMAND = hadoop_command()
print SHELL_COMMAND
os.system(SHELL_COMMAND)
