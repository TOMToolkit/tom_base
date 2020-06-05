This README-dev is intended for maintainers of the repository for information on releases, standards, and anything that 
isn't pertinent to the wider community.

## Deployment
The [PyPi](https://pypi.org/project/tomtoolkit/) package is kept under the Las Cumbres Observatory PyPi account. The 
development and master branches are deployed automatically by TravisCI upon tagging either branch.

In order to trigger a PyPi deployment of either development or master, the branch must be given an annotated tag that 
matches the correct version format. The version formats are as follows:
 
|             | Development  | Master       | All other branches |
|-------------|--------------|--------------|--------------------|
| Tagged      | Push to PyPi | Push to PyPi | No effect          |
| Not tagged  | No effect    | No effect    | No effect          |

Tagged branches must follow the [semantic versioning syntax](https://semver.org/). Tagged versions will not be 
deployed unless they match the validation regex. The version format is as follows:

|   | Development   | Master |
|---|---------------|--------|
|   | x.y.z-alpha.w | x.y.z  |

Following deployment of a release, a Github Release is created, and this should be filled in with the relevant release notes.

## Deployment Workflow
  _**This section of this document is a work-in-progress**_
#### Pre-release deployment
* _meet pre-deployment criteria documented [here]()_.
* merge to `development`
* `git tag -a x.y.z-alpha.w -m "x.y.z-aplha.w"`
* `git push --tags`
* This causes Travis to create a draft release in GitHub and push to PyPI
* Edit the release notes in GitHub; Update, edit; repeat until satisfied. Release notes should contain:
  * Links to Read the Docs API (docstring) docs
  * Links to Read the Docs higher level docs
  * Link to Tom Demo feature demonstration
  * what else?
  
  For example: TODO: _insert example here_
* When satisfied, `Publish Release` Repo watchers are notified by email.
* deploy `tom-demo-dev` with new features demonstrated, pulling `tom_base-x.y.z-alpha.w` from PyPI


#### Public release deployment

* Create PR: `master <- development`
* Merge PR
* `git tag -a x.y.z -m "Release x.y.z"`
* `git push --tags` Triggers Travis to:
   * build, build
   * push release to PyPI
   * create GitHub draft release
* Update Release Notes in GitHub draft release. (This should be the accumulation of the all
  the development-release release notes:  For example, release notes for releases x.y.z-alpha.1,
  x.y.z-alpha.2, etc. should be combined into release notes for release x.y.z.
* Publish Release
* Post notification to Slack, Tom Toolkit workspace, #general channel. (In the future, we hope to
have automated release notification to a dedicated #releases slack channel).

### Preview Read the Docs doc strings
* `cd /path/to/tom_base/docs`
* `pip install -r requirements.txt  # make sure sphinx is installed to your venv`
* `make html  # make clean first, if things are weird`
* point a browser to the html files in `./_build/html/` to proof read before deployment 