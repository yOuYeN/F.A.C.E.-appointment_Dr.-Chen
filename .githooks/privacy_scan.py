#!/usr/bin/env python3
"""
病人姓名外洩防線。名單在執行時從本機 gitignore 檔（names.local.js / history.local.js）
讀出，本檔本身不含任何姓名，可安全公開。

用法：
  privacy_scan.py staged            掃描已 staged 的檔案內容
  privacy_scan.py msg <file>        掃描 commit 訊息檔
  privacy_scan.py tree <sha>        掃描某 commit 的整棵樹
  privacy_scan.py msgrange <range>  掃描某 commit range 的所有訊息

命中 → exit 1 並印出檔名行號。找不到名單檔 → 印警告後放行（新 clone 尚無本機個資檔）。

已知極限（別把它當保證）：
  * `git commit --no-verify` / `git push --no-verify` 會整個跳過 hook。
  * 還沒登錄進本機個資檔的新病人抓不到。
  * pid 本身就是名字（英文暱稱）只警告不阻擋，見下方 PID_CONTEXT。
"""
import re
import subprocess
import sys
from pathlib import Path

LOCAL_FILES = ("names.local.js", "history.local.js")
CJK = r"一-鿿"

# 檔頭註解裡的欄位說明（如 name : '姓名'）會被誤抽成病人名，必須排除
PLACEHOLDERS = {"姓名", "name", "專屬碼", "療程／第幾次／備註"}

# 名字出現在這些位置＝當作 pid 值，只警告不阻擋（例：{"pid":"Mina"} / who:['LBZ']）
PID_CONTEXT = re.compile(r"""(?:"pid"|pid|who|sundayMorningWho|staffWho)\s*:""")


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def load_names(root: Path):
    """回傳 (variants, found_any_source)。variants 皆為要比對的字串。"""
    names, found = set(), False
    for fn in LOCAL_FILES:
        p = root / fn
        if not p.exists():
            continue
        found = True
        text = p.read_text(encoding="utf-8", errors="replace")
        # 先剝掉註解，否則檔頭的欄位說明 name : '姓名' 會被當成病人名
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
        for m in re.findall(r"name\s*:\s*'([^']+)'", text):
            names.update(x.strip() for x in re.split(r"[、,，]", m))
        for m in re.findall(r"SUNDAY_FIXED_NAME\s*=\s*'([^']+)'", text):
            names.add(m.strip())

    names -= PLACEHOLDERS
    variants = set()
    for n in filter(None, names):
        variants.add(n)
        # 三字中文名 → 去姓（顏OO → OO），今天就是漏在這裡
        if re.fullmatch(f"[{CJK}]{{3}}", n):
            variants.add(n[1:])
        # 英文名一律小寫比對
        if re.fullmatch(r"[A-Za-z]{3,}", n):
            variants.add(n.lower())
    return variants, found


def scan_text(text: str, variants, label: str):
    """回傳 (errors, warnings)，各為 [(label, lineno, variant, line)]。"""
    errors, warnings = [], []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for v in variants:
            hit = v in line or (v.isascii() and v.lower() in low)
            if not hit:
                continue
            if PID_CONTEXT.search(line):
                warnings.append((label, i, v, line.strip()[:90]))
            else:
                errors.append((label, i, v, line.strip()[:90]))
    return errors, warnings


def git(*args) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    ).stdout


def collect(mode, arg, variants):
    errors, warnings = [], []

    if mode == "staged":
        files = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACM").splitlines() if f]
        for f in files:
            blob = git("show", f":{f}")
            if "\0" in blob[:1024]:
                continue
            e, w = scan_text(blob, variants, f)
            errors += e
            warnings += w

    elif mode == "msg":
        errors_, warnings_ = scan_text(
            Path(arg).read_text(encoding="utf-8", errors="replace"), variants, "commit 訊息"
        )
        # 訊息裡沒有 pid 欄位語意，一律當錯誤
        errors += errors_ + warnings_

    elif mode == "tree":
        for f in git("ls-tree", "-r", "--name-only", arg).splitlines():
            if not f:
                continue
            blob = git("show", f"{arg}:{f}")
            if "\0" in blob[:1024]:
                continue
            e, w = scan_text(blob, variants, f)
            errors += e
            warnings += w

    elif mode == "msgrange":
        for sha in git("rev-list", arg).split():
            body = git("log", "-1", "--format=%B", sha)
            e, w = scan_text(body, variants, f"commit {sha[:7]} 訊息")
            errors += e + w

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: privacy_scan.py {staged|msg <file>|tree <sha>|msgrange <range>}")
    mode = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""

    root = repo_root()
    variants, found = load_names(root)
    if not found:
        print("⚠️  privacy_scan：找不到 names.local.js／history.local.js，無法比對姓名 → 放行。")
        print("   （新 clone 屬正常；但這代表這台機器上的防線是關的。）")
        return 0
    if not variants:
        print("⚠️  privacy_scan：名單解析為空 → 放行。請確認本機個資檔格式沒被改動。")
        return 0

    errors, warnings = collect(mode, arg, variants)

    for label, line, v, txt in warnings:
        print(f"⚠️  {label}:{line} 出現「{v}」但看起來是 pid 值 → 只警告。{txt}")

    if errors:
        print()
        print("🔴 偵測到病人姓名，已中止。")
        for label, line, v, txt in errors:
            print(f"   {label}:{line}  含「{v}」")
            print(f"      {txt}")
        print()
        print("   公開檔案與 commit 訊息一律只能用 pid（見 CORE_RULES 隱私鐵則）。")
        print("   真的要放行請自行判斷後加 --no-verify（會跳過所有檢查）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
