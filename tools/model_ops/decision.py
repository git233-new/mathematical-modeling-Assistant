#!/usr/bin/env python3
"""模型选型决策矩阵 — 可执行版本。

输入: problem_card dict (schemas/problem_card.json)
输出: {"champion": str, "challengers": [str], "matches": [...], "caveats": [...]}
来源: 知识库/建模增强/模型选型决策矩阵.md
"""

# ---------------------------------------------------------------------------
# 8 个子表，每行: (条件, 首选, 备选, 适用边界, 常见坑)
# 条件为 callable(problem_card, **kw) -> bool
# ---------------------------------------------------------------------------

PREDICTION = [
    (lambda c, **k: k.get("is_timeseries"),
     "ARIMA/SARIMA", ["Prophet", "LSTM"],
     "已检验平稳(ADF p<0.05)", "非平稳未差分直接用ARIMA必崩"),
    (lambda c, **k: c["data_scale"] == "tiny" and k.get("high_dim"),
     "PLS回归", ["SVR", "岭回归"],
     "响应与成分近似线性", "强非线性改SVR"),
    (lambda c, **k: c["data_scale"] == "tiny" and not k.get("nonlinear", False),
     "多元线性回归", ["Ridge", "Lasso"],
     "VIF<10、残差独立同分布", "VIF>10改Lasso；异方差改WLS"),
    (lambda c, **k: c["data_scale"] == "small" and not k.get("extrapolate"),
     "随机森林", ["GAM", "梯度提升树"],
     "不需要外推", "树模型无法外推，超出训练域塌回边界值"),
    (lambda c, **k: c["data_scale"] in ("medium", "large"),
     "XGBoost/LightGBM", ["BP神经网络", "SVR"],
     "样本>=500、特征<10K", "样本<500时RF更稳"),
    (lambda c, **k: k.get("output") == "binary_probability",
     "逻辑回归", ["Probit", "朴素贝叶斯"],
     "特征近似独立", "高度相关用朴素贝叶斯但牺牲可解释"),
]

OPTIMIZATION = [
    (lambda c, **k: c.get("multi_objective"),
     "NSGA-II", ["MOEA/D", "加权求和"],
     "目标数2-5", "目标>5用NSGA-III"),
    (lambda c, **k: any(v["type"] in ("binary", "discrete") for v in c.get("variables", []))
     and c["data_scale"] in ("tiny", "small"),
     "整数规划(分支定界)", ["割平面", "0-1枚举"],
     "变量<=100", "变量>100分支定界过慢，换启发式"),
    (lambda c, **k: k.get("stages") == "multi",
     "动态规划", ["强化学习(Q-learning)", "近似DP"],
     "状态空间可控", "状态爆炸改近似DP/RL"),
    (lambda c, **k: k.get("uncertainty_param"),
     "随机规划(机会约束)", ["鲁棒优化(Ben-Tal)", "分布鲁棒"],
     "分布已知用随机规划", "仅知区间用鲁棒"),
    (lambda c, **k: k.get("bilevel"),
     "双层规划(Bilevel/KKT)", ["主从博弈(Stackelberg)", "启发式"],
     "下层凸", "下层非凸改启发式"),
    (lambda c, **k: k.get("queueing"),
     "M/M/c+成本优化", ["离散事件仿真"],
     "到达/服务近似指数", "非指数分布用仿真"),
    (lambda c, **k: c.get("nonlinear") and k.get("complex_feasible"),
     "罚函数+GA", ["可行方向法", "SQP", "修复策略"],
     "罚因子可调", "可行域极窄时罚函数可能全违例"),
    (lambda c, **k: c.get("nonlinear"),
     "遗传算法GA", ["PSO", "模拟退火SA"],
     "编码可设计", "实数编码难设计时用PSO；GA易早熟"),
    (lambda c, **k: not c.get("nonlinear"),
     "线性规划LP", ["内点法", "单纯形"],
     "变量<10万", "变量>10万内点法更快"),
]

