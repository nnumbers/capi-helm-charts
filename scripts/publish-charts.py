#!/usr/bin/env python3

"""
This script publishes the charts from the specified directory to the specified
branch.

For each chart, it sets the "version" and "appVersion" before packaging it. It then
generates a Helm repository index and commits the charts and the index to the
specified branch.

The version is derived from a combination of the latest Git tag and the current SHA.
It assumes that the tags are SemVer compliant, i.e. are of the form
`<major>.<minor>.<patch>-<prerelease>`.

The appVersion is derived from the current SHA, as produced when using
`tags: type=sha,prefix=` with `docker/metadata-action`.

This means that referencing the chart at a particular SHA automatically picks up
the correct util image for that version.
"""

import contextlib
import pathlib
import os
import re
import subprocess
import tempfile
import urllib



@contextlib.contextmanager
def working_directory(directory):
    """
    Context manager that runs the wrapped code with the given directory as the
    working directory.

    When the context manager exits, the original working directory is restored.
    """
    previous_cwd = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous_cwd)


def cmd(command):
    """
    Execute the given command and return the output.
    """
    output = subprocess.check_output(command, text = True, stderr = subprocess.DEVNULL)
    return output.strip()


#: Regex that attempts to match a SemVer version
#: It allows the tag to maybe start with a "v"
SEMVER_REGEX = r"^v?(?P<major>[0-9]+).(?P<minor>[0-9]+).(?P<patch>[0-9]+)(-(?P<prerelease>[a-zA-Z0-9.-]+))?$"


def get_version():
    """
    Returns a SemVer-compliant version based on Git information for the current working directory.
    
    The version is based on the distance from the last tag and includes the name of the branch that the
    commit is on. It is is constructed such that the versions for a particular branch will order correctly.
    """
    try:
        # Start by trying to find the most recent tag
        last_tag = cmd(["git", "describe", "--tags", "--abbrev=0"])
    except subprocess.CalledProcessError:
        # If there are no tags, then set the parts in such a way that when we increment the patch version we get 0.1.0
        major_vn = 0
        minor_vn = 1
        patch_vn = -1
        prerelease_vn = None
        # Since there is no tag, just count the number of commits in the branch
        commits = int(cmd(["git", "rev-list", "--count", "HEAD"]))
    else:
        # If we found a tag, split into major/minor/patch/prerelease
        tag_bits = re.search(SEMVER_REGEX, last_tag)
        if tag_bits is None:
            raise RuntimeError(f'Tag is not a valid SemVer version - {last_tag}')
        major_vn = int(tag_bits.group('major'))
        minor_vn = int(tag_bits.group('minor'))
        patch_vn = int(tag_bits.group('patch'))
        prerelease_vn = tag_bits.group('prerelease')
        # Get the number of commits since the last tag
        commits = int(cmd(["git", "rev-list", "--count", f"{last_tag}..HEAD"]))

    if commits > 0:
        # If there are commits since the last tag and no existing prerelease part, increment the patch version
        if not prerelease_vn:
            patch_vn += 1
        # Add information to the prerelease part about the branch and number of commits
        # Get the name of the current branch
        branch_name = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]).lower()
        # Sanitise the branch name so it only has characters valid for a prerelease version
        branch_name = re.sub("[^a-zA-Z0-9-]+", "", branch_name).lower()
        prerelease_vn = '.'.join([prerelease_vn or "dev.0", branch_name, str(commits)])

    # Build the SemVer version from the parts
    version = f"{major_vn}.{minor_vn}.{patch_vn}"
    if prerelease_vn:
        version += f"-{prerelease_vn}"
    return version


def setup_publish_branch(branch, publish_directory):
    """
    Clones the specified branch into the specified directory.
    """
    server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
    repository = os.environ.get('GITHUB_REPOSITORY', 'stackhpc/capi-helm-charts')
    remote = f"{server_url}/{repository}.git"
    print(f"[INFO] Cloning {remote}@{branch} into {publish_directory}")
    # If there is a token in the environment, add it to the remote
    if 'GITHUB_TOKEN' in os.environ:
        print("[INFO] Adding authentication token to URL")
        token = os.environ['GITHUB_TOKEN']
        remote_parts = urllib.parse.urlsplit(remote)
        new_remote_parts = remote_parts._replace(netloc = f"x-access-token:{token}@{remote_parts.netloc}")
        remote = urllib.parse.urlunsplit(new_remote_parts)
        print(remote)
    # Try to clone the branch
    # If it fails, create a new empty git repo with the same remote
    try:
        cmd([
            'git',
            'clone',
            '--depth=1',
            '--single-branch',
            '--branch',
            branch,
            remote,
            publish_directory
        ])
    except subprocess.CalledProcessError:
        with working_directory(publish_directory):
            cmd(['git', 'init'])
            cmd(['git', 'remote', 'add', 'origin', remote])
            cmd(['git', 'checkout', '--orphan', branch])
    username = os.environ.get('GITHUB_ACTOR', 'github-actions-bot')
    email = f"{username}@users.noreply.github.com"
    print(f"[INFO] Configuring git to use username '{username}'")
    with working_directory(publish_directory):
        cmd(["git", "config", "user.name", username])
        cmd(["git", "config", "user.email", email])


def main():
    """
    Entrypoint for the script.
    """
    print(cmd(["git", "config", "--list"]))
    if 'CHART_DIRECTORY' in os.environ:
        chart_directory = pathlib.Path(os.environ['CHART_DIRECTORY']).resolve()
    else:
        chart_directory = pathlib.Path(__file__).resolve().parent.parent
    charts = [path.parent for path in pathlib.Path(chart_directory).glob('**/Chart.yaml')]
    print(f"[INFO] Detected {len(charts)} charts")
    publish_branch = os.environ.get('PUBLISH_BRANCH', 'gh-pages')
    print(f"[INFO] Charts will be published to branch '{publish_branch}'")
    version = get_version()
    print(f"[INFO] Charts will be published with version '{version}'")
    publish_directory = tempfile.mkdtemp()
    print(publish_directory)
#    with tempfile.TemporaryDirectory() as publish_directory:
    setup_publish_branch(publish_branch, publish_directory)
    for chart_directory in charts:
        print(f"[INFO] Packaging chart in {chart_directory}")
        cmd([
            "helm",
            "package",
            "--dependency-update",
            "--version",
            version,
            "--destination",
            publish_directory,
            chart_directory
        ])
    # Re-index the publish directory
    print("[INFO] Generating Helm repository index file")
    cmd(["helm", "repo", "index", publish_directory])
    with working_directory(publish_directory):
        print("[INFO] Committing changed files")
        cmd(["git", "add", "-A"])
        cmd(["git", "commit", "-m", f"Publishing charts for {version}"])
        print(f"[INFO] Pushing changes to branch '{publish_branch}'")
        cmd(["git", "push", "--set-upstream", "origin", publish_branch])


if __name__ == "__main__":
    main()
