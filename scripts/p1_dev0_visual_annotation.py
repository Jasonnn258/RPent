#!/usr/bin/env python3
"""Local-only visual-evidence review for five frozen P1-DEV0 probe pairs.

build: Generates a self-contained HTML page embedding already created/private
RGB boards; no HTTP server, external JS, image upload or model inference.
summarize: Validates and counts manually exported visual *observability*
labels. Such labels are NOT audit-only physical grasp ground truth.

Examples:
 python3 scripts/p1_dev0_visual_annotation.py build
 python3 scripts/p1_dev0_visual_annotation.py summarize \
   --labels artifacts/p1_dev0/visual_review/visual_labels.json

The only changed files are local artifacts/p1_dev0/visual_review/*,
which are gitignored and contain sensitive images or annotations.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "artifacts" / "p1_dev0" / "visual_review"
PROTOCOL = "P1-DEV0-OFFLINE-RGB-OBSERVABILITY-REVIEW-V1"
CHOICES = {
    "target_visible_pre": ("yes", "no", "uncertain"),
    "target_visible_post": ("yes", "no", "uncertain"),
    "gripper_visible_post": ("yes", "no", "uncertain"),
    "object_gripper_relation_post": (
        "within_jaws_visible", "near_gripper", "separated",
        "occluded", "uncertain"),
    "temporal_visual_evidence": (
        "suggests_attachment", "suggests_detachment", "ambiguous"),
    "confidence": ("low", "medium", "high"),
}
DESCRIPTIONS = {
    "target_visible_pre": "Probe 前目标物体可见吗？",
    "target_visible_post": "Probe 后目标物体可见吗？",
    "gripper_visible_post": "Probe 后夹爪可见吗？",
    "object_gripper_relation_post": "Probe 后目标与夹爪的视觉关系",
    "temporal_visual_evidence": "前后图像对持握的视觉支持程度（非物理真值）",
    "confidence": "本次可视判断的置信度",
}


def _index(out: Path) -> list[dict]:
    data = json.loads((out / "review_index.json").read_text(encoding="utf-8"))
    if data.get("status") != "PRIVATE_BOARDS_WRITTEN_NOT_VISUAL_VERIFIER":
        raise ValueError("Visual review boards do not have the expected provenance gate")
    rows = data.get("cases")
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("Expected exactly 5 previous RGB review boards")
    ids = [r.get("episode_key") for r in rows]
    if len(set(ids)) != 5 or not all(
        isinstance(x, str) and x.startswith("p1dev0_t") and len(x) < 60
        for x in ids
    ):
        raise ValueError("Invalid or duplicate case IDs")
    for r in rows:
        name = r.get("board_name")
        if (not isinstance(name, str) or name != Path(name).name or
                not name.endswith("_paired_rgb.png")):
            raise ValueError("Unsafe or missing local board name")
    return rows


def _safe_json_for_js(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026")


def build(out: Path) -> Path:
    cases = _index(out)
    snippets = []
    total = 0
    for case in cases:
        file = out / case["board_name"]
        if not file.is_file():
            raise FileNotFoundError(file.name)
        blob = file.read_bytes()
        if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG signature: " + file.name)
        if len(blob) > 12 * 1024 * 1024:
            raise ValueError("PNG too large for a local offline review sheet")
        total += len(blob)
        if total > 40 * 1024 * 1024:
            raise ValueError("Private HTML would be too large")
        key = html.escape(case["episode_key"], quote=True)
        header = f'{key} · task {int(case["task"])} · arm {html.escape(case["arm"])}'
        controls = []
        for field, choices in CHOICES.items():
            opts = ''.join(
                f'<option value="{html.escape(val)}">{html.escape(val)}</option>'
                for val in choices
            )
            controls.append(
                f'<label>{html.escape(DESCRIPTIONS[field])}'
                f'<select data-field="{field}"><option value="">未填写 / UNKNOWN</option>'
                f'{opts}</select></label>'
            )
        image = base64.b64encode(blob).decode("ascii")
        snippets.append(
            f'<section class="case" data-case="{key}"><h2>{header}</h2>'
            f'<img alt="Pre/post RGB board for {key}" '
            f'src="data:image/png;base64,{image}">'
            f'<div class="fields">{"".join(controls)}</div>'
            '<label>可见性与遮挡说明（最多 500 字）'
            '<textarea data-notes rows="2" maxlength="500"></textarea></label>'
            '</section>'
        )
    page = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P1 DEV0 · Local Visual Observability Review</title>
<style>
body{font:15px/1.45 system-ui,-apple-system,sans-serif;max-width:1300px;margin:auto;
padding:22px;background:#fafafa;color:#242424}
h1{font-size:24px}h2{font-size:18px}
.case{background:white;border:1px solid #ccc;padding:16px;margin:18px 0;border-radius:8px}
img{display:block;max-width:100%;height:auto;border:1px solid #ddd;margin:12px 0}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:12px}
label{display:block;font-weight:600}select,textarea{display:block;width:100%;box-sizing:border-box;
padding:8px;margin-top:6px;background:white;border:1px solid #bbb;border-radius:4px}
textarea{margin-bottom:8px}button{background:#222;color:white;border:0;border-radius:5px;padding:12px 19px;cursor:pointer}
p.note{border-left:3px solid #888;padding-left:12px;color:#444}
</style></head><body>
<h1>P1 DEV0 · 离线 RGB 可辨识性审阅</h1>
<p class="note">仅使用本地已有图像。上排：Agentview Probe 前 / Probe 后 / 绝对差异；
下排：Wrist 前 / 纵向对齐后的 Probe 后 / 绝对差异。差异可能由机械运动、遮挡造成，
<b>不能视为抓取真值</b>。只判断目标与夹爪是否视觉可辨，无法确定时保留 UNKNOWN。
此页面不联网、不提交图像。点击导出将标注保存在浏览器下载目录。</p>
<div id="cases">__CARDS__</div>
<button id="export" type="button">导出本地视觉标注 JSON</button>
<p id="status"></p>
<script>
"use strict";
const protocol = __PROTOCOL__;
document.getElementById("export").addEventListener("click", () => {
  const entries = [];
  for (const block of document.querySelectorAll("section[data-case]")) {
    const obj = { episode_key: block.dataset.case };
    block.querySelectorAll("select[data-field]").forEach(x => {
      obj[x.dataset.field] = x.value || "unknown";
    });
    obj.notes = block.querySelector("textarea[data-notes]").value.slice(0, 500);
    entries.push(obj);
  }
  const payload = {protocol, items:entries,
    warning:"Subjective RGB observability evidence, not physical grasp ground truth"};
  const blob = new Blob([JSON.stringify(payload,null,2)+"\\n"], {type:"application/json"});
  const href=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=href;a.download="visual_labels.json";
  document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(href);
  document.getElementById("status").textContent="标注文件已请求下载（不会上传到外部服务）";
});
</script></body></html>
"""
    page = page.replace("__CARDS__", "\n".join(snippets))
    page = page.replace("__PROTOCOL__", _safe_json_for_js(PROTOCOL))
    file = out / "visual_review_local.html"
    file.write_text(page, encoding="utf-8")
    return file