EVALUATION = [
    (lambda c, **k: k.get("has_expert"),
     "AHP", ["BWM", "ANP"],
     "指标<9/层", "指标>9一致性差改BWM；CR<0.1"),
    (lambda c, **k: k.get("fuzzy"),
     "模糊综合评价", ["灰色关联", "云模型"],
     "隶属函数可定", "难定改灰色关联"),
    (lambda c, **k: k.get("need_reduction"),
     "PCA+TOPSIS", ["因子分析+TOPSIS"],
     "变量线性相关性较强", "线性关系弱用因子分析"),
    (lambda c, **k: k.get("dea"),
     "DEA", ["MAUT", "交叉效率"],
     "决策单元数>=指标数x2", "单元数过少区分度差"),
    (lambda c, **k: k.get("dynamic_eval"),
     "动态TOPSIS", ["时序熵权法", "面板TOPSIS"],
     "权重需时变", "无需时变则静态即可"),
    (lambda c, **k: True,
     "熵权法+TOPSIS", ["CRITIC+VIKOR", "灰色关联"],
     "指标已量化", "强相关用CRITIC；必须正向化"),
]

CLASSIFICATION = [
    (lambda c, **k: k.get("labels") == "known" and not k.get("nonlinear", False),
     "逻辑回归/LDA", ["SVM(线性核)", "决策树"],
     "类别较均衡", "不平衡改加权LR或SMOTE"),
    (lambda c, **k: k.get("labels") == "known" and c["data_scale"] in ("medium", "large"),
     "XGBoost/LightGBM", ["BP神经网络", "CatBoost"],
     "类别数<10", "类别>10且不平衡需调objective"),
    (lambda c, **k: k.get("labels") == "known" and c["data_scale"] == "tiny" and k.get("high_dim"),
     "SVM(RBF核)", ["朴素贝叶斯", "KNN"],
     "特征多为连续", "全分类变量用朴素贝叶斯"),
    (lambda c, **k: k.get("labels") == "known",
     "随机森林", ["SVM(RBF核)", "XGBoost"],
     "特征数<样本数", "特征数>>样本数用SVM"),
    (lambda c, **k: k.get("cluster_shape") == "arbitrary",
     "DBSCAN", ["层次聚类", "谱聚类"],
     "密度差异适中", "密度差异大改层次"),
    (lambda c, **k: k.get("hierarchy"),
     "层次聚类(Agglomerative)", ["BIRCH", "Ward"],
     "样本<10万", "样本>10万用BIRCH"),
    (lambda c, **k: k.get("high_dim") and k.get("need_explain"),
     "PCA+K-Means", ["自编码器+K-Means"],
     "数据线性可分", "非线性流形用自编码器"),
    (lambda c, **k: k.get("multi_label"),
     "ML-KNN", ["Binary Relevance", "分类器链"],
     "标签数<20", "标签>20用ML-KNN"),
    (lambda c, **k: True,
     "K-Means+RF", ["GMM+RF", "层次+LDA"],
     "簇近球形", "K-Means对初值敏感，多次运行取最优"),
]

MECHANISM = [
    (lambda c, **k: k.get("physics") == "heat",
     "热传导方程(Fourier)", ["有限元FEM", "有限差分"],
     "简单几何+均匀介质用解析", "复杂几何/非均匀用FEM"),
    (lambda c, **k: k.get("physics") == "mechanics",
     "Newton/拉格朗日", ["多体动力学仿真"],
     "约束多时拉格朗日更利", "约束少可直接Newton"),
    (lambda c, **k: k.get("physics") == "optics",
     "几何光学(反射/折射)", ["光线追迹", "波动光学"],
     "衍射不显著", "衍射显著改波动光学"),
    (lambda c, **k: k.get("physics") == "fluid",
     "Navier-Stokes", ["伯努利方程(简化)"],
     "低速不可压无黏主导", "黏性/高速不可用伯努利"),
    (lambda c, **k: k.get("physics") == "circuit",
     "Maxwell/基尔霍夫", ["等效电路法"],
     "低频可用基尔霍夫", "高频必须用Maxwell全波"),
    (lambda c, **k: k.get("physics") == "chemistry",
     "Arrhenius/速率方程", ["CFD+反应模型"],
     "简单均相反应", "非均相/复杂机理用CFD"),
    (lambda c, **k: k.get("physics") == "vibration",
     "二阶ODE(质量-弹簧-阻尼)", ["拉格朗日(多自由度)"],
     "阻尼线性", "阻尼非线性用数值积分"),
    (lambda c, **k: k.get("physics") == "acoustics",
     "声线传播(Snell分层)", ["射线追踪", "简正波"],
     "浅海高频", "深海低频简正波更准"),
]

