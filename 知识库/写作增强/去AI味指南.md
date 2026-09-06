# 去 AI 味写作指南（国赛中文论文）

> 用途：论文初稿完成后、交付前用。把空泛、模板化、生成稿式表达压回具体对象、数字、因果。
> 配套：第三轮自审见 `七轮自审框架.md`；最终 DOCX 按 `文档/论文写作.md` 交付自检入口扫描模板化表达。

---

## 一、润色边界（不碰的东西）

- 只改文字表达；不改格式、建模思路、图表编号、公式含义、真实结果
- 不编造“人味”：不补写未发生的讨论/试错/情绪；真实过程只来自运行/实验/代码变更记录
- 保留专有名词、模型名、指标名、变量名、单位、结果数字
- 不拔高用词；不大幅增字；删语义重复句
- 总分段落总论点是空话（如“具有重要意义”）→ 删总论点，直留分论点
- 标题层级、段落样式、图表位置、公式编号、题注格式不变

**高频关联词处理**：比如/虽然/但是/不仅/而且/同时/首先/然后/总之/其中 → 按语境替换/移位/删；首先/其次 → 其一/其二/紧接着/删；和 → 并且/以及/与；这说明 → 研究说明/具体对象作主语；正文“了”清理（文件名/引用/题注/术语保留）；体系/架构/机制 → 流程/结构/关系/原理/约束/过程；短句合并用因而/使得/导致/所以；同段避免单一句式，交替把字句/被字句/判断句。

---

## 二、定位痕迹 → 决定动作

先找句子，再决定删/改/补证据/弱化结论；整段重写须有明确理由。

| 痕迹 | 典型写法 | 处理 |
|---|---|---|
| 空泛拔高 | 标志着、重要作用、具有重要意义、奠定坚实基础 | 删空话，改数字/对比/具体贡献 |
| 宣传修辞 | 突破性、令人震撼、完美、极致、表现出色 | 删形容词，让指标说话 |
| 模糊归因 | 专家认为、研究表明、据报道、众所周知 | 有文献标注来源，无来源删 |
| 机械连接 | 首先/其次/最后/综上所述/值得注意的是 | 按内容关系直接衔接 |
| 平行套句 | 不仅……而且、原因有三、三个方面 | 有几个写几个，不凑整齐 |
| 结果空话 | 展示了/反映了/说明了 + 空泛判断 | 改对象、数字/趋势、原因 |
| 概念漂移 | 模型/算法/方法/方案反复切换 | 同一概念固定一名 |
| 万能局限 | 数据有限、场景复杂、未来进一步研究 | 写清限制来自哪个假设/数据/计算边界 |

**核心原则**：每句至少落到其一——具体数字、可比对象、因果解释；三者全无的句子可删或重写。

---

## 三、改写五法

| 手法 | 要点 | 示例 |
|---|---|---|
| **主语具体化** | 少用“本文/我们/该模型”开头；结果解释主语用图/表/误差分布/最优方案/灵敏度曲线/参数取值/约束条件 | 原：结果表明模型鲁棒性好 → 改：参数扰动±20%时，目标函数波动<2.1%，最优变量未变 |
| **判断落证据** | 较好/良好/优越/有效/可行不可单独出现；保留时后接数字/对比/约束检查 | 原：模型发挥重要作用 → 改：召回率78.3%→92.1%，误报率降4.2pp |
| **方法果并置** | 每小问按：模型/算法 → 求解证据 → 结果解释 → 边界检查 | 原：建立模型求解，结果可行 → 改：单架单弹三维运动学+遮蔽模型经时间扫描得最优遮蔽1.396s，与解析解1.401s相对误差0.36% |
| **局限落假设** | 不写通用套话；写：哪个假设限制、影响哪结果、后续怎么改 | 原：模型有不足，未来改进 → 改：价格视为固定值；±15%波动时最优面积排序可能变，后续设为随机变量用鲁棒优化重解 |
| **保留不顺滑** | 技术语气克制，留真实判断：为什么选模型/哪结果意外/哪假设最影响结论/哪结果仅本题成立；无真实材料不强行加“我们尝试了/讨论后决定”，改用可核查的适配理由/参数依据/对照结果/适用边界 |

