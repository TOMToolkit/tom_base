This README-dev is intended for maintainers of the repository for information on releases, standards, and anything that 
isn't pertinent to the wider community.

## Deployment
The [PyPi](https://pypi.org/project/tomtoolkit/) package is kept under the Las Cumbres Observatory PyPi account. The 
dev and main branches are deployed automatically by TravisCI upon tagging either branch.

In order to trigger a PyPi deployment of either dev or main, the branch must be given an annotated tag that 
matches the correct version format. The version formats are as follows:
 
|             | Dev  | Main         | All other branches |
|-------------|--------------|--------------|--------------------|
| Tagged      | Push to PyPi | Push to PyPi | No effect          |
| Not tagged  | No effect    | No effect    | No effect          |

Tagged branches must follow the [semantic versioning syntax](https://semver.org/). Tagged versions will not be 
deployed unless they match the validation regex. The version format is as follows:

|   | Dev   | Main   |
|---|---------------|--------|
|   | x.y.z-alpha.w | x.y.z  |

Following deployment of a release, a Github Release is created, and this should be filled in with the relevant release notes.

## Deployment Workflow
  _**This section of this document is a work-in-progress**_

### Pre-release deployment
1. Meet pre-deployment criteria.
   * Includes appropriate release notes, including breaking changes, in `releasenotes.md`.
   * Pass [Codacy code quality check](https://app.codacy.com/gh/TOMToolkit/tom_base/pullRequests).
   * Doesn't decrease [Coveralls test coverage](https://coveralls.io/github/TOMToolkit/tom_base).
   * Passes [Travis tests and code style check](https://travis-ci.com/github/TOMToolkit/tom_base/branches).
   * Successfully builds [ReadTheDocs documentation](https://readthedocs.org/projects/tom-toolkit/builds/) (not an automated check) (TODO: fix webhook).
   * One review approval by a repository owner.
  
2. Merge your feature branch into the `dev` branch
   * `git checkout dev`
   * `git merge feature/your_feature_branch`

3. Tag the release, triggering GitHub and PyPI actions:

   Release tags must follow [semantic versioning](https://semver.org) syntax.
   * `git tag -a x.y.z-alpha.w -m "x.y.z-alpha.w"`
   * `git push --tags`
      * Pushing the tags causes Travis to create a draft release in GitHub and push to PyPI
      
4. Deploy `tom-demo-dev` with new features demonstrated, pulling `tomtoolkit==x.y.z-alpha.w` from PyPI.

   Examples:
     * Release of observation templates should include saving an observation template and submitting an observation via the observation_template
     * Release of manual facility interface should include an implementation of the new interface
     * Release of a new template tag should include that template tag in a template

5. Edit the Release Notes in GitHub

   When the tags were pushed above, GitHub created draft Release Notes
   which need to be filled out. (These can be found by following the `releases` link on the [front page](https://github.com/TOMToolkit/tom_base) of the repo.
   Or, [here](https://github.com/TOMToolkit/tom_base/releases)).
   
   Edit, Update, and repeat until satisfied.
   Release notes should contain (as needed):
   * Links to Read the Docs API (docstring) docs
   * Links to Read the Docs higher level docs
   * Link to Tom Demo feature demonstration
   * Links to issues that have been fixed
  
6. Publish the Release 

   When satisfied with the Release Notes, `Publish Release`.
   Repo watchers are notified by email.

### Public release deployment
The public release deployment workflow parallels the pre-release deployment work flow
and more details for a particular step may be found above.
 
1. Create PR: `main <- dev`
2. Meet pre-deployment criteria.
   * Include docstrings for any new or updated methods
   * Include tutorial documentation for any new major features as needed
   * Pass [Codacy code quality check](https://app.codacy.com/gh/TOMToolkit/tom_base/dashboard?bid=18204585).
   * Doesn't decrease [Coveralls test coverage](https://coveralls.io/github/TOMToolkit/tom_base?branch=dev).
   * Passes [Travis tests and code style check](https://travis-ci.com/github/TOMToolkit/tom_base/branches).
   * Successfully builds [ReadTheDocs documentation](https://readthedocs.org/projects/tom-toolkit/builds/) (not an automated check) (TODO: fix webhook).

3. Merge PR
   * Must be a repository owner to merge.

4. Tag the release, triggering GitHub and PyPI actions:
   * `git tag -a x.y.z -m "Release x.y.z"` -- must follow semantic versioning
   * `git push --tags` Triggers Travis to:
   * build, build
   * push release to PyPI  
   * create GitHub draft release
    
5. deploy `tom-demo` with new features demonstrated, pulling `tomtoolkit==x.y.z` from PyPI

6. Update Release Notes in GitHub draft release.
   
   This should be the accumulation of the all
   the dev-release release notes:  For example, release notes for releases x.y.z-alpha.1,
    x.y.z-alpha.2, etc. should be combined into release notes for release x.y.z.

7.  Publish Release

8.  Post notification to Slack, Tom Toolkit workspace, #general channel. (In the future, we hope to
have automated release notification to a dedicated #releases slack channel).

## Development Notes - Doing checks locally

### Preview Read the Docs doc strings
* `cd /path/to/tom_base/docs`
* `pip install -r requirements.txt  # make sure sphinx is installed to your venv`
* `make html  # make clean first, if things are weird`
* point a browser to the html files in `./_build/html/` to proof read before deployment 

### Run code style checks
* `pip install pycodestyle`
* `pycodestyle tom_* --exclude=*/migrations/* --max-line-length=120`

### Run tests
* `./manage.py test`

* Examples for running specific tests or test suites:
  * `./manage.py test tom_targets.tests`
  * `./manage.py test tom_targets.tests.tests.TestTargetDetail`
  * `./manage.py test tom_targets.tests.tests.TestTargetDetail.test_sidereal_target_detail`
