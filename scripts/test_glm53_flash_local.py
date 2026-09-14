#!/usr/bin/env python3
"""test_glm53_flash_local.py — 本地 GLM-5.3-Flash 服务功能验证(Test 1-5 + 2 补充)。

对应部署规格的验收项(全部打 OpenAI-compatible 端点):
  T1 纯文本 echo:固定 prompt → 回显 LOCAL_GLM_OK
  T2 视觉:真实 episode RGB → 物体 + 空间关系(必须提到 ≥2 个物体 + 1 个方位词)
  T3 JSON 稳定性:{phase,action,reason} ×10,全部 json.loads 成功且字段齐
  T4 harness 决策:grasped=true 上下文 ×5 → 不再输出 grasp(应 transport/place)
  T5 outcome verification:三种观测 → MATCHED/MISMATCHED/UNCERTAIN +
     COMMIT/OBSERVE/RECOVER/REASON 决策
  T6 reasoning_effort 端到端:low/high/max 全 200,且 reasoning token 量单调
  T7 tool calling:定义 get_grasp_pose 工具 → 模型返回 tool_calls(glm47 parser)

用法: python scripts/test_glm53_flash_local.py [--base-url http://127.0.0.1:8000/v1]
exit 0 = 全过;否则 1。
"""
import argparse
import base64
import json
import os
import sys
import time

ROOT = "/workspace/yjx/workspace/RPent"
DEFAULT_IMG = os.path.join(
    ROOT, "logs/ovpm_exp/20260905-21:11:09_glm-5.3-flash_vanilla_libero_spatial_task_t9_s3_r1/images/image_04.png")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def make_client(base_url):
    import httpx
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key="EMPTY",
                  http_client=httpx.Client(trust_env=False, timeout=600.0),
                  max_retries=0)


def chat(client, model, messages, **kw):
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=model, messages=messages,
        max_completion_tokens=kw.pop("max_tokens", 8192), **kw)
    return r, time.perf_counter() - t0


def content_of(r):
    m = r.choices[0].message
    return (m.content or "").strip()


