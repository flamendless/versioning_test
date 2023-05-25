"""
AUTO-VERSION v2
@donlimit

Auto generation of release notes + tag from commits -> Markdown

No flag:
    * will create new git tag locally with incremented 'minor' version

Available flags:
    * test - no pushing to remote. Will delete created locally created new git tag
    * hotfix - increment 'rel'
    * push - push to remote the generated files and tag
"""

import os
import re
import subprocess
import sys

from collections import OrderedDict
from dataclasses import dataclass
from pprint import pprint
from typing import List, Dict, Tuple, Union, Pattern, Optional, OrderedDict as TOrderedDict

PATH_RELEASE_NOTES: str = "templates/contributors/release_notes"
PATH_TO_RELEASES_MD: str = "templates/contributors/releases.md"
SEPARATOR: str = " - "
INDENT: str = " " * 4
RE_EMAIL: Pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

CMDS: Dict[str, str] = {
    "get_tag": (
        "git rev-list --tags --timestamp --no-walk | "
        "sort -nr | "
        "head -n1 | "
        "cut -f 2 -d ' ' | "
        "xargs git describe --contains"
    ),
    "fetch_tags": "git fetch --tags origin",
    "delete_tag": "git tag --delete {}",
    "create_tag": "git tag {}",
    "push_tag": "git push origin {}",
    "pretty_log": "git log --pretty='%s (%ae)' {}",
    "add_files": "git add {} {}",
    "commit_files": "git commit -m {}",
    "push": "git push --set-upstream origin {}",
}

INCLUDE_COMMIT_PREFIX: List[str] = ["hotfix", "cb", "boss", "bossfin", "ob"]

@dataclass
class Index:
    major: int = 0
    minor: int = 1
    release: int = 2

@dataclass
class Commit:
    prefix: str
    msg: str
    email: str


def run_cmd(cmd: Union[List[str], str], shell: bool=False) -> str:
    try:
        print(f"Running: {cmd}")
        val: bytes = subprocess.check_output(cmd, shell=shell)
        val: str = val.decode("utf-8").rstrip("\n")
        return val
    except subprocess.CalledProcessError as exc:
        raise Exception(exc)

def get_latest_git_tag() -> str:
    tag: str = run_cmd(CMDS["get_tag"], shell=True)
    if not tag:
        raise Exception("No semver tag found. Please create one. Example: v0.0.1")

    if tag.startswith("v"):
        tag = tag[1:]

    if tag[0].isdigit():
        return tag

    raise Exception(f"Latest tag is not a valid semver tag. Got {tag}")

def create_git_tag(version: str) -> None:
    cmd: str = CMDS["create_tag"].format(version)
    _: str = run_cmd(cmd, shell=True)
    print(f"Created git tag: {version}")

def delete_git_tag(version: str) -> str:
    cmd: str = CMDS["delete_tag"].format(version)
    res: str = run_cmd(cmd, shell=True)
    return res

def push_all(path: str, version: str) -> None:
    cmd_add: str = CMDS["add_files"].format(path, PATH_TO_RELEASES_MD)
    res_add: str = run_cmd(cmd_add)
    print(f"Added files: {res_add}")

    msg: str = f"Generate release note: {version}"
    cmd_commit: str = CMDS["commit_files"].format(msg)
    res_commit: str = run_cmd(cmd_commit)
    print(f"Committed files: {res_commit}")

    branch_name: str = run_cmd("git branch --show-current")
    print(f"Current branch: {branch_name}")

    cmd_push: str = CMDS["push"].format(branch_name)
    res_push: str = run_cmd(cmd_push)
    print(f"Pushed: {res_push}")

    cmd_push_tag: str = CMDS["push_tag"].format(version)
    res_push_tag: str = run_cmd(cmd_push_tag)
    print(f"Pushed tag {version}: {res_push_tag}")


def to_semver(version: str) -> List[int]:
    semver: List[str] = version.split(".")
    return [int(c) for c in semver]

def create_new_version(latest_tag: str) -> str:
    semver_str: List[str] = latest_tag.split(".")
    semver: List[int] = [int(c) for c in semver_str]
    index: int = Index.release if ("hotfix" in sys.argv) else Index.minor
    semver[index] += 1
    semver = [str(x) for x in semver]
    return ".".join(semver)

def get_prefix(commit: str) -> str:
    index: int = commit.index(SEPARATOR)
    prefix: str = commit.strip()[:index]
    return prefix

