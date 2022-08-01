import subprocess, re
from dataclasses import dataclass
from typing import List, Dict

CMD_GIT_GET_TAG: List[str] = ["git", "tag"]
CMD_GIT_CREATE_TAG: List[str] = ["git", "tag", "<>"]
CMD_GIT_PUSH_TAG: List[str] = ["git", "push", "origin", "<>"]
CMD_GIT_PRETTY_LOGS: List[str] = ["git", "log", "--pretty=\"%s (%ae)\"", "<>"]

RE_HOTFIX = re.compile(r"^(.)+[HOTFIX|hotfix]")
RE_CB = re.compile(r"^\[?CB-?[0-9]*\]?")
RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

INDENT: str = "  "


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

def get_commits(prev_ver: str, ver: str) -> List[str]:
    cmd: List[str] = CMD_GIT_PRETTY_LOGS.copy()
    cmd[3] = f"{prev_ver}..{ver}"
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
        email: str = re.findall(RE_EMAIL, commit)[0]

        start: int = commit.find("CB-")
        subticket: str  = commit[:(start + 4)]
        n: List[str] = [i for i in subticket if i.isdigit()]
        ticket: int = "".join(n)

        start2: int = len(f"CB-{ticket} ")
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

def run():
    last_tag: str = get_last_git_tag()
    sv: SemVer = SemVer.get_from_str(last_tag)
    last_commits: List[str] = get_last_commits(1)
    is_hotfix: bool = check_is_hotfix(last_commits)
    print(f"{is_hotfix=}")

    new_sv: SemVer = None
    if is_hotfix:
        new_sv = sv.inc_semver("rel")
    else:
        new_sv = sv.inc_semver("minor")

    create_git_tag(new_sv)

    new_sv_ver: str = new_sv.to_string()
    commits: List[str] = get_commits(sv.to_string(), new_sv_ver)
    if not commits:
        return

    gen_list: List[Commit] = process_commits(commits)
    if not gen_list:
        return

    grouped: Dict[str, List[Commit]] = group_by_tickets(gen_list)

    filename: str = f"RELEASE_NOTES_{new_sv_ver}.md"
    with open(filename, "w") as file:
        file.write("--------------------------------\n\n")
        file.write(f"     RELEASE {new_sv_ver}\n\n")
        file.write(f"   (this is auto-generated)\n\n")
        file.write("--------------------------------\n\n")

        ticket: int
        group: List[Commit]
        for ticket, group in grouped.items():
            is_multi: bool = len(group) > 1

            lines: List[str] = []
            line: str = f"* CB-{ticket}"

            if is_multi:
                line = line + "\n"
            else:
                line = f"{line} - "
                lines.append(line)

            has_email: bool = False

            n: int
            commit: Commit
            for n, commit in enumerate(group):
                if is_multi:
                    if not has_email:
                        has_email = True
                        line = f"{line} ({commit.email}) - \n"
                        lines.append(line)
                    lines.append(f"{INDENT} {n}. {commit.msg}\n")
                else:
                    lines.append(f"{commit.msg} ({commit.email})\n")

            file.writelines(lines)

    # push_git_tag(new_sv)


if __name__ == "__main__":
    run()
