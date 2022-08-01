import subprocess
from dataclasses import dataclass
from typing import List

CMD_GIT_GET_TAG: List[str] = ["git", "describe", "--tags", "--abbrev=0"]
CMD_GIT_CREATE_TAG: List[str] = ["git", "tag"]
CMD_GIT_PUSH_TAG: List[str] = ["git", "push", "origin"]

@dataclass
class SemVer:
    major: int
    minor: int
    rel: int

    def __getitem__(self, key: str):
        return int(getattr(self, key))

    def __setitem__(self, key: str, new_value: int):
        return setattr(self, key, new_value)

    def inc_semver(self: "SemVer", field: str) -> "SemVer":
        self[field] = self[field] + 1
        return self

    def to_string(self: "SemVer") -> str:
        return f"v{self.major}.{self.minor}.{self.rel}"

    @staticmethod
    def get_from_str(ver: str) -> "SemVer":
        major, minor, rel = ver.split(".")
        return SemVer(major, minor, rel)

def get_last_git_tag() -> str:
    tag = None
    try:
        tag: str = subprocess.check_output(CMD_GIT_GET_TAG)
    except subprocess.CalledProcessError as exc:
        print(exc)
        return

    tag.decode("utf-8").replace("\n", "")
    if not tag.startswith("v"):
        raise Exception("Last tag is not a semver tag")
    return tag[1:]


def create_git_tag(semver: SemVer):
    tag: str = semver.to_string()
    CMD_GIT_CREATE_TAG[2] = tag
    CMD_GIT_PUSH_TAG[3] = semver.to_string()
    subprocess.check_call(CMD_GIT_CREATE_TAG)
    subprocess.check_call(CMD_GIT_PUSH_TAG)


last_tag = get_last_git_tag()
# sv = SemVer.get_from_str(last_tag).inc_semver("major")
# create_git_tag(sv)
