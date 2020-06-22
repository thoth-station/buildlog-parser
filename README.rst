Thoth's build log parser
------------------------

Parse build logs out of OpenShift's Python Source-To-Image (s2i) builds that use
`Thoth s2i container images <https://github.com/thoth-station/s2i-thoth>`_.

This tool finds structure in an unstructured build logs of `OpenShift's s2i
<https://docs.openshift.com/container-platform/3.6/creating_images/s2i.html>`_
and produces a JSON document describing all the actions taken during an
OpenShift s2i build process together with additional metadata that can be
obtained purely from OpenShift's build logs.

The prerequisite for using this tool is to use `Thoth's Python s2i container
images <https://github.com/thoth-station/micropipenv>`_ that use Thoth as a
recommendation engine for Python software stacks and `micropipenv
<https://github.com/thoth-station/micropipenv>`_ for installing dependencies.
The build logs produced during s2i builds are still user friendly when directly
browsing them in an OpenShift cluster, but can be used for data mining and
additional analysis (e.g. build breaking package).

Usage
=====

Point this tool to a log obtained from the cluster:

.. code-block:: console

  # Obtain logs using:
  #   oc logs user-api-469-build -n thoth-test-core > log.txt
  # or for the most recent build:
  #   oc logs -f bc/user-api -n thoth-test-core > log.txt
  thoth-buildlog-parser parse --input log.txt

And that's it. The tool will produce a JSON document describing the build process
with all the metadata.


Example input & output
======================

You can find some example inputs and example outputs in ``tests/data/`` directory.


Installation
============

This tool is packages and published on PyPI so you can issue one of the following commands to install it:

.. code-block:: console

  pip install thoth-buildlog-parser
  pipenv install thoth-buildlog-parser

After installing this tool, a new command should be available:

.. code-block:: console

  thoth-buildlog-parser --help


Running from Git
================

To run this tool directly from the Git repo:

.. code-block::

  git clone git@github.com:thoth-station/buildlog-parser.git  # or use https
  cd buildlog-parser
  pipenv install --dev
  PYTHONPATH=. pipenv run python3 ./thoth-buildlog-parser parse --help