GRAPH = [
    (lambda c, **k: k.get("graph_task") == "shortest_single",
     "Dijkstra", ["A*", "Bellman-Ford"],
     "无负权边", "有负权边用Bellman-Ford"),
    (lambda c, **k: k.get("graph_task") == "shortest_all",
     "Floyd-Warshall", ["Johnson算法"],
     "节点<1000", "稀疏用Johnson更快"),
    (lambda c, **k: k.get("graph_task") == "max_flow",
     "Ford-Fulkerson/Dinic", ["最小费用最大流"],
     "容量非负", "注意整数容量保证整数流"),
    (lambda c, **k: k.get("graph_task") == "mst",
     "Prim/Kruskal", ["Boruvka"],
     "边权非负", "稠密图Prim，稀疏图Kruskal"),
    (lambda c, **k: k.get("graph_task") == "matching",
     "匈牙利/KM", ["最大流转化"],
     "节点<500", "节点>500用贪心近似"),
    (lambda c, **k: k.get("graph_task") == "robustness",
     "图连通性+节点移除", ["渗流理论", "谱方法"],
     "小网络直接枚举", "大网络用近似"),
    (lambda c, **k: k.get("graph_task") == "centrality",
     "PageRank/度中心性", ["介数中心性", "Katz"],
     "有向加权用变体", "未归一化不可横向比"),
    (lambda c, **k: k.get("graph_task") == "community",
     "Louvain", ["Label Propagation", "谱聚类"],
     "规模大用Louvain", "模块度有分辨率极限"),
]

SIMULATION = [
    (lambda c, **k: k.get("sim_type") == "continuous",
     "系统动力学(SD)", ["ODE数值积分(RK4)"],
     "反馈回路清晰", "因果回路图要先画"),
    (lambda c, **k: k.get("sim_type") == "discrete_event",
     "离散事件仿真(DES)", ["排队论解析(M/M/c)"],
     "到达/服务非指数", "指数假设不成立时解析失效"),
    (lambda c, **k: k.get("sim_type") == "spatial",
     "元胞自动机(CA)", ["ABM", "反应扩散方程"],
     "局部规则明确", "邻域/规则敏感，需敏感性分析"),
    (lambda c, **k: k.get("sim_type") == "queue",
     "M/M/c+成本优化", ["离散事件仿真"],
     "稳态可达", "非稳态/非指数用DES"),
    (lambda c, **k: k.get("sim_type") == "monte_carlo",
     "蒙特卡洛模拟", ["拉丁超立方", "准蒙特卡洛"],
     "可定义输入分布", "必须固定随机种子"),
    (lambda c, **k: k.get("sim_type") == "agent",
     "演化博弈仿真", ["多Agent仿真"],
     "有限理性主体", "收益矩阵/更新规则要说明"),
]

