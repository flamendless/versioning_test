# Auto generation of release notes from commits -> markdown based on tags
#
#    Standard commit format to follow:

#        1. The following are accepted for CB commit:
#           (the important is the CB-XX at the start)
#            -> CB-XX - message
#            -> CB-XX message reference CB-YY
#            -> [CB-XX] - message
#            -> [CB-XX] message reference CB-YY
#
#        2. The following are accepted for HOTFIX commit:
#           (the important is the HOTFIX/hotfix at the start)
#            -> HOTFIX - hey
#            -> hotfix - hey
#            -> [HOTFIX] hey
#            -> [HOTFIX] hey
#
#
# Script by: Brandon Blanker Lim-it (@flamendless)
#
# (NOTE: this script is written for the specific use-case,
#        not yet modular and ready for other cases,
#        thus written badly for now
# )

import subprocess, re, os
from pprint import pprint
from dataclasses import dataclass
from typing import List, Dict, Tuple

PATH: str = "templates/contributors/release_notes"
APPEND_PATH: str = "templates/contributors/releases.md"

CMD_GIT_GET_TAG: List[str] = ["git", "describe", "--tags", "--abbrev=0"]
CMD_GIT_CREATE_TAG: List[str] = ["git", "tag", "<>"]
CMD_GIT_PUSH_TAG: List[str] = ["git", "push", "origin", "<>"]
CMD_GIT_PRETTY_LOGS: List[str] = ["git", "log", "--pretty=\"%s (%ae)\"", "<>"]
CMD_GIT_ADD_FILES: List[str] = ["git", "add", "<>", "<>"]
CMD_GIT_COMMIT_FILES: List[str] = ["git", "commit", "-m", "<>"]
CMD_GIT_PUSH: List[str] = ["git", "push"]

RE_HOTFIX = re.compile(r"^\[?[HOTFIX|hotfix]\]?")
RE_CB = re.compile(r"^\[?CB-?[0-9]*\]?")
RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

INDENT: str = "     "


@dataclass
class Commit:
    ticket: int
    msg: str
    email: str


@dataclass
class SemVer:
    major: int
    minor: int
    rel: int

    prefix_v: bool = True

    def __post_init__(self: "SemVer") -> None:
        print(f"Created: {self.to_string()}")

    def __getitem__(self, key: str) -> int:
        return int(getattr(self, key))

    def __setitem__(self, key: str, new_value: int) -> None:
        return setattr(self, key, new_value)

    def to_string(self: "SemVer") -> str:
        prefix: str = "v" if SemVer.prefix_v else ""
        return f"{prefix}{self.major}.{self.minor}.{self.rel}"

    def inc_semver(self: "SemVer", field: str) -> "SemVer":
        new_vals = {
            "major": self.major,
            "minor": self.minor,
            "rel": self.rel,
        }
        new_vals[field] = int(new_vals[field]) + 1
        return SemVer(**new_vals)

    @staticmethod
    def get_from_str(ver: str) -> "SemVer":
        major, minor, rel = ver.split(".")
        return SemVer(major, minor, rel)


def run_cmd(cmd: List[str]) -> str:
    try:
        val: bytes = subprocess.check_output(cmd)
        val: str = val.decode("utf-8").rstrip("\n")
        return val
    except subprocess.CalledProcessError as exc:
        raise Exception(exc)

def get_last_git_tag() -> Tuple[str, bool]:
    tags: List[str] = run_cmd(CMD_GIT_GET_TAG).split("\n")
    tag: str = tags[-1]
    if not tag:
        raise Exception("No semver tag found. Please create one. Example: v0.0.1")

    if tag.startswith("v"):
        return (tag[1:], True)
    if tag[0].isdigit():
        return (tag, False)

    raise Exception("Last tag is not a semver tag")

def create_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_CREATE_TAG[2] = tag
    subprocess.check_call(CMD_GIT_CREATE_TAG)

def push_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_PUSH_TAG[3] = tag
    subprocess.check_call(CMD_GIT_PUSH_TAG)

def get_diff_commits(prev_ver: str) -> List[str]:
    CMD_GIT_PRETTY_LOGS[3] = f"{prev_ver}..HEAD"
    commits: str = run_cmd(CMD_GIT_PRETTY_LOGS)
    commits: str = commits.replace("\"", "")
    return commits.split("\n")

def get_commits(prev_ver: str, ver: str) -> List[str]:
    CMD_GIT_PRETTY_LOGS[3] = f"{prev_ver}..{ver}"
    commits: str = run_cmd(CMD_GIT_PRETTY_LOGS)
    commits: str = commits.replace("\"", "")
    commits: List[str] = commits.split("\n")
    valid_commits: List[str] = []

    commit: str
    for commit in commits:
        if re.match(RE_CB, commit):
            valid_commits.append(commit)

    return valid_commits

