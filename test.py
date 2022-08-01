import subprocess, re
from dataclasses import dataclass
from typing import List

CMD_GIT_GET_TAG: List[str] = ["git", "tag"]
CMD_GIT_CREATE_TAG: List[str] = ["git", "tag", "<>"]
CMD_GIT_PUSH_TAG: List[str] = ["git", "push", "origin", "<>"]
CMD_GIT_PRETTY_LOGS: List[str] = ["git", "log", "--pretty=\"%s (%an)\"", "<>"]
CMD_GET_CB_COMMITS: List[str] = ["grep", "-i", "-E", "^\[?CB-?[0-9]*\]?"]
RE_HOTFIX = re.compile(r"^(.)+[HOTFIX|hotfix]")


@dataclass
class SemVer:
    major: int
    minor: int
    rel: int

    def __post_init__(self: "SemVer") -> None:
        print(f"Created: {self.to_string()}")

    def __getitem__(self, key: str) -> int:
        return int(getattr(self, key))

    def __setitem__(self, key: str, new_value: int) -> None:
        return setattr(self, key, new_value)

    def to_string(self: "SemVer") -> str:
        return f"v{self.major}.{self.minor}.{self.rel}"

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

def get_last_git_tag() -> str:
    tags: List[str] = run_cmd(CMD_GIT_GET_TAG).split("\n")
    tag: str = tags[-1]
    if not tag.startswith("v"):
        raise Exception("Last tag is not a semver tag")
    return tag[1:]

def create_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_CREATE_TAG[2] = tag
    subprocess.check_call(CMD_GIT_CREATE_TAG)

def push_git_tag(semver: SemVer) -> None:
    tag: str = semver.to_string()
    CMD_GIT_PUSH_TAG[3] = tag
    subprocess.check_call(CMD_GIT_PUSH_TAG)

def get_last_commits(n: int) -> List[str]:
    CMD_GIT_PRETTY_LOGS[3] = f"HEAD~{n}..HEAD"
    commits: str = run_cmd(CMD_GIT_PRETTY_LOGS)
    if not commits:
        return
    return commits.split("\n")

def generate_release_list(prev_ver: str, ver: str) -> List[str]:
    cmd: List[str] = CMD_GIT_PRETTY_LOGS.copy()
    cmd[3] = f"{prev_ver}..{ver}"

    p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(CMD_GET_CB_COMMITS, stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    out, err = p2.communicate()
    print(out, err)
    return out

def check_is_hotfix(commits: List[str]) -> bool:
    commit: str
    for commit in commits:
        if re.match(RE_HOTFIX, commit):
            return True
    return False



last_tag: str = get_last_git_tag()
sv: SemVer = SemVer.get_from_str(last_tag)
commits: List[str] = get_last_commits(1)
is_hotfix: bool = check_is_hotfix(commits)
print(f"{is_hotfix=}")

new_sv: SemVer = None
if is_hotfix:
    new_sv = sv.inc_semver("rel")
else:
    new_sv = sv.inc_semver("minor")

create_git_tag(new_sv)

gen_list: List[str] = generate_release_list(sv.to_string(), new_sv.to_string())
for note in gen_list:
    print(note)

# push_git_tag(new_sv)
