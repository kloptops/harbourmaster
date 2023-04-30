# Tools

## ports_analyse.py

Requires a local Portmaster repo and the PortMaster-Hosting files downloaded, this will create the `pylibs/ports_info.py`

## pre-commit

The pre-commit script is designed to automatically populate the Harbourmaster GitHubRepoV1 source with the necessary details for your GitHub repository. By integrating this script into your pre-commit hooks, it ensures that the required files are generated consistently and accurately with every commit.

### Installation Instructions

To install and configure the pre-commit script for your GitHub repository, follow these steps:

- Download the Script: Start by downloading the pre-commit script file to your local machine.
- Modify Header Variables: Open the pre-commit script in a text editor, and locate the header section at the top. You will see a set of variables that need to be modified to match your GitHub repository details. Update the following variables:
    - PM_PRIORITY: the priority order of your source, lower means it is checked before others.
    - PM_PREFIX: the prefix given to your source.
    - PM_NAME: the of the name of your source.
    - GIT_USER_NAME: your GitHub username or organization name.
    - GIT_REPO_NAME: the name of your GitHub repository.
    - GIT_REPO_BRANCH: usually main, but replace with whatever branch you want to use.
    - GIT_ROOT_PATH: the root of the releases directory.
- Make sure to save the changes after modifying the variables.
- Move the Script: Move the modified pre-commit script file to the appropriate location within your GitHub repository. The exact location may vary depending on your repository's structure, but a common location is the .git/hooks/ directory. Ensure that the script is executable by running chmod +x pre-commit in the terminal (if necessary).

That's it! The pre-commit script should now be installed and operational for your GitHub repository, ensuring the Harbourmaster GitHubRepoV1 Source is populated correctly with the required files before each commit.