STATISTICAL = [
    (lambda c, **k: k.get("stat_task") == "two_group",
     "t检验", ["Mann-Whitney U", "Bootstrap"],
     "正态且方差齐", "非正态小样本用U"),
    (lambda c, **k: k.get("stat_task") == "multi_group",
     "单因素ANOVA", ["Kruskal-Wallis", "Welch ANOVA"],
     "满足前提", "多次t检验替代ANOVA会膨胀I类错误"),
    (lambda c, **k: k.get("stat_task") == "multi_factor",
     "双因素ANOVA", ["线性混合模型", "响应曲面"],
     "随机效应存在用混合", "交互显著不能只看主效应"),
    (lambda c, **k: k.get("stat_task") == "correlation",
     "Pearson", ["Spearman", "互信息"],
     "线性+正态用Pearson", "有序/异常值用Spearman"),
    (lambda c, **k: k.get("stat_task") == "causal",
     "格兰杰因果", ["工具变量", "DID"],
     "时序数据", "非时序格兰杰不适用"),
    (lambda c, **k: k.get("stat_task") == "rsm",
     "响应曲面RSM", ["正交设计", "均匀设计"],
     "因素<5先筛选", "因素>5先用Plackett-Burman"),
    (lambda c, **k: k.get("stat_task") == "estimation",
     "MLE+Bootstrap", ["贝叶斯估计", "刀切法"],
     "无强先验用MLE", "有先验用贝叶斯"),
    (lambda c, **k: k.get("stat_task") == "compositional",
     "CLR变换+标准方法", ["ILR", "ALR"],
     "先解除单纯形约束", "直接欧氏距离在成分数据上失效"),
    (lambda c, **k: k.get("stat_task") == "grey",
     "灰色关联分析", ["灰色GM(1,1)预测", "互信息"],
     "样本<20", "样本>50用互信息更可靠"),
]

# 路由: problem_type -> 子表
_TABLES = {
    "prediction": PREDICTION,
    "optimization": OPTIMIZATION,
    "evaluation": EVALUATION,
    "classification": CLASSIFICATION,
    "clustering": CLASSIFICATION,
    "simulation": SIMULATION,
    "network": GRAPH,
    "statistical_test": STATISTICAL,
    "fitting": PREDICTION,
    "dynamic": MECHANISM,
    "game_theory": SIMULATION,
    "dimensionality_reduction": EVALUATION,
}


def decide(problem_card: dict, **kw) -> dict:
    """problem_card (schemas/problem_card.json) -> 模型推荐。

    kw 补充条件(可选):
      is_timeseries, high_dim, nonlinear, extrapolate, output,
      stages, uncertainty_param, bilevel, queueing, complex_feasible,
      has_expert, fuzzy, need_reduction, dea, dynamic_eval,
      labels, cluster_shape, hierarchy, need_explain, multi_label,
      physics, graph_task, sim_type, stat_task
    """
    ptypes = problem_card.get("problem_types", [])
    scale = problem_card.get("data_scale", "small")
    card = {**problem_card, "data_scale": scale}

    matches = []
    seen = set()
    for pt in ptypes:
        table = _TABLES.get(pt)
        if not table:
            continue
        for cond, primary, alts, boundary, pitfall in table:
            try:
                if cond(card, **kw) and primary not in seen:
                    seen.add(primary)
                    matches.append({
                        "category": pt, "primary": primary,
                        "alternatives": alts, "boundary": boundary,
                        "pitfall": pitfall,
                    })
            except (KeyError, TypeError):
                continue

    if not matches:
        return {"champion": None, "challengers": [],
                "matches": [], "caveats": ["无匹配行，检查 problem_card 输入"]}

    champion = matches[0]["primary"]
    challengers = list(matches[0]["alternatives"])
    for m in matches[1:]:
        if m["primary"] not in challengers:
            challengers.append(m["primary"])

    return {
        "champion": champion,
        "challengers": challengers[:4],
        "matches": matches,
        "caveats": [m["pitfall"] for m in matches],
    }


def demo():
    card = {
        "question": "Q1",
        "problem_types": ["prediction"],
        "variables": [],
        "objectives": [],
        "data_scale": "small",
    }
    r = decide(card, nonlinear=True)
    print(f"champion: {r['champion']}")
    print(f"challengers: {r['challengers']}")
    for m in r["matches"]:
        print(f"  [{m['category']}] {m['primary']} | {m['boundary']}")
    return r


if __name__ == "__main__":
    demo()