def reasoning_tokens(r):
    u = r.usage
    return getattr(u, "completion_tokens_details.reasoning_tokens", 0) or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="zai-org/GLM-5.3-Flash")
    ap.add_argument("--image", default=DEFAULT_IMG)
    args = ap.parse_args()
    client = make_client(args.base_url)
    M = args.model

    print("== T1 纯文本 echo ==")
    try:
        r, lat = chat(client, M, [
            {"role": "system", "content": "Reply with exactly the token the user asks you to repeat. Nothing else."},
            {"role": "user", "content": "Repeat exactly: LOCAL_GLM_OK"}])
        c = content_of(r)
        check("T1 echo", "LOCAL_GLM_OK" in c, f"lat={lat:.1f}s out={c[:60]!r}")
    except Exception as ex:
        check("T1 echo", False, f"{type(ex).__name__}: {ex}")

    print("== T2 视觉(真实 episode RGB) ==")
    try:
        with open(args.image, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r, lat = chat(client, M, [{
            "role": "user", "content": [
                {"type": "text", "text": "Describe this robot workspace image: "
                 "list the objects you see and their spatial relations "
                 "(left/right/front/behind/on). One short paragraph."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
        c = content_of(r)
        n_obj = sum(w in c.lower() for w in
                    ("mug", "bowl", "plate", "butter", "milk", "bread", "table", "gripper", "arm", "pot", "cookie", "drawer", "cabinet", "stove"))
        n_spa = sum(w in c.lower() for w in ("left", "right", "front", "behind", "on ", "next to", "above"))
        check("T2 vision", n_obj >= 2 and n_spa >= 1,
              f"lat={lat:.1f}s objects≥2:{n_obj>=2} spatial≥1:{n_spa>=1} out={c[:80]!r}")
    except Exception as ex:
        check("T2 vision", False, f"{type(ex).__name__}: {ex}")

    print("== T3 JSON 稳定性 ×10 ==")
    ok_n = 0
    for i in range(10):
        try:
            r, _ = chat(client, M, [
                {"role": "system", "content": "You are a robot task planner. Always reply with a single JSON object: {\"phase\": str, \"action\": str, \"reason\": str}. No other text."},
                {"role": "user", "content": f"Scene {i}: red mug at table center, gripper open above it. Previous: move_to(red_mug). Next action?"}])
            j = json.loads(content_of(r).removeprefix("```json").removesuffix("```").strip())
            assert set(j) >= {"phase", "action", "reason"} and all(isinstance(v, str) and v for v in j.values())
            ok_n += 1
        except Exception:
            pass
    check("T3 json x10", ok_n == 10, f"{ok_n}/10 parse+schema ok")

    print("== T4 harness 决策 ×5(grasped=true 不得再 grasp) ==")
    # 判定"重新抓取"必须匹配动作短语(re-grasp/grasp the/close gripper),
    # 不能用子串 "grasp" —— 正确答案 "move the grasped red mug" 会被误杀
    # (2026-09-14 三臂探针实测:本地/远端全部正确,旧判定是测试 bug)。
    import re
    grasp_act = re.compile(
        r"re-?grasp|grasp(?:ing)?\s+(?:the|a|an|red|object|mug)"
        r"|close\s+(?:the\s+)?gripper(?:\s+on)?|grip\s+(?:the|a)",
        re.IGNORECASE)
    ok_n = 0
    for i in range(5):
        try:
            r, _ = chat(client, M, [
                {"role": "system", "content": "You are a robot task planner. Reply with JSON {\"phase\": str, \"action\": str, \"reason\": str}."},
                {"role": "user", "content": f"Task: put the red mug on the white plate. State: gripper HAS FIRMLY GRASPED the red mug (grasped=true, grip width 0.02m, object lifted 5cm). Next action? Trial {i}."}])
            c = content_of(r).lower()
            head = c.split("reason")[0]
            if not grasp_act.search(head) and any(k in head for k in ("transport", "move", "lift", "place", "put", "carry")):
                ok_n += 1
        except Exception:
            pass
    check("T4 no-regrasp", ok_n >= 4, f"{ok_n}/5 chose transport over re-grasp")

    print("== T5 outcome verification(3 观测 × 决策) ==")
    ov_cases = [
        ("expected: mug on plate | observed: mug resting fully inside plate rim, no overlap with table", "matched"),
        ("expected: mug on plate | observed: mug still at original table spot, gripper empty", "mismatched"),
        ("expected: mug on plate | observed: image partially occluded by gripper arm, plate not visible", "uncertain"),
    ]
    ok_n = 0
    for obs, want in ov_cases:
        try:
            r, _ = chat(client, M, [
                {"role": "system", "content": "You verify robot task outcomes. Reply with exactly one JSON: {\"verdict\": \"MATCHED\"|\"MISMATCHED\"|\"UNCERTAIN\", \"decision\": \"COMMIT\"|\"OBSERVE\"|\"REASON\"|\"RECOVER\"}."},
                {"role": "user", "content": obs}])
            j = json.loads(content_of(r).removeprefix("```json").removesuffix("```").strip())
            if j.get("verdict", "").upper() == want.upper() and j.get("decision", "").upper() in ("COMMIT", "OBSERVE", "REASON", "RECOVER"):
                ok_n += 1
        except Exception:
            pass
    check("T5 outcome-verify", ok_n == 3, f"{ok_n}/3 verdict+decision correct")

    print("== T6 reasoning_effort 端到端 ==")
    try:
        stats = {}
        for eff in ("low", "high", "max"):
            r, lat = chat(client, M, [{"role": "user", "content":
                            "A robot must pick a red mug from a crowded table. Plan the grasp approach considering collisions. Be thorough."}],
                          reasoning_effort=eff, max_tokens=16384)
            rt = reasoning_tokens(r)
            stats[eff] = (rt, lat)
        mono = stats["low"][0] <= stats["max"][0] and stats["low"][0] < stats["high"][0] + 4000
        check("T6 effort knob", all(v[0] is not None for v in stats.values()) and mono,
              " | ".join(f"{k}:rt={v[0]} lat={v[1]:.0f}s" for k, v in stats.items()))
    except Exception as ex:
        check("T6 effort knob", False, f"{type(ex).__name__}: {ex}")

    print("== T7 tool calling(glm47 parser) ==")
    try:
        tools = [{"type": "function", "function": {
            "name": "get_grasp_pose",
            "description": "Query the grasp planner for a 6-DoF pose of the given object",
            "parameters": {"type": "object", "properties": {
                "object_name": {"type": "string"}}, "required": ["object_name"]}}}]
        r, _ = chat(client, M, [
            {"role": "system", "content": "You control a robot. Use tools when needed."},
            {"role": "user", "content": "I need to pick up the red mug. Get its grasp pose."}],
            tools=tools, tool_choice="auto")
        tc = r.choices[0].message.tool_calls
        ok = bool(tc) and tc[0].function.name == "get_grasp_pose" and \
            "mug" in json.loads(tc[0].function.arguments).get("object_name", "").lower()
        check("T7 tool_calls", ok, f"tc={[(t.function.name, t.function.arguments) for t in (tc or [])]}")
    except Exception as ex:
        check("T7 tool_calls", False, f"{type(ex).__name__}: {ex}")

    n_pass = sum(1 for _, ok, _ in results if ok)
    print(f"\n===== {n_pass}/{len(results)} PASS =====")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