def summarize(out: Path, label_file: Path) -> dict:
    cases = _index(out)
    expected = {row["episode_key"] for row in cases}
    obj = json.loads(label_file.read_text(encoding="utf-8"))
    if obj.get("protocol") != PROTOCOL:
        raise ValueError("Wrong reviewer protocol")
    items = obj.get("items")
    if not isinstance(items, list) or len(items) != 5:
        raise ValueError("Expected 5 visual observations; use 'unknown' for unseen")
    ids = [x.get("episode_key") for x in items]
    if set(ids) != expected or len(set(ids)) != 5:
        raise ValueError("Unknown/duplicate/missing frozen episode ID")
    counters = {k: Counter() for k in CHOICES}
    for r in items:
        if not isinstance(r.get("notes"), str) or len(r["notes"]) > 500:
            raise ValueError("Invalid notes")
        for field, choices in CHOICES.items():
            value = r.get(field, "unknown")
            if value != "unknown" and value not in choices:
                raise ValueError("Invalid visual label: " + field)
            counters[field][value] += 1
    answer = {
        "protocol": PROTOCOL,
        "status": "FIVE_VISUAL_OBSERVATIONS_RECORDED_NOT_GROUND_TRUTH",
        "n_episodes": 5,
        "annotation_file_sha256": hashlib.sha256(label_file.read_bytes()).hexdigest(),
        "counts": {k: dict(sorted(v.items())) for k, v in counters.items()},
        "unresolved_target_visibility_post": counters["target_visible_post"].get("no", 0)
          + counters["target_visible_post"].get("uncertain", 0)
          + counters["target_visible_post"].get("unknown", 0),
        "warning": "Human visual observations are subjective and may contain motion/occlusion bias. "
                   "They are not held-object oracle labels, causal effects, or online policy inputs.",
    }
    report = out / "visual_observability_summary.json"
    report.write_text(json.dumps(answer, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return answer


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("build", "summarize"))
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--labels", type=Path)
    args = ap.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((REPO / "artifacts").resolve()):
        ap.error("Output must stay under gitignored artifacts/")
    if args.mode == "build":
        print(json.dumps({"status": "OFFLINE_REVIEW_HTML_READY",
                          "file": str(build(out)),
                          "privacy": "Contains original image pixels; never commit/upload automatically"},
                         ensure_ascii=False, indent=2))
    else:
        if args.labels is None:
            ap.error("--labels required for summarize")
        report = summarize(out, args.labels)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
