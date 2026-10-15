.. _contributing:

***************************
Contributing to Pychestrate
***************************

The coding standards, naming conventions, code structure and testing conventions for this repository are kept **once**, in the
`pychestrate-service <https://github.com/code-craft-ai-company/pychestrate-service>`_ repository, because they are the same for every Pychestrate
repository (this one, ``pychestrate-client`` and the service). This repository used to carry its own copies of these chapters. They had drifted from
the service's: an old brand name, commands for scripts that no longer exist, a framework this code does not use. One copy cannot disagree with another.

Read them there. In a sibling checkout (the usual layout, with ``pychestrate-core`` and ``pychestrate-service`` side by side) they are at
``../pychestrate-service/userguide/``.

.. list-table::
   :header-rows: 1
   :widths: 24 40 36

   * - Chapter
     - What it covers
     - Where
   * - Coding Standards
     - How code is written: debuggability and readability first, defaults, return statements, retries, the rules a reviewer applies.
     - `10-00-coding-standards.rst <https://github.com/code-craft-ai-company/pychestrate-service/blob/main/userguide/10-00-coding-standards.rst>`_
   * - Code Organization
     - Where code goes: the ``source`` tree, packages, the site, blueprints, test roots.
     - `10-01-code-organization.rst <https://github.com/code-craft-ai-company/pychestrate-service/blob/main/userguide/10-01-code-organization.rst>`_
   * - Naming Conventions
     - How things are named: methods that convert or serialize, constants, files.
     - `10-02-naming-conventions.rst <https://github.com/code-craft-ai-company/pychestrate-service/blob/main/userguide/10-02-naming-conventions.rst>`_
   * - Testing Patterns and Practices
     - How tests are written and results read.
     - `10-03-testing-patterns-and-practices.rst <https://github.com/code-craft-ai-company/pychestrate-service/blob/main/userguide/10-03-testing-patterns-and-practices.rst>`_
   * - Testing Frameworks
     - testbase and testplus (what this repository uses), and the unittest and pytest conventions for repositories that use them.
     - `10-04-testing-frameworks.rst <https://github.com/code-craft-ai-company/pychestrate-service/blob/main/userguide/10-04-testing-frameworks.rst>`_

Paths in those chapters such as ``source/testroots/ccai`` and ``ccai.tests.singlehost`` apply to this repository as they do to the service.

Changing a standard
===================

Open a pull request against ``pychestrate-service`` (the chapters are under ``userguide/``). The change then applies to every repository at once; do not
copy a chapter back here.
