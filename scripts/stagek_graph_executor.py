#!/usr/bin/env python
"""Stage K 图边执行器 + 物理结局 verifier(K0 标定 / K1 数据集共用)。

语义全部来自冻结件,本模块零新增自由度:
- 边 / 绑定 / executor 链:resources/libero/executable_graph_v1.yaml(7e7528e);
- 结局公式:stageJ_graph_spec.md §5(实现口径见 stageK0_prereg.md §4);
- 链式语义:感知无果 → 链中止记 NO_EFFECT;其余原语异常 → ERROR;
  move_to 未显式给 gripper → 默认开爪(-1.0)冻结照跑。

纪律:GT 物体位姿只进本模块的 verifier/analysis 输出,不进任何
runtime/planner 可见文本(graph spec §5.4 红线)。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GRAPH_PATH = REPO / "resources/libero/executable_graph_v1.yaml"

# FG-3 偏移后缀(graph v1 冻结常量)
OFFSET_SUFFIX = (
    " — grasp at a slightly offset point, about two centimeters "
    "to the side of the previous attempt"
)

# 结局类(§5)
VERIFIED, NO_EFFECT, HARM, ERROR = (
    "VERIFIED_RECOVERY", "NO_EFFECT", "HARM", "ERROR")

# 进入记录的原语 result 子集(轻量;完整 result 在 states.json)
_RESULT_FIELDS = {
    "success", "peak_lift_m", "final_dist_m", "final_gripper_opening",
    "min_gripper_opening", "chunks_used", "steps_used", "name",
    "target_xyz", "final_eef_pos", "found", "score", "center_xyz",
    "libero_terminated", "row_range", "col_range", "n_valid", "gripper",
}

# §5 阈值(冻结)
LIFT_M = 0.01          # FG 物体抬升 / 跟随判据
PICK_LIFT_M = 0.005    # pick 物证抬升
GRIP_HELD = 0.06       # 握持开度阈值
RESID_DROP_M = 0.005   # MCS 残差下降
HARM_DROP_M = -0.02    # 脱手坠落
HARM_XY_M = 0.05       # 扫飞/撞离水平位移
EEF_RISE_M = 0.01      # 抬升证据(Δeef_z)


# ---------------------------------------------------------------------------
# 图加载与绑定解析
# ---------------------------------------------------------------------------

def load_edges(path: Path = GRAPH_PATH) -> dict[str, dict]:
    """yaml → {edge_id: edge}(冻结件只读)。"""
    import yaml
    data = yaml.safe_load(Path(path).read_text())
    return {e["id"]: e for e in data["edges"]}


def _eval_expr(expr: str, names: dict) -> list:
    """在 {eef, obj} 名空间安全求值 waypoint 表达式(ast 白名单)。"""
    tree = ast.parse(expr.strip(), mode="eval")

    def _n(node):
        if isinstance(node, ast.Expression):
            return _n(node.body)
        if isinstance(node, ast.List):
            return [_n(x) for x in node.elts]
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ValueError(f"表达式引用未绑定名 {node.id}")
            return names[node.id]
        if isinstance(node, ast.Attribute):  # eef.x / obj.z
            base = _n(node.value)
            if node.attr in ("x", "y", "z"):
                return base["xyz".index(node.attr)]
            raise ValueError(f"不支持的属性 .{node.attr}")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = _n(node.left), _n(node.right)
            return a + b if isinstance(node.op, ast.Add) else \
                a - b if isinstance(node.op, ast.Sub) else \
                a * b if isinstance(node.op, ast.Mult) else a / b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("max", "min"):
            args = [_n(x) for x in node.args]
            return max(args) if node.func.id == "max" else min(args)
        raise ValueError(f"不支持的表达式节点 {type(node).__name__}")

    return _n(tree)


class EdgeExecutor:
    """在给定 runtime 上下文里解析并执行一条图边,给出 §5 结局分类。

    ctx(快照时刻冻结,rollout 间不变):
        task_lang      任务语言
        last_pick      prefix 内最后一条 pi0_pick/pi0_doubled 的 prompt
    EEF / OBJ_XYZ 分别取快照测量与链内感知步输出,不外部注入。
    """

    def __init__(self, toolkit, env, prims, outdir: Path):
        self.toolkit = toolkit
        self.env = env
        self.prims = prims
        self.outdir = Path(outdir)

    # ---- 测量(J0 冻结通道) --------------------------------------------

    def measure(self) -> dict:
        m = self.env.sim_measurement()
        o = m.get("obs") or {}
        names = [k[:-4] for k in o
                 if k.endswith("_pos") and "_to_robot0_eef" not in k
                 and not k.startswith("robot0")]
        q = [float(x) for x in o.get("robot0_gripper_qpos", [])]
        return {
            "eef": [float(x) for x in o.get("robot0_eef_pos", [])],
            "grip": abs(q[0]) + abs(q[1]) if len(q) >= 2 else None,
            "objs": {n: [float(x) for x in o[f"{n}_pos"]] for n in names},
            "ooi": (m.get("obj_of_interest") or [None])[0]
                  if isinstance(m.get("obj_of_interest"), list)
                  else m.get("obj_of_interest"),
            "ok": bool(self.env.check_success()),
        }

    def _tail_result(self) -> dict:
        sj = json.load(open(self.outdir / "states.json"))
        return (sj[-1] or {}).get("result") or {}

    # ---- 绑定解析 --------------------------------------------------------

    def _resolve_binding(self, raw, ctx, names):
        """parameterizer binding 原文 → 值(惰性:表达式引用 obj 时延迟到用时)。"""
        if raw == "TASK_LANG":
            return ctx["task_lang"]
        if raw == "LAST_PICK_PROMPT":
            return ctx["last_pick"]
        if raw == "LAST_PICK_PROMPT + OFFSET_SUFFIX":
            return (ctx["last_pick"] or ctx["task_lang"]) + OFFSET_SUFFIX
        if raw == "LAST_PICK_PROMPT(无则 TASK_LANG)":
            return ctx["last_pick"] or ctx["task_lang"]
        if raw == "EEF":
            return list(names["eef"])
        if raw == "OBJ_XYZ":
            return names.get("obj")  # 链内感知步后有效
        if isinstance(raw, str) and raw.strip().startswith("["):
            return _eval_expr(raw, names)
        return raw

    def _resolve_arg(self, v, bindings, ctx, names):
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            name = v[2:-1]
            if name in bindings:
                raw = bindings[name]
            elif name == "TASK_LANG":
                return ctx["task_lang"]
            else:
                raise ValueError(f"未绑定参数 ${{{name}}}")
            return self._resolve_binding(raw, ctx, names)
        return v

    # ---- 边执行 ----------------------------------------------------------

    def exec_edge(self, edge: dict, ctx: dict) -> dict:
        """执行一条边(假定环境已 restore 到 snapshot 并 set_obs)。"""
        t0 = __import__("time").time()
        base = self.measure()
        names = {"eef": base["eef"], "obj": None}
        raw_bindings = dict(edge["parameterizer"]["bindings"])
        chain, samples = [], [("base", base)]
        outcome = None
        perception_found = None

        for step_spec in edge["executor"]:
            tool = step_spec["tool"]
            args = {}
            for k, v in step_spec["args"].items():
                args[k] = self._resolve_arg(v, raw_bindings, ctx, names)
            err = None
            try:
                self.toolkit._step(tool, **args)
                result = self._tail_result()
            except Exception as exc:  # 原语/服务异常 → ERROR
                result, err = {}, f"{type(exc).__name__}: {exc}"[:300]
            entry = {"tool": tool,
                     "result": {k: v for k, v in result.items()
                                if k in _RESULT_FIELDS},
                     "error": err or result.get("error")}
            chain.append(entry)

            if tool == "segment":
                perception_found = bool(result.get("found"))
                if entry["error"] or not perception_found:
                    outcome = NO_EFFECT  # 感知无果 → 链中止(§2 冻结语义)
                    break
                box = result.get("box") or [0, 0, 0, 0]
                names["mask_rows"] = [int(box[1]), int(box[3])]
                names["mask_cols"] = [int(box[0]), int(box[2])]
            if tool == "back_project":
                if entry["error"]:
                    outcome = NO_EFFECT
                    break
                names["obj"] = list(result["center_xyz"]) \
                    if result.get("center_xyz") is not None else None
                if names["obj"] is None:
                    outcome = NO_EFFECT
                    break
            if entry["error"] and outcome is None:
                outcome = ERROR
                break
            samples.append((tool, self.measure()))

        # 判定窗口:4 × 5 步保持(§2);ERROR 支不跑,NO_EFFECT 支照跑
        if outcome != ERROR:
            for w in range(4):
                try:
                    self.toolkit._step("set_gripper", gripper=0.0, steps=5)
                    m = self.measure()
                except Exception as exc:
                    outcome, m = ERROR, None
                    chain.append({"tool": f"window{w}",
                                  "result": {}, "error": str(exc)[:200]})
                    break
                samples.append((f"win{w}", m))
                if m["ok"]:
                    break

        if outcome is None:
            outcome, verify = self._classify(edge, base, samples, chain)
        else:
            verify = self._verify_stats(base, samples, chain)
        return {
            "edge_id": edge["id"], "family": edge["failure_family"],
            "outcome": outcome, "perception_found": perception_found,
            "chain": chain,
            "samples": [(t, {"eef": m["eef"], "grip": m["grip"],
                             "objs": m["objs"], "ok": m["ok"]})
                        for t, m in samples if m],
            "verify": verify,
            "elapsed_s": round(__import__("time").time() - t0, 1),
        }

    # ---- §5 结局分类 -----------------------------------------------------

    def _verify_stats(self, base, samples, chain) -> dict:
        ms = [m for _, m in samples if m]
        last = ms[-1]

        def _dz(name):
            if name in base["objs"] and name in last["objs"]:
                return last["objs"][name][2] - base["objs"][name][2]
            return None

        def _dxy(name):
            if name in base["objs"] and name in last["objs"]:
                b, l = base["objs"][name], last["objs"][name]
                return float(np.hypot(l[0] - b[0], l[1] - b[1]))
            return None

        ooi = base["ooi"]
        pick = next((c["result"] for c in chain
                     if "peak_lift_m" in (c["result"] or {})), {})
        dz_series, eefz_series = [], []
        for m in ms:
            if ooi and ooi in m["objs"]:
                dz_series.append(m["objs"][ooi][2] - base["objs"][ooi][2])
            eefz_series.append(m["eef"][2] - base["eef"][2])
        resid0 = residT = None
        if ooi and ooi in base["objs"] and ooi in last["objs"]:
            resid0 = float(np.linalg.norm(
                np.array(base["eef"]) - np.array(base["objs"][ooi])))
            residT = float(np.linalg.norm(
                np.array(last["eef"]) - np.array(last["objs"][ooi])))
        corr = None
        if len(dz_series) >= 3 and np.std(dz_series) > 1e-9 \
                and np.std(eefz_series) > 1e-9:
            corr = float(np.corrcoef(dz_series, eefz_series)[0, 1])
        min_grip = min((m["grip"] for m in ms if m["grip"] is not None),
                       default=None)
        return {
            "ooi": ooi,
            "d_ooi_z": _dz(ooi) if ooi else None,
            "max_d_ooi_z": max(dz_series) if dz_series else None,
            "max_obj_xy": max((v for v in (_dxy(n) for n in base["objs"])
                               if v is not None), default=None),
            "max_d_eef_z": max(eefz_series) if eefz_series else None,
            "dz_series_len": len(dz_series),
            "corr_dz_eefz": corr,
            "resid_0": resid0, "resid_T": residT,
            "min_grip": min_grip,
            "peak_lift_m": pick.get("peak_lift_m"),
            "final_grip_pick": pick.get("final_gripper_opening"),
            "check_success_ever": any(m["ok"] for m in ms),
        }

    def _classify(self, edge, base, samples, chain) -> tuple[str, dict]:
        v = self._verify_stats(base, samples, chain)
        fam = edge["failure_family"]
        ooi = v["ooi"]

        verified = False
        if fam == "FALSE_GRASP":
            follows = (v["corr_dz_eefz"] is not None and v["corr_dz_eefz"] > 0
                       and (v["max_d_ooi_z"] is not None
                            and v["max_d_ooi_z"] >= LIFT_M))
            pick_ok = (v["peak_lift_m"] is not None
                       and v["peak_lift_m"] >= PICK_LIFT_M
                       and v["final_grip_pick"] is not None
                       and v["final_grip_pick"] <= GRIP_HELD)
            verified = ((v["d_ooi_z"] is not None and v["d_ooi_z"] >= LIFT_M
                         and follows) or pick_ok)
        elif fam == "RELEASE_PREDICATE_STALL":
            verified = v["check_success_ever"]
        else:  # MOVE_CONTACT_STALL
            verified = (v["resid_0"] is not None and v["resid_T"] is not None
                        and v["resid_0"] - v["resid_T"] >= RESID_DROP_M) \
                or v["check_success_ever"]

        harmful = False
        if not verified:
            lift_evidence = (v["max_d_eef_z"] is not None
                             and v["max_d_eef_z"] >= EEF_RISE_M) or \
                (v["peak_lift_m"] is not None
                 and v["peak_lift_m"] >= PICK_LIFT_M)
            held = (v["min_grip"] is not None and v["min_grip"] <= GRIP_HELD
                    and lift_evidence)
            dropped = v["d_ooi_z"] is not None and v["d_ooi_z"] <= HARM_DROP_M
            swept = v["max_obj_xy"] is not None and v["max_obj_xy"] >= HARM_XY_M
            harmful = (held and dropped) or swept

        outcome = VERIFIED if verified else HARM if harmful else NO_EFFECT
        v["verified"] = verified
        v["harmful"] = harmful
        return outcome, v
