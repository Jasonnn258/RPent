"""Final backup: memory + lightweight trajectories + manifest.

1. Copy resources/libero/* -> final_export/memories/ (preserve structure).
2. From logs/, copy lightweight artifacts (transcript, recipe, states, audit,
   json/jsonl/csv/md/config) into final_export/trajectories/ + configs/,
   skipping episode.mp4 and per-frame images.
3. Write experiment_manifest.csv (one row per suite/task/seed/attempt).
"""
import os, re, glob, json, shutil, csv, sys

REPO = "/vla_test/yjx/workspace/RPent"
LOGS = os.path.join(REPO, "logs")
EXPORT = os.path.join(REPO, "artifacts", "final_export")
MEM = os.path.join(EXPORT, "memories")
TRAJ = os.path.join(EXPORT, "trajectories")
CFG = os.path.join(EXPORT, "configs")
os.makedirs(MEM, exist_ok=True)
os.makedirs(TRAJ, exist_ok=True)
os.makedirs(CFG, exist_ok=True)

# ---- 1. memories ----
src_mem = os.path.join(REPO, "resources", "libero")
for root, dirs, files in os.walk(src_mem):
    rel = os.path.relpath(root, src_mem)
    dst = os.path.join(MEM, rel) if rel != "." else MEM
    os.makedirs(dst, exist_ok=True)
    for f in files:
        shutil.copy2(os.path.join(root, f), os.path.join(dst, f))
print(f"[1] memories copied from resources/libero -> memories/")

# ---- 2. lightweight trajectories ----
# keep these file patterns; skip episode.mp4 and images/ dirs
KEEP_EXT = {".json", ".jsonl", ".csv", ".md", ".txt", ".yaml", ".yml"}
KEEP_NAME = {"states.json", "run.log", "camera_meta.json"}
SKIP_DIRS = {"images", "images_cam", "images_cam_hi", "images_wrist", "images_wrist_hi",
             "world", "world_hi", "world_wrist", "world_wrist_hi", "depths", "depths_wrist",
             "segments", "action_videos", "wrist_meta"}
SKIP_FILES = {"episode.mp4"}

n_runs = 0
n_files = 0
for d in glob.glob(os.path.join(LOGS, "*_libero_*_t*_s*")):
    b = os.path.basename(d)
    m = re.match(r"^[\d:-]+_libero_([a-z_]+)_t(\d+)_s(\d+)$", b)
    if not m: continue
    suite, task, seed = m.group(1), m.group(2), m.group(3)
    dst = os.path.join(TRAJ, suite, f"t{task}", f"s{seed}")
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f in SKIP_FILES: continue
            ext = os.path.splitext(f)[1].lower()
            if f not in KEEP_NAME and ext not in KEEP_EXT: continue
            shutil.copy2(os.path.join(root, f), os.path.join(dst, f))
            copied += 1
    if copied > 0:
        n_runs += 1; n_files += copied
print(f"[2] trajectories: {n_runs} runs, {n_files} files -> trajectories/")

# ---- configs ----
for f in ["pyproject.toml", "SETUP_NOTES.md", "DATA_TRANSFER.md", "README.md"]:
    p = os.path.join(REPO, f)
    if os.path.exists(p): shutil.copy2(p, os.path.join(CFG, f))
for f in glob.glob(os.path.join(REPO, "*.sh")):
    shutil.copy2(f, os.path.join(CFG, os.path.basename(f)))
print(f"[3] configs copied")

# ---- 4. experiment_manifest.csv ----
def classify(run_dir):
    sf = os.path.join(run_dir, "states.json")
    if not os.path.exists(sf): return "infra_crash", None
    try:
        st = json.load(open(sf))
        term = st[-1].get("libero_terminated") if (isinstance(st, list) and st) else None
    except: return "infra_crash", None
    if term is True: return "success", True
    rl = os.path.join(run_dir, "run.log")
    if os.path.exists(rl):
        txt = open(rl, errors="ignore").read()
        if "API planner timed out" in txt: return "infra_timeout", False
        if "reached max_turns" in txt: return "policy_fail", False
    return "policy_fail", False

rows = []
for d in sorted(glob.glob(os.path.join(LOGS, "*_libero_*_t*_s*"))):
    b = os.path.basename(d)
    m = re.match(r"^([\d:-]+)_libero_([a-z_]+)_t(\d+)_s(\d+)$", b)
    if not m: continue
    ts, suite, task, seed = m.group(1), m.group(2), m.group(3), m.group(4)
    ftype, ok = classify(d)
    # attempt type: seed0 = bootstrap, else eval
    attempt = "bootstrap" if seed == "0" else "eval"
    rows.append({
        "ts": ts, "suite": suite, "task": int(task), "seed": int(seed),
        "attempt": attempt, "success": ok if ok is not None else "",
        "failure_type": ftype,
        "log_dir": d,
        "traj_dir": os.path.join("trajectories", suite, f"t{task}", f"s{seed}"),
        "memory_dir": os.path.join("memories", "results_" + suite.replace("libero_","") + "_pert"),
        "transcript": os.path.join(d, f"transcript_{suite.replace('libero_','')}_t{task}_s{seed}.json"),
        "recipe": os.path.join(d, f"recipe_{suite.replace('libero_','')}_t{task}_s{seed}.jsonl"),
        "states": os.path.join(d, "states.json"),
    })
# write manifest
mfest = os.path.join(EXPORT, "experiment_manifest.csv")
cols = ["ts","suite","task","seed","attempt","success","failure_type",
        "log_dir","traj_dir","memory_dir","transcript","recipe","states"]
with open(mfest, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
print(f"[4] manifest: {len(rows)} rows -> {mfest}")

# ---- summary stats ----
from collections import Counter, defaultdict
suite_stat = defaultdict(lambda: [0,0])
ftype_stat = Counter()
for r in rows:
    if r["success"] in (True, False):
        suite_stat[r["suite"]][1] += 1
        if r["success"] is True: suite_stat[r["suite"]][0] += 1
    ftype_stat[r["failure_type"]] += 1
print("\n=== 各 suite SR ===")
for s in sorted(suite_stat):
    ok, tot = suite_stat[s]
    print(f"  {s}: {ok}/{tot} ({ok/max(tot,1)*100:.0f}%)")
print("\n=== failure_type 分布 ===")
for k, v in ftype_stat.most_common():
    print(f"  {k}: {v}")
