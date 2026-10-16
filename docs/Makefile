# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# this rule builds a single file and is used by the watch rule (below).
html-file:
	@test -n "$(FILE)" || { echo "usage: make html-file FILE=path/to/page.rst"; exit 1; }
	@$(SPHINXBUILD) -b html -d "$(BUILDDIR)/doctrees" "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS) $(O) "$(FILE)"

# type 'make watch' to build files as they are saved
watch:
	@echo "Watching $(SOURCEDIR) for changes to .rst and .md files; Ctrl-C to stop."
	@inotifywait -m -r -q -e close_write,moved_to --format '%w%f' --include '\.(rst|md)$$' \
	    "$(SOURCEDIR)" "@$(SOURCEDIR)/$(BUILDDIR)" \
	| while read -r changed; do \
	    echo "==> $$changed"; \
	    $(MAKE) --no-print-directory html-file FILE="$$changed"; \
	done

# Here's how do that (i.e. 'make watch') from the CLI not using make:
#
#     inotifywait -m -r -q -e close_write,moved_to --format '%w%f' --include '\.(rst|md)$' . @./_build \
#         | while read -r changed; do make html-file FILE="$changed"; done

.PHONY: help html-file watch Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
