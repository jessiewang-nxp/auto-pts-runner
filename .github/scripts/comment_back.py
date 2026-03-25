import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path


def _safe_getenv(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def get_results_on_github_link() -> str:
    """Reproduce auto-pts 'Results on Github' link generation.

    auto-pts pushes the report folder into a git repo (bluetooth-qualification)
    and builds a link to the tree at HEAD.
    """

    repo_path = Path(r"C:\Dpc\bluetooth-qualification")
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path, text=True).strip()
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=repo_path, text=True).strip()
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", remote)
        if not m:
            return f"UNKNOWN_REMOTE ({remote})"
        return f"https://github.com/{m.group('owner')}/{m.group('repo')}/tree/{sha}"
    except Exception as e:
        return f"UNKNOWN_REMOTE ({e})"


def parse_report_txt() -> tuple[str, int, int, int]:
    """Return (repo_line, pass_cnt, fail_cnt, total)."""

    report_txt = Path(r"C:\Dpc\auto-pts\report.txt")
    if not report_txt.exists():
        return ("report missing", 0, 0, 0)

    lines = report_txt.read_text(encoding="utf-8", errors="ignore").splitlines()
    repo_line = lines[0] if lines else ""
    results = lines[1:] if len(lines) > 1 else []

    pass_cnt = sum(1 for l in results if "PASS" in l)
    fail_cnt = sum(1 for l in results if "FAIL" in l)
    total = len(results)

    return (repo_line, pass_cnt, fail_cnt, total)


def make_comment() -> str:
    board = _safe_getenv("BOARD")
    cases = _safe_getenv("CASES")
    autopts_ref = _safe_getenv("AUTOPTS_REF")
    zephyr_ref = _safe_getenv("ZEPHYR_REF")
    nb = _safe_getenv("NB", "false")

    run_url = ""
    server_url = _safe_getenv("GITHUB_SERVER_URL")
    repo = _safe_getenv("GITHUB_REPOSITORY")
    run_id = _safe_getenv("GITHUB_RUN_ID")
    if server_url and repo and run_id:
        run_url = f"{server_url}/{repo}/actions/runs/{run_id}"

    results_link = get_results_on_github_link()
    repo_line, pass_cnt, fail_cnt, total = parse_report_txt()

    body: list[str] = []
    body.append("### 3. Test Results")
    body.append("")
    body.append("**Summary**")
    body.append(f"- PASS: {pass_cnt}")
    body.append(f"- FAIL: {fail_cnt}")
    body.append(f"- Total: {total}")

    # Context (compact)
    ctx = []
    if board:
        ctx.append(f"board={board}")
    if cases:
        ctx.append(f"cases={cases}")
    if autopts_ref:
        ctx.append(f"auto-pts={autopts_ref}")
    if zephyr_ref:
        ctx.append(f"zephyr={zephyr_ref}")
    if nb.lower() == "true":
        ctx.append("nb=true")
    if ctx:
        body.append("")
        body.append("**Run Context**: `" + ", ".join(ctx) + "`")

    if repo_line:
        body.append("")
        body.append(f"**Repo**: `{repo_line}`")

    body.append("")
    body.append("**Logs**")
    body.append(f"- [Results on Github]({results_link})")
    if run_url:
        body.append(f"- [Actions Run]({run_url})")

    body.append("")
    body.append("Artifacts: report.xlsx / report.txt are attached in the Actions run.")

    return "\n".join(body)


def post_comment(comment: str) -> None:
    token = _safe_getenv("GITHUB_TOKEN")
    repo = _safe_getenv("GITHUB_REPOSITORY")
    issue = _safe_getenv("ISSUE_NUMBER")

    if not (token and repo and issue):
        raise RuntimeError("Missing env vars: GITHUB_TOKEN/GITHUB_REPOSITORY/ISSUE_NUMBER")

    url = f"https://api.github.com/repos/{repo}/issues/{issue}/comments"
    req = urllib.request.Request(
        url,
        data=json.dumps({"body": comment}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "auto-pts-runner",
        },
        method="POST",
    )
    urllib.request.urlopen(req).read()


def main() -> int:
    comment = make_comment()
    print("--- comment preview ---")
    print(comment)
    print("-----------------------")

    try:
        post_comment(comment)
        print("comment posted")
    except Exception as e:
        # Don't fail CI for comment problems
        print(f"comment failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