---

## 四、数模常用替换速查

| 原句 | 改写方向 |
|---|---|
| 模型表现良好 | 写指标：测试集 RMSE=0.23 或相对基线提升 |
| 实验证明模型有效 | 写检查：残差分布/误差上限/约束满足率/交叉验证 |
| 深入探讨模型机理 | 写推导对象：热传导边界/力矩平衡/状态转移 |
| 充分展示算法优势 | 写哪表、哪指标、相对哪基线占优 |
| 取得满意收敛效果 | 写迭代次数、目标函数变化阈值、停止条件 |
| 具有一定实用性 | 写迁移场景及迁移前必重估参数 |

**典例**：
- 原：通过灵敏度分析展示参数影响，反映稳健性 → 改：e±20%扰动目标函数波动<2.1%；h0同幅扰动波动8.7%，说明对e不敏感、对h0敏感
- 原：模型有优点也有不足，未来改进 → 改：优点：四问共用刚体动力学/碰撞/协同控制方程，解析小角度与全六自由度互验。局限：忽略绳弹性；刚度<10³N/m时残差>5%，后续加阻尼项修正

---

## 五、5 类 AI 痕迹机器清洗

| 类别 | 典型写法 | 清洗动作 |
|---|---|---|
| **1. 破折号泛滥** | 全文大量 — (U+2014) | **全文清零**：按语境换句号/逗号/冒号/分号；转折用然而/但，解释用即/即：；严禁保留 em/en dash |
| **2. 规则三机械排比** | 三个侧面/维度/方面/阶段/原则/步骤/证据链；从A/B/C三个方面；第一/二/三机械排比 | **打破整齐**：实有几条写几条；删“三个/四个”定语；从A/B/C→先看A再看B最后看C；删序数词改自然衔接 |
| **3. 回避式动词** | 发挥…作用/提供…依据/作为…支撑/为…提供保障/构建了…框架/对…起到…作用/是…关键 | **改主语+动作+结果**：“补贴方案发挥作用”→“补贴方案使响应率62.3%→81.7%”；“模型提供依据”→“模型输出靶向集合直接决定各网格补贴强度” |
| **4. 过度强调/总结口号** | 这一结果直接说明/正是…本质/货币化体现/深刻揭示/充分证明/核心在于/关键在于/值得深入思考/不得不提 | **删空升华**：直接删上述词；只留“观察到/发现/计算得出 + 具体数字/现象” |
| **5. 整齐对仗句** | 不是A而是B/非A而是B；既A又B/既非A也非B | **打破对称**：“不是A而是B”→“主要表现为B/核心差异在于B/本质属B”；“既A又B”拆两句或改“兼具A与B” |

---

## 六、机器扫描入口（交付前必跑）

```python
# AI 味模式扫描（命中即拒绝保存，已并入 validate_paper_structure 致命错误）
from tools.docx.core.paper_format import scan_ai_taste_patterns
hits = scan_ai_taste_patterns(doc)
for label, snippet in hits:
    print(f'[{label}] {snippet[:60]}')

# 禁用词扫描（命中即拒绝保存，已并入 validate_paper_structure 致命错误）
from tools.docx.core.paper_format import scan_forbidden_words
hits = scan_forbidden_words(doc)
for matched, snippet in hits:
    print(matched, '->', snippet[:40])
```

**禁用词表**（含但不限于）：
- 工具暴露：AI、人工智能、大模型、GPT、智能体、WorkBuddy、skill
- 生成痕迹：机器生成、自动生成的、合并、融合两套、两套解、两份解
- 参考痕迹：底版、另一份、参考解、标准解、对着标准、对着参考、取舍

> 肉眼漏表格单元格/题注/附录痕迹。交付前必全文机扫，命中先改 0 再存。统一命令见 `文档/论文写作.md`。

---

## 七、终稿自检清单