def process_commits(commits: List[str]) -> List[Commit]:
    processed: List[Commit] = []

    commit: str
    for commit in commits:
        if commit.startswith("["):
            commit = commit[1:]
            closing_start = commit.find("]")
            commit = commit[:closing_start] + commit[(closing_start + 1):]

        email: str = re.findall(RE_EMAIL, commit)[0]

        cb_ticket: str = re.match(RE_CB, commit).group()
        n: List[str] = [i for i in cb_ticket if i.isdigit()]
        ticket: int = "".join(n)

        start2: int = len(f"CB-{ticket}  ")
        msg: str = commit[start2:-(len(email) + 3)]

        processed.append(Commit(ticket, msg, email))

    return processed

def group_by_tickets(commits: List[Commit]) -> Dict[str, List[Commit]]:
    grouped: Dict[str, List[Commit]] = {}
    commit: Commit
    for commit in commits:
        ticket: int = commit.ticket
        if ticket not in grouped:
            grouped[ticket] = []
        grouped[ticket].append(commit)
    return grouped

def check_is_hotfix(commits: List[str]) -> bool:
    commit: str
    for commit in commits:
        if re.match(RE_HOTFIX, commit):
            return True
    return False

def git_push(path: str, sv: SemVer):
    CMD_GIT_ADD_FILES[2] = path
    CMD_GIT_ADD_FILES[3] = APPEND_PATH
    add: str = run_cmd(CMD_GIT_ADD_FILES)
    print(add)

    CMD_GIT_COMMIT_FILES[3] = f"Generated release note: {sv.to_string()}"
    commit: str = run_cmd(CMD_GIT_COMMIT_FILES)
    print(commit)

    push: str = run_cmd(CMD_GIT_PUSH)
    print(push)

def run():
    last_tag_data: Tuple[str, bool] = get_last_git_tag()
    last_tag: str = last_tag_data[0]
    has_v: bool = last_tag_data[1]
    SemVer.prefix_v = has_v

    sv: SemVer = SemVer.get_from_str(last_tag)
    sv_ver: str = sv.to_string()
    commits: List[str] = get_diff_commits(sv_ver)
    is_hotfix: bool = check_is_hotfix(commits)
    print(f"{is_hotfix=}")

    new_sv: SemVer = None
    if is_hotfix:
        new_sv = sv.inc_semver("rel")
    else:
        new_sv = sv.inc_semver("minor")

    create_git_tag(new_sv)

    new_sv_ver: str = new_sv.to_string()
    commits: List[str] = get_commits(sv_ver, new_sv_ver)
    print(f"{commits=}")
    if not commits:
        return

    gen_list: List[Commit] = process_commits(commits)
    if not gen_list:
        return

    grouped: Dict[str, List[Commit]] = group_by_tickets(gen_list)

    filename: str = f"{PATH}/RELEASE_NOTES_{new_sv_ver}.md"
    with open(filename, "w") as file:
        lines: List[str] = []
        lines.append("--------------------------------\n\n")
        lines.append(f"       RELEASE {new_sv_ver}\n\n")
        lines.append(f"   (this is auto-generated)\n\n")
        lines.append(f"   (script by Brandon Lim-it)\n\n")
        lines.append("--------------------------------\n\n")

        ticket: int
        group: List[Commit]
        for ticket, group in grouped.items():
            is_multi: bool = len(group) > 1

            line: str = f"* CB-{ticket}"

            if not is_multi:
                lines.append(line)

            has_email: bool = False

            n: int
            commit: Commit
            for n, commit in enumerate(group):
                if is_multi:
                    if not has_email:
                        has_email = True
                        line = f"{line}  ({commit.email}):\n\n"
                        lines.append(line)
                    lines.append(f"{INDENT} {(n + 1)}. {commit.msg}\n")
                else:
                    lines.append(f"{commit.msg}  ({commit.email})\n")

            lines.append("\n")

        pprint(lines)
        file.writelines(lines)
    print(f"Written: {filename}")

    orig_data: str = ""
    with open(APPEND_PATH, "r") as file:
        orig_data = file.read()
    lines.append(orig_data)
    with open(APPEND_PATH, "w") as file:
        file.writelines(lines)
    print(f"Written: {APPEND_PATH}")

    # push_git_tag(new_sv)
    # git_push(filename, new_sv)


if __name__ == "__main__":
    if not os.path.exists(PATH):
        os.makedirs(PATH)

    if not os.path.exists(APPEND_PATH):
        from pathlib import Path
        Path(APPEND_PATH).touch()

    run()
