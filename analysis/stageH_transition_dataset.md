# Stage H transition dataset(§7,只建不训)

_生成 by scripts/build_stageH_transition_dataset.py;记录数 252(h0 148 + h1 104);sha256 = 28d569fa68271a823f209f5b3f4f602a1c3bed45eaeb8adad032f1530069353b_

- h0 记录:历史 148 点 + H2 冻结标签(join stageH2_router_items;无干预注入,arm/injected_block/next_prim = null);
- h1 记录:H1 fire 级(重放触发 + 事件交叉核对同分析器;infra 缺失 0 集、事件不一致剔除 13 集);
- split:md5(task,seed)%100<40 → validation(与 H0 协议一致);
- **未做任何训练**(§7 冻结;H3 不自动开启)。

## 计数

| src | arm | n |
|---|---|---|
| h0 | — | 148 |
| h1 | h1C | 34 |
| h1 | h1G | 32 |
| h1 | h1P2 | 38 |

## h1 validated@5(fire 级)

| arm | validated | n |
|---|---|---|
| h1C | False | 23 |
| h1C | True | 11 |
| h1G | False | 16 |
| h1G | True | 16 |
| h1P2 | False | 17 |
| h1P2 | True | 21 |

## family 分布

| src | family | n |
|---|---|---|
| h0 | FALSE_GRASP | 113 |
| h0 | MOVE_CONTACT_STALL | 17 |
| h0 | RELEASE_PREDICATE_STALL | 18 |
| h1 | FALSE_GRASP | 80 |
| h1 | MOVE_CONTACT_STALL | 6 |
| h1 | RELEASE_PREDICATE_STALL | 18 |