- [ ] 每核心结论有结果文件/图表/公式推导/运行日志支撑
- [ ] 每结果句含数字/对比/因果解释至少一项
- [ ] 好/良好/优越/有效/可行后接可核查证据
- [ ] 清理机械连接词、强行三段式
- [ ] 不用“套话计数”判质量，检查连接词是否承载真实逻辑
- [ ] 同一概念全文一名
- [ ] 局限落到本题具体假设/数据/计算边界
- [ ] 润色未改格式/图片/表格编号/公式含义/真实结果
- [ ] `scan_forbidden_words` 0 命中
- [ ] 交付自检入口无未处理模板化表达

**过审标准**：删形容词后，剩的名词/动词/数字仍能说明——做过什么、算出什么、结论何条件下成立。

---

## 附录：humanizer 通用去 AI 味模式库（英文/通用文本）

> 融合说明：原《humanizer.md》已并入本文件（MIT，v2.11.2，基于 Wikipedia "Signs of AI writing"；已压缩——每类模式保留词表与单示例）。
> 分工：**中文数模论文以本指南正文为准**；写英文摘要、国际会议文本、评审文件或 README 时，
> 逐条对照下述 35 类模式。改写铁律一致：只改写法，不改事实、不增删数字与结论。

# Humanizer: remove AI writing patterns

Rewrite AI-sounding text so it reads like the writer, not a chatbot. Do not change what it says or make up details.

The patterns below come from Wikipedia's ["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup.

## What to do

When given text to humanize:

1. **Find AI patterns.** Check the text against the patterns below.
2. **Keep every claim.** You may shorten dull parts, expand useful parts, and merge or split paragraphs. Keep the information even when you change the structure.
3. **Do not invent facts.** Do not add a fact, name, number, date, quote, or citation unless it comes from the source or the user. If a sentence needs a missing detail, ask for it or use a simpler sentence. You may add an opinion or reaction when the writer's voice calls for one, but you may not add a factual claim. Fiction is exempt because invented details are part of the task.
4. **Match the voice.** Use the right tone for the text, such as formal, casual, or technical. Add personality only when the text and the writer call for it.

The input type controls what you return. See [How to return the result](#how-to-return-the-result). Use the same rewrite process in every mode.

## Match the writer's voice

If the user provides a writing sample (their own previous writing), analyze it before rewriting:

1. Read the sample first. Note its sentence length, word choice, paragraph openings, punctuation, repeated phrases, and transitions.
2. Match those habits. Do not replace casual words with formal ones or remove deliberate quirks.
3. If there is no sample, use the guidance below.

A writing sample takes priority over these style rules. If the sample uses em dashes, keep them at about the same rate. Do not apply §14 as a ban.

## Add personality only when it fits

Removing AI patterns is only half the job. The result should still sound like a person.

Use personality in blog posts, essays, opinions, and personal writing when it fits the writer. Keep reference, technical, legal, and factual text neutral. Do not add opinions or first-person language where they do not belong.

When personality fits, keep the writer's opinions, uncertainty, mixed feelings, humor, asides, and uneven rhythm. Never invent facts to make the text feel personal.

## Content patterns

### 1. Inflated claims about importance and legacy

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted
**Before:**
> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.
**After:**
> The Statistical Institute of Catalonia was established in 1989, part of a wider decentralization of administrative functions in Spain.

### 2. Name-dropping to prove importance

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence
**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.
**After:**
> Her views have been cited in The New York Times and the BBC.

### 3. Shallow analysis with -ing phrases

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...
**Before:**
> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.
**After:**
> The temple is painted blue, green, and gold, colors meant to evoke Texas bluebonnets and the Gulf of Mexico.

### 4. Sales language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning
**Before:**
> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.
**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia.

### 5. Vague sources

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)
**Before:**
> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.
**After:**
> Researchers and conservationists study the Haolai River for its unusual characteristics.

### 6. Formulaic challenges and outlook sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook
**Before:**
> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.
**After:**
> Korattur has recurring traffic congestion and water shortages.

## Language and grammar patterns

### 7. Overused AI words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, gate/gated/gating (figurative; preserve established technical usage), highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, quietly, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant
**Before:**
> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.
**After:**
> Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.

