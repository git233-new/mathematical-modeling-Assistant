"""竞赛画像与交付门禁阈值（单一事实来源）。

此前这些常量/Profile 定义在 ``paper_format.py``，被 ``structure_validation.py``
大批量导入，而 ``paper_format`` 又在文件尾部反向重导出 validation 符号，形成
循环导入（只有 paper_format 先被导入时才能加载）。拆出本模块后，两个核心模块
都只依赖本模块，任一顺序均可直接导入，消除了环形依赖。

阈值口径与 ``文档/论文写作.md`` 及 ``tools/project_ops/project_audit.py`` 的
``GATE_EXPECTED`` 保持一致（提交前门禁会交叉校验）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContestProfile:
    name: str
    paper: str
    margins: tuple[float, float, float, float]
    required_markers: tuple[str, ...]
    rules_source: str
    max_body_pages: int | None = None
    min_body_pages: int | None = None


CONTEST_PROFILES = {
    'cumcm': ContestProfile(
        name='全国大学生数学建模竞赛',
        paper='A4',
        margins=(2.54, 2.54, 3.18, 3.18),
        required_markers=('摘 要', '关键词：'),
        rules_source='http://www.mcm.edu.cn/',
        max_body_pages=30,
        min_body_pages=20,
    ),
}


def get_profile(contest='cumcm'):
    # 单一通用竞赛画像：所有数模赛事共用同一套交付门禁，不按赛事名分支；
    # 未知赛事名直接回退到默认画像，不拒绝。
    return CONTEST_PROFILES.get(contest.lower(), CONTEST_PROFILES['cumcm'])


# ---------------------------------------------------------------------------
# 交付门禁阈值（CUMCM 2026 口径）
# ---------------------------------------------------------------------------
CUMCM_MIN_BODY_UNITS = 11111
# 总页数 / 等效总页数（不依赖 Word/LibreOffice 渲染的硬下限，正文+附录合计）
CUMCM_MIN_TOTAL_PAGES = 30
CUMCM_MAX_TOTAL_PAGES = 45
# 等效总页数下限（独立于字数闸门的兜底篇幅检查：捕获字数达标但大量空白/空段的文档）
CUMCM_MIN_ESTIMATED_PAGES = 20
# 等效页数换算系数（粗略校准：每 ~407 字/词 ≈ 1 页，用于 estimate_equivalent_pages）
CUMCM_UNITS_PER_PAGE = 407
CUMCM_MIN_FIGURES = 12
CUMCM_MIN_TABLES = 10
CUMCM_MIN_EQUATIONS = 15
CUMCM_MAX_EQUATIONS = 25
CUMCM_MIN_REFERENCES = 8
CUMCM_MAX_REFERENCES = 12
CUMCM_MIN_FLOWCHARTS = 1
CUMCM_MAX_FLOWCHARTS = 2
CUMCM_KEYWORD_MIN = 4
CUMCM_KEYWORD_MAX = 6
# 参考文献年份下限：只收录该年份及之后的文献（无年份条目不拦截）
REFERENCE_MIN_YEAR = 2016
_FLOWCHART_TERMS = ('流程图', '技术路线', '研究思路', '解题思路')
_FLOWCHART_OVERALL_TERMS = ('总体', '研究思路', '技术路线')


# ---------------------------------------------------------------------------
# 章节字数/页数预算表（单一事实来源）
# ---------------------------------------------------------------------------
# 同时喂给两个消费者：
# - ``paper_workflow.CONTENT_BUDGET``：预检 metrics 返回的展示表（键 = label，
#   {'characters': chars, 'pages': pages}），顺序即论文写作.md §1.2 预算表顺序；
# - ``structure_validation._SECTION_BUDGETS``：W11 章节双向约束（按 pattern 定位章节，
#   lo/hi ±20% 容差预警），note 为题注/消息里用的章名。
# 展示文本与 文档/论文写作.md §1.2 逐行镜像；机器判法一律以本表为准，md 只给人看，
# 差异由 tests/test_sync_contracts 与 project_audit 的文档镜像检查兜底。


@dataclass(frozen=True)
class SectionBudget:
    label: str                   # 预算表展示名（计划/预检视角，如 模型建立（5.x））
    chars: str                   # 展示字符区间文本，如 '5000-6000'
    pages: str                   # 展示页数文本，如 '8-10'
    lo: int | None = None        # 校验下界（None = 不设机器下界）
    hi: int | None = None        # 校验上界（None = 不设机器上界）
    pattern: str | None = None   # 章节标题定位正则（W11 用；None = 无独立章节机器校验）
    note: str = ''               # 校验消息里的章名（缺省回退到 label）


SECTION_BUDGET_ROWS = (
    SectionBudget('摘要（含关键词）', '800-900', '1'),
    SectionBudget('问题重述', '800-1000', '1-1.5', 800, 1000,
                  r'^一、\s*问题重述', '问题重述'),
    SectionBudget('问题分析', '1000-1200', '1.5', 1000, 1200,
                  r'^二、\s*问题分析', '问题分析'),
    SectionBudget('模型假设', '300-600', '0.5 以内', 300, 600,
                  r'^三、\s*模型假设', '模型假设'),
    SectionBudget('符号说明', '表格为主，不按正文凑字', '0.3-0.5'),
    SectionBudget('模型建立（5.x）', '5000-6000', '8-10', 5000, 6000,
                  r'^五、\s*模型建立与求解', '模型建立与求解'),
    SectionBudget('灵敏度/检验', '1300-1500', '3-4', 1300, 1500,
                  r'^六、\s*模型检验与分析', '模型检验与分析'),
    SectionBudget('优缺点/推广', '800-1000', '1', 800, 1000,
                  r'^七、\s*模型评价与改进', '模型评价与改进'),
    SectionBudget('参考文献', '300', '0.5'),
    SectionBudget('附录', '按最终源码实际长度', '不设项目自定义上限'),
    SectionBudget('合计', '见论文写作.md项目交付下限表',
                  '总 30–45 页（正文 20–30，其余为附录/参考文献）'),
)