def get_message(commit: str, prefix: str, email: str) -> str:
    msg: str = commit

    if msg.startswith(prefix):
        msg = msg[len(prefix):].strip()

    if msg[0] == "-":
        msg = msg[1:].strip()

    p_email: str = f"({email})"
    if msg.endswith(p_email):
        msg = msg[:len(msg) - len(p_email)].strip()

    return msg

def get_valid_commits(*, before: str, after: str) -> List[Commit]:
    cmd: str = CMDS["pretty_log"].format(f"{before}..{after}")
    raw_commits: str = run_cmd(cmd, shell=True)
    commits: List[str] = raw_commits.split("\n")

    valid_commits: List[Commit] = []
    for commit in commits:
        sanitized_commit: str = commit.strip()

        for pre in INCLUDE_COMMIT_PREFIX:
            prefixes: Tuple[str, str] = (pre, pre.upper())
            if sanitized_commit.startswith(prefixes):
                res: List[Optional[str]] = re.findall(RE_EMAIL, commit)
                if not res:
                    break

                prefix: str = get_prefix(sanitized_commit)
                email: str = res[0]
                c: Commit = Commit(
                    prefix=prefix,
                    msg=get_message(sanitized_commit, prefix, email),
                    email=email,
                )

                valid_commits.append(c)
                break

    return valid_commits

def group_commits(commits: List[Commit]) -> TOrderedDict[str, List[Commit]]:
    grouped: TOrderedDict[str, List[Commit]] = OrderedDict()
    for commit in commits:
        prefix: str = commit.prefix
        if prefix not in grouped:
            grouped[prefix] = []
        grouped[prefix].append(commit)
    return grouped

def generate_lines(
    version: str,
    grouped_commits: TOrderedDict[str, List[Commit]]
) -> List[str]:
    lines: List[str] = [
        "--------------------------------\n\n",
        f"       RELEASE {version}\n\n",
        "   (this is auto-generated)\n\n",
        "   (script by @omi-donlimit)\n\n",
        "--------------------------------\n\n",
    ]

    for prefix, commits in grouped_commits.items():
        line: str = f"* {prefix}"

        if len(commits) == 1:
            line = f"{line} - {commits[0].msg} ({commits[0].email})"
            lines.append(line)
            continue

        lines.append(f"{line}:")
        for n, commit in enumerate(commits[::-1]):
            line = f"{INDENT} {n + 1}. {commit.msg} ({commit.email})\n"
            lines.append(line)

        lines.append("\n")

    return lines


def generate_release(filename: str, lines: List[str]) -> None:
    with open(filename, "w") as file:
        file.writelines(lines)
        print(f"Written: {filename}")

    with open(PATH_TO_RELEASES_MD, "r") as file:
        orig_data: str = file.read() or ""
        lines.append(orig_data)

    with open(PATH_TO_RELEASES_MD, "w") as file:
        file.writelines(lines)
        print(f"Written: {PATH_TO_RELEASES_MD}")

def run(new_version: str) -> bool:
    is_test: bool = "test" in sys.argv
    create_git_tag(new_version)

    valid_commits: List[Commit] = get_valid_commits(before=latest_tag, after=new_version)
    if not valid_commits:
        print("No valid commits to process. Exiting early.")
        return False

    grouped_commits: TOrderedDict[str, List[Commit]] = group_commits(valid_commits)

    filename: str = f"{PATH_RELEASE_NOTES}/RELEASE_NOTES_{new_version}.md"
    lines: List[str] = generate_lines(new_version, grouped_commits)
    pprint(lines)

    if is_test:
        return False

    if "push" in sys.argv:
        generate_release(filename, lines)
        push_all(filename, new_version)

    return True


if __name__ == "__main__":
    if not os.path.exists(PATH_RELEASE_NOTES):
        os.makedirs(PATH_RELEASE_NOTES)

    if not os.path.exists(PATH_TO_RELEASES_MD):
        from pathlib import Path
        Path(PATH_TO_RELEASES_MD).touch()

    print(f"Args: {sys.argv}")

    run_cmd(CMDS["fetch_tags"], shell=True)

    latest_tag: str = get_latest_git_tag()
    print(f"Latest Tag: {latest_tag}")

    new_version: str = create_new_version(latest_tag)
    print(f"New Tag: {new_version}")

    try:
        success: bool = run(new_version)
        if not success:
            delete_git_tag(new_version)
    except Exception as exc:
        print(exc)
        delete_git_tag(new_version)