### 8. Avoiding is and are

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]
**Before:**
> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.
**After:**
> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.

### 9. Not X but Y and clipped negative endings
It also adds clipped endings such as "no guessing" instead of writing a clear clause.
**Before:**
> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.
**After:**
> The heavy beat adds to the aggressive tone.
**Before (tailing negation):**
> The options come from the selected item, no guessing.
**After:**
> The options come from the selected item without forcing the user to guess.

### 10. Forced groups of three
**Before:**
> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.
**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.

### 11. Changing names and repeating sentence openings
Use one clear name for the same subject. For repeated openings, merge sentences, change the subject when that helps, or begin with the action.
**Before (synonym cycling):**
> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.
**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.
**Before (repeated openings):**
> She noted the door. She noted the lock on it. She filed both away.
**After:**
> She noted the door and its lock, then filed both away.

### 12. False from X to Y ranges
**Before:**
> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.
**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.

### 13. Passive voice and missing subjects
**Before:**
> No configuration file needed. The results are preserved automatically.
**After:**
> You do not need a configuration file. The system preserves the results automatically.

## Style patterns

### 14. Em and en dashes

**Rule:** The final rewrite must not contain em dashes (—) or en dashes (–), unless the writer's sample uses them. Replace a dash with a period, comma, colon, or parentheses, or rewrite the sentence. Also check for spaced dashes (` — `) and double hyphens (` -- `) used as dashes.
**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.
**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.
### 15. Too much bold text
**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.
**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.

### 16. Lists with bold mini-headings
**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.
**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

### 17. Title case in headings
**Before:**
> ## Strategic Negotiations And Global Partnerships
**After:**
> ## Strategic negotiations and global partnerships

### 18. Emojis
**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting
**After:**
> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.

### 19. Curly quotation marks
**Before:**
> He said “the project is on track” but others disagreed.
**After:**
> He said "the project is on track" but others disagreed.

## Chatbot patterns

### 20. Chatbot text left in the answer

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., Want me to...?, Want me to give examples?, Should I continue?, let me know, here is a...
**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.
**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

### 21. Knowledge-limit disclaimers and guesses

**Words to watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information, not publicly available, maintains a low profile, keeps personal details private, prefers to stay out of the spotlight, likely [grew up/studied/began], it is believed that
**Before (cutoff disclaimer):**
> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.
**After:**
> The company's founding date is not documented in the available sources. (Or cut the sentence. State a date only if a source provides one.)
**Before (speculative gap-fill):**
> Information about her early life is not publicly available, suggesting she maintains a low profile and keeps personal details private. She likely grew up in a middle-class household, which shaped her later interest in education reform.
**After:**
> Her early life is not documented in the available sources. (Or omit the section.)

### 22. Overly agreeable tone
**Before:**
> Great question! You're absolutely right that this is a complex topic. That's an excellent point about the economic factors.
**After:**
> The economic factors you mentioned are relevant here.

## Filler and hedging

### 23. Filler phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"

### 24. Too many qualifiers

**Phrases to watch:** to be fair, it's also possible, could potentially, might arguably, in some cases it may, this is an inference
**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.
**After:**
> The policy may affect outcomes.

### 25. Generic positive endings
**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.
**After:**
> (Cut the paragraph. End on the last concrete fact instead of a send-off. If the source states real plans, use those.)

### 26. Too many hyphenated word pairs

**Words to watch:** third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end
**Before:**
> The cross-functional team delivered a high-quality, data-driven report. The team is cross-functional, the report is high-quality, and the methodology is data-driven.
**After:**
> The cross-functional team delivered a high-quality, data-driven report. The team is cross functional, the report is high quality, and the methodology is data driven.

### 27. Pretending to reveal a deeper truth

**Phrases to watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter
**Before:**
> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.
**After:**
> The question is whether teams can adapt. That mostly depends on whether the organization is ready to change its habits.

### 28. Announcing the next point

