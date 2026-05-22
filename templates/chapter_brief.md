# {chapter} Brief

schema_version: 2

## 章节标题

TODO：给出非占位章节标题；候选正文最终也必须以 `# 标题` 开头。

## 章节简介

TODO：80-180 字，说明本章读者可感知的状态变化；不得把未发生剧情写成已发生事实。

## Story Card

- 第一屏扰动：TODO：300 字内出现异常、冲突、危险、反常信息或强人物动作。
- 主角本章想要：TODO：写成可行动、可失败、会付代价的目标。
- 主角主动动作：TODO：主角主动选择、拒绝、试探、冒险、交换、误导或承担代价。
- 最大阻力：TODO：人、规则、资源、关系、时间压力中至少一个。
- 中段变化点：TODO：计划外变化、反转、加压、误判暴露或局面变形。
- 本章小兑现：TODO：至少兑现一个信息、情绪、关系、行动结果或小答案。
- before -> after：TODO：读者能感知的状态变化，格式为 before -> after。
- 章末点击理由：TODO：一句话说明读者为什么必须看下一章。
- 本章只讲懂的一条世界规则：TODO：只写一条，并通过场景压力、选择、误用或普通人反应展示。
- 禁止临场破局：TODO：不得靠哪些未授权新道具、新能力或新规则解决本章核心问题。

## Machine Contract Appendix

- 上章章末锚点：TODO：首章写“开篇章，无上章”；非首章列出时间 / 地点 / 在场人物 / 主角状态 / 携带物 / 证据 / 未完成动作。
- 本章开场落点：TODO：列出时间 / 地点 / 在场人物 / 主角状态 / 第一动作。
- 场景承接说明：TODO：类型：原地承接 / 明示跳切 / 省略过桥 / 开篇起始；说明：若地点、时间或状态改变，写清过桥原因和动作。
- 主线牵引档位：TODO：S0-S4 开头，并说明本章如何保持主线牵引。
- 外部压力档位：TODO：W0-W4 开头，并说明外部世界、制度、势力、资源或关系如何影响本章行动。
- 本章继承变化：TODO：写本章承接上一章或开篇初始状态的具体变化；不能写 none。
- 本章节奏用途：TODO：推进 / 缓冲 / 兑现 / 铺垫 / 转场 / 蓄压 / 爆发，可选 1-2 个。
- 节奏说明：TODO：说明为什么本章不会空转，也不会为了过检强行加速。
- 本章进展契约：TODO：进展类型：setup / reveal / decision / thread_advance / payoff / digest / cost_payment / transition；有效推进类型：risk_escalation / relationship_change / information_reversal / cost_landed / choice_completed / power_shift / goal_advanced / false_hope_broken / payoff / digest；推进对象：thread_id / entity_id / 主线核心问题；起始状态依据：上章锚点 / open thread / 事件 id；结束状态变化：本章结束时不可忽略的变化；进展重要度：P0/P1/P2/P3；低牵引功能：低牵引时写消化、蓄压、关系转向、信息校准或转场功能。
- 本章代价与后果契约：TODO：推进重量：C0/C1/C2/C3/C4；后果等级：reversible / scar / structure_change；代价类型：physical / emotional / relationship / resource / reputation / time / rule_debt；已支付代价：本章谁付出什么；延后代价：后续追讨什么；后果承接义务：下一章或三章内必须承接什么；消化窗口：本章 / 下一章 / 2章内 / 3章内；冷却范围：哪条主线、伏笔或能力短期内不能继续猛解。
- 本章解决边界：TODO：新开伏笔：...；推进伏笔：...；解决伏笔：...；禁止解决：...；解决是否需要代价：是 / 否。
- reader_reward_intensity：TODO：R0 / R1 / R2 / R3 / R4，必须与 reader promise 手动策略一致。
- reader_reward_type：TODO：爽点 / 悬念 / 笑点 / 情绪 / 信息 / 关系 / 权力 / 审美 / 恐惧 / 治愈 / 代价，可多选。
- reader_reward_delivery：TODO：本章实际交付给读者的回报，必须能在正文中找到证据。
- reader_reward_timing：TODO：opening / midpoint / ending / full_chapter / next_chapter_setup。
- reward_evidence_requirement：TODO：正文中必须能匹配到的回报证据句；R2+ 不得写 none。
- pressure_level：TODO：H0/H1/H2/H3/H4，标明本章读者压力强度。
- release_valve：TODO：本章释放阀，小胜 / 真相兑现 / 关系推进 / 情绪缓冲 / 反制；高压章节不得写 none。
- protagonist_desire_or_principle：TODO：本章显露的欲望、私心、原则或底线，必须能指导主角主动动作。
- 低戏剧载体：TODO：none / waiting / archive / report / travel / research / daily_repeat / emotional_silence / explanation / meeting / training / procedure / dialogue / investigation。
- 低戏剧载体承载的推进类型：TODO：none / risk_escalation / relationship_change / information_reversal / cost_landed / choice_completed / power_shift / goal_advanced / false_hope_broken / payoff / digest。
- 核心机制是否出现：TODO：used / limited / backfired / upgraded / misled / intentionally_absent / silent。
- 若未出现，当前沉默计数：TODO：0 / 1 / 2 / 3...
- 等待结尾债务：TODO：none / waiting_ending / resolved_waiting / next_chapter_must_resolve。
- 可用人物状态：TODO：列出本章可用的人物状态；没有则写 context pack only。
- 可用道具 / 装备：TODO：本章能出现的道具或装备；没有则写 none。
- 可用道具 IDs：TODO：只列 `bible/objects.yaml` 中本章允许使用的 id；没有则写 none。
- 可用技能 / 能力：TODO：本章能出现的技能或能力；没有则写 none。
- 可用技能 IDs：TODO：只列 `bible/abilities.yaml` 中本章允许使用的 id；没有则写 none。
- 能力限制 / 代价：TODO：本章能力、资源、地位或规则使用的限制与代价；没有则说明为什么。
- 未解决伏笔：TODO：本章开始时仍未解决的伏笔；没有则写 none。
- 新增设定：TODO：新增设定必须先停留在 open_questions，不能直接进 canon；没有则写 none。
- 允许新增元素：TODO：按 L0/L1/L2/L3/L4 标明本章可新增内容；没有则写 none。
- 最低落账事件：TODO：character_decision / character_state_change / relationship_change / world_fact / rule_reveal / thread_opened / thread_advanced / thread_paid_off / location_change / object_change。
- 禁止新增：TODO：不得新增的 L2/L3/L4 设定、道具、能力或规则。
- 禁止解决：TODO：本章不能解决的主谜题、核心规则或长期伏笔。
- 主角弱点 / 误判：TODO：来自 initial_personality 的弱点、误判、上头点或默认策略。
- 普通人 / 外部视角对照：TODO：读者通过谁的反应理解规则压力。
- 旧问题：TODO：首章写 none，非首章写上一章遗留问题。
- 悬念状态：TODO：opened / advanced / partially_answered / paid_off / escalated。
