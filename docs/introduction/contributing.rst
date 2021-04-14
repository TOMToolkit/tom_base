Contributing
------------

This page will go over the process for contributing to the TOM Toolkit.

Contributing Code/Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you’re interested in contributing code to the project, thank you! For
those unfamiliar with the process of contributing to an open-source
project, you may want to read through Github’s own short informational
section on `how to submit a
contribution <https://opensource.guide/how-to-contribute/#how-to-submit-a-contribution>`__.

Identifying a starting point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The best place to begin contributing is by first looking at the `Github
issues page <https://github.com/TOMToolkit/tom_base/issues>`__, to see
what’s currently needed. Issues that don’t require much familiarity with
the TOM Toolkit will be tagged appropriately.

Familiarizing yourself with Git
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are not familiar with git, we encourage you to briefly look at
the `Git
Basics <https://git-scm.com/book/en/v2/Getting-Started-Git-Basics>`__
page.

Git Workflow
~~~~~~~~~~~~

The workflow for submitting a code change is, more or less, the
following:

1. Fork the TOM Toolkit repository to your own Github account. |image0|
2. Clone the forked repository to your local working machine.

::

     git clone git@github.com:<Your Username>/tom_base.git

3. Add the original “upstream” repository as a remote.

::

   git remote add upstream https://github.com/TOMToolkit/tom_base.git

4. Ensure that you’re synchronizing your repository with the “upstream”
   one relatively frequently.

::

   git fetch upstream
   git merge upstream/main

5. Create and checkout a branch for your changes (see `Branch
   Naming <#branch-naming>`__).

::

   git checkout -b <New Branch Name>

6. Commit frequently, and push your changes to Github. Be sure to merge
   main in before submitting your pull request.

::

   git push origin <Branch Name>

7. When your code is complete and tested, create a pull request from the
   upstream TOM Toolkit repository. |image1|

8. Be sure to click “compare across forks” in order to see your branch!
   |image2|

9. We may ask for some updates to your pull request, so revise as
   necessary and push when revisions are complete. This will
   automatically update your pull request.

Branch Naming
~~~~~~~~~~~~~

Branch names should be prefixed with the purpose of the branch, be it a
bugfix or an enhancement, along with a descriptive title for the branch.

::

     bugfix/fix-typo-target-detail
     feature/reticulating-splines
     enhancement/refactor-planning-tool

Code Style
~~~~~~~~~~

We recommend that you use a linter, as all pull requests must pass a
``flake8`` check. We also recommend configuring your editor to
automatically remove trailing whitespace, add newlines on save, and
other such helpful style corrections. You can check if your styling will
meet standards before submitting a pull request by doing a
``pip install flake8`` and running the same command our Github Actions
build does:

::

   flake8 tom_* --exclude=*/migrations/* --max-line-length=120

Documentation
~~~~~~~~~~~~~

We require any new features to

.. |image0| image:: /_static/fork.png
.. |image1| image:: /_static/pull-request.png
.. |image2| image:: /_static/compare-across-forks.png