**Phrases to watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado, heads up, quick note, before I forget
**Before:**
> Let's dive into how caching works in Next.js. Here's what you need to know.
**After:**
> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.
**Before (casual register):**
> One thing that bit me hard, so pay attention to this part: the webpack dev server doesn't send the CORS header by default.
**After:**
> The webpack dev server doesn't send the CORS header by default.

### 29. A heading repeated in the first sentence

**Signs to watch:** A heading followed by a one-line paragraph that simply restates the heading before the real content begins.
**Before:**
> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.
**After:**
> ## Performance
>
> When users hit a slow page, they leave.

### 30. Writing about the previous version
**Before:**
> This function was added to replace the previous approach of iterating through all items, which caused O(n²) performance.
**After:**
> This function uses a hash map for O(1) lookups, avoiding the O(n²) cost of naive iteration.

### 31. Forced punchlines and dramatic fragments
**Before:**
> Then AlphaEvolve arrived. It had no preference for symmetry. No aesthetic prior. No nostalgia for human taste. The old rules were gone.
**After:**
> AlphaEvolve changed the search because it did not favor symmetry or human-looking designs. That made some of the older assumptions less useful.

### 32. Formulaic sayings

**Words to watch:** X is the Y of Z, X becomes a trap, X is not a tool but a mirror, the language of, the currency of, the architecture of
**Before:**
> Symmetry is the language of trust. Efficiency becomes a trap when teams forget the human layer.
**After:**
> Symmetric layouts often feel more predictable to users. Teams can over-optimize workflows and miss how people actually use them.

### 33. Fake-candid openings

**Phrases to watch:** Honestly?, Look, Here's the thing, The thing is, Let's be honest, Real talk, when used as standalone hooks or fake-candid pauses before an ordinary point.
**Before:**
> Is it worth the price? Honestly? It depends on how often you'll use it.
**After:**
> Whether it's worth the price depends on how often you'll use it.

### 34. Answering objections no one raised

**Phrases to watch:** This isn't (mainly/really) about, I'm not saying/arguing/trying to, To be clear, Don't get me wrong, This is not to say, You could argue/frame this differently but, Some might say... but
**Before:**
> This isn't mainly about prompt length, and I'm not arguing that documentation doesn't matter. You could categorize the problem another way, but the issue is whether the agent can use the instruction when it acts.
**After:**
> The issue is whether the agent can use the instruction when it acts.

### 35. Rejecting fake alternatives

**Phrases to watch:** A tempting option/approach would be, One might be tempted to, An obvious approach would be, You might think... but, It would be easy to just, Some would suggest
**Before:**
> Session tokens are rotated every 24 hours. A tempting approach would be to rotate them by restarting the auth service on a cron job, but that would drop every active session. Rotation happens in place, and clients refresh transparently.
**After:**
> Session tokens are rotated every 24 hours, in place, and clients refresh transparently.

## Check for false positives

### What not to flag

以下各项单独出现不构成 AI 证据：

- 规范语法与统一风格 / 随意与正式混用 / 干瘪文字 / 正式学术词 / 书信式开头结尾 / 孤立过渡词 / 单独弯引号 / 单独 em dash / 单个强调短句 / 有意重复开头 / 句中 honestly·look / 有用的范围声明与免责 / 设计文档中的真实备选 / 无出处陈述 / 复杂正确排版 / 引文内的被讨论词句——均非 AI 证据
- 判定看**多个模式同时出现**；单个 em dash 证明不了什么

### Human details to keep

保留以下作者人味细节：

- 具体、不寻常的细节；混合情绪与未解张力；带年代烙印的引用（俚语/梗）；有意的第一人称取舍；长短句交替；真实的插入语与自我修正；2022-11-30（ChatGPT 发布）前的编辑

---

## How to return the result

返回：只给最终改写文本（文件模式只回写正文，代码块/元数据/链接不动）。

## Rewrite process

1. 标记每个 AI 模式 → 2. 写草稿并读出声查节奏 → 3. 自问两题（还有哪里像 AI？是否增删了任何事实/数字/引用/声明？）→ 4. 整段自然重写，不逐词打补丁；执行 §14 dash 规则。

## Source

基于 [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)（WikiProject AI Cleanup 维护）。
