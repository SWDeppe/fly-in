
# Makefile for python code
# 
# > make help
#
# The following commands can be used.
#
# init:  sets up environment and installs requirements
# install:  Installs development requirments
# format:  Formats the code with autopep8
# lint:  Runs flake8 on src, exit if critical rules are broken
# clean:  Remove build and cache files
# env:  Source venv and environment files for testing
# leave:  Cleanup and deactivate venv
# test:  Run pytest
# run:  Executes the logic


VENV_PATH=./env/bin/activate
PYTHON_INTERPRETER=./env/bin/python3.10

###    GENERAL    ###
define find.functions
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'
endef


help:
	@echo 'The following commands can be used.'
	@echo ''
	$(call find.functions)


all: # Generates the venv and installs dependencies
all:
	@echo "Installing dependencies"
	@$(MAKE) install
	@echo "Generating your virtual environement in ./.env"
	@$(MAKE) env
	@echo "Installing .env dependencies"
	@$(MAKE) init

dev: all
	$(PYTHON_INTERPRETER) -m pip install -r requirements/dev.txt


###    ENVIRONNEMENT MANAGMENT    ###
init: ## sets up environment and installs requirements
init:
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt

install: ## Installs development requirments
install: 
	$(PYTHON_INTERPRETER) -m pip install -r requirements/dev.txt

SHELL := /bin/zsh
env: ## Source venv and environment files for testing
env: clip
	@$(PYTHON_INTERPRETER) -m venv env

clip:
	@echo "For activating run: source $(VENV_PATH) or run ctrl+V"
	echo "source $(VENV_PATH)" | xclip -selection clipboard 


###    PACKAGING    ###
#  				TODO: remove or use for ./modules/			#
# package: ## Create package in dist
# package: clean
# 	$(PYTHON_INTERPRETER) setup/setup.py sdist bdist_wheel

# upload-test: ## Create package and upload to test.pypi
# upload-test: package
# 	$(PYTHON_INTERPRETER) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/* --non-interactive --verbose

# upload: ## Create package and upload to pypi
# upload: package
# 	$(PYTHON_INTERPRETER) -m twine upload dist/* --non-interactive

##############################################################

###    DEBUG    ###
lint: ## Runs flake8 on src, exit if critical rules are broken
lint:
	@# stop the build if there are Python syntax errors or undefined names
	@echo flake8:
	@$(PYTHON_INTERPRETER) -m flake8 src --count --select=E9,F63,F7,F82 --show-source --statistics
	@# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	@$(PYTHON_INTERPRETER) -m flake8 src --count --exit-zero --statistics
	@echo "\n\nmypy":
	@$(PYTHON_INTERPRETER) -m mypy . --strict

test: ## Run pytest
test:
	@$(PYTHON_INTERPRETER) -m pytest . -p no:logging -p no:warnings

debug: # Run the project unsing PDB 

###    CLEANUP    ###
clean: ## Remove build and cache files
clean:
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
	rm -rf .pytest_cache
	# Remove all pycache
	find . | grep -E "(__pycache__|\.pyc|\.pyo)" | xargs rm -rf

leave: ## Cleanup and deactivate venv
leave: clean
	deactivate

