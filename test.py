import subprocess, re
from dataclasses import dataclass
from typing import List


CMD_GIT_GET_TAG: List[str] = ["git", "tag"]
CMD_GIT_CREATE_TAG: List[str] = ["git", "tag", "<>"]
CMD_GIT_PUSH_TAG: List[str] = ["git", "push", "origin", "<>"]
CMD_GIT_PRETTY_LOGS: List[str] = ["git", "log", "--pretty=\"%s (%an)\"", "<>"]
RE_HOTFIX = re.compile(r"^(.)+[HOTFIX|hotfix]")


@dataclass
class SemVer:
    major: int
    minor: int
    rel: int

    def __post_init__(self: "SemVer") -> None:
        print(f"Initialized: {self.to_string()}")

    def __getitem__(self, key: str) -> int:
        return int(getattr(self, key))

    def __setitem__(self, key: str, new_value: int) -> None:
        return setattr(self, key, new_value)

    def to_string(self: "SemVer") -> str:
        return f"v{self.major}.{self.minor}.{self.rel}"

    def inc_semver(self: "SemVer", field: str) -> "SemVer":
        self[field] = self[field] + 1
        print(f"Incremented to: {self.to_string()}")
        return self

    @staticmethod
    def get_from_str(ver: str) -> "SemVer":
        major, minor, rel = ver.split(".")
        return SemVer(major, minor, rel)


def stdout_to_str(stdout: bytes) -> str:
    return stdout.decode("utf-8").rstrip("\n")

def get_last_git_tag() -> str:
    tags = None
    try:
        tags: bytes = subprocess.check_output(CMD_GIT_GET_TAG)
    except subprocess.CalledProcessError as exc:
        print(exc)
        return

    tags: List[str] = stdout_to_str(tags).split("\n")
    tag: str = tags[-1]

    if not tag.startswith("v"):
        raise Exception("Last tag is not a semver tag")
    return tag[1:]


def create_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_CREATE_TAG(2, tag)
    subprocess.check_call(CMD_GIT_CREATE_TAG)

def push_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_PUSH_TAG(3, tag)
    subprocess.check_call(CMD_GIT_PUSH_TAG)

def get_last_commits(n: int) -> List[str]:
    CMD_GIT_PRETTY_LOGS[3] = f"HEAD~{n}..HEAD"
    commits = None
    try:
        commits: bytes = subprocess.check_output(CMD_GIT_PRETTY_LOGS)
    except subprocess.CalledProcessError as exc:
        print(exc)
        return

    commits: str = stdout_to_str(commits)
    if not commits:
        return

    commits: List[str] = commits.split("\n")
    return commits

def get_latest_commits(ver: str) -> List[str]:
    CMD_GIT_PRETTY_LOGS[3] = f"{ver}..HEAD"
    logs = None
    try:
        logs: bytes = subprocess.check_output(CMD_GIT_PRETTY_LOGS)
    except subprocess.CalledProcessError as exc:
        print(exc)
        return

    logs: str = stdout_to_str(logs)
    if not logs:
        print("(No new commits since last tag)")
        return

    logs: List[str] = logs.split("\n")
    return logs


last_tag: str = get_last_git_tag()
sv: SemVer = SemVer.get_from_str(last_tag)
commits: List[str] = get_last_commits(1)

commit: str
for commit in commits:
    if re.match(RE_HOTFIX, commit):
        print(1)
        break

# sv = sv.inc_semver("major")
# logs: List[str] = get_latest_commits(sv.to_string())
# print(logs)
# create_git_tag(sv)
# push_git_tag(sv)
