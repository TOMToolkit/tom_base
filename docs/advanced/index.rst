***************
Advanced Topics
***************

.. toctree::
  :maxdepth: 1
  :hidden:

  backgroundtasks
  observation_module
  custom_code
  scripts
  strategies
  latex_generation
  querying
  exceptions


:doc:`Background Tasks <backgroundtasks>` - Learn how to set up an asynchronous task library to handle long
running and/or concurrent functions.

:doc:`Building a TOM Observation Facility Module <observation_module>` - Learn to build a module which will
allow your TOM to submit observation requests to observatories.

:doc:`Running Custom Code Hooks <custom_code>` - Learn how to run your own scripts when certain actions happen
within your TOM (for example, an observation completes).

:doc:`Scripting your TOM with Jupyter Notebooks <scripts>` - Use a Jupyter notebook (or just a python
console/scripts) to interact directly with your TOM.

:doc:`Observing and cadence strategies <strategies>` - Learn about observing and cadence strategies and how to write a
custom cadence strategy to automate a series of observations

:doc:`LaTeX table generation <latex_generation>` - Learn how to generate LaTeX for certain models and add LaTeX generators for other models

:doc:`Advanced Querying <querying>` - Get a couple of tips on programmatic querying with Django's QuerySet API

:doc:`Authentication exceptions for external services <exceptions>` - Ensure that your custom external services have 
  appropriate and visible errors.
