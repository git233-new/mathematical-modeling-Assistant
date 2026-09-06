# 图表模板目录与绘图配方

每个模板 id 对应 `templates/` 下的一个可运行脚本。渲染统一使用
`tools/figure/runtime/render_template.py`。

## 模板目录

| id | 脚本 | 图表 |
| --- | --- | --- |
| `multiclass-shap-combo` | `make_multiclass_shap_combo.py` | 多分类 SHAP 柱状图与蜂群图组合图 |
| `paired-raincloud` | `make_paired_raincloud.py` | 配对云雨图 |
| `cv-roc-ci` | `make_cv_roc_ci.py` | 交叉验证 ROC 曲线与置信区间图 |
| `taylor-diagram` | `make_taylor_diagram.py` | 多模型评价泰勒图 |
| `correlation-pairgrid` | `make_correlation_pairgrid.py` | 数据分布、拟合线、置信区间、相关系数组合图 |
| `prediction-marginal-grid` | `make_prediction_marginal_grid.py` | 预测值与真实值边缘分布组合图 |
| `rf-tpe-surface` | `make_rf_tpe_surface.py` | TPE 优化 RF 模型 3D 曲面图 |
| `grouped-corr-split-violin` | `make_grouped_corr_split_violin.py` | 下三角相关矩阵 + 特征分组与半边小提琴图 |
| `grouped-circular-heatmap` | `make_grouped_circular_heatmap.py` | 分组环形热图 |
| `urban-park-cooling-combo` | `make_urban_park_cooling_combo.py` | 堆叠图 + 云雨图 + 箱线图组合图 |
| `nature-chord-diagram` | `make_nature_chord_diagram.py` | Nature 风格和弦图 |

## 模板配方

优先使用打包脚本。这些说明仅用于模板复制到工作区后的定制。

- SHAP 组合图：堆叠的水平方向平均绝对重要性条形图，外加类别/模型蜂群条带以及特征值颜色条。
- 配对云雨图：半小提琴图、抖动散点观测、箱体几何、均值菱形标记以及连接均值趋势线。
- 带置信区间的 ROC：将各折曲线插值到统一的 FPR 网格，绘制均值曲线、标准差带、AUC 均值 ± 标准差图例以及对角线基线。
- 泰勒图：极坐标系，角度为 `arccos(correlation)`，半径为模型标准差。
- 相关矩阵网格：下半部分为散点/拟合置信区间，对角线为直方图，上半部分为带发散配色与显著性星号的系数单元格。
- 预测边缘分布网格：预测值-真实值散点图，外加顶部/右侧直方图与类 KDE 曲线。
- 3D 调参曲面：`mpl_toolkits.mplot3d`、平滑响应曲面、颜色条以及校验过的相机视角。
- 分裂小提琴图 + 相关矩阵：带符号的下三角标记矩阵，外加左/右半小提琴分布对比。
- 环形热力图：极坐标条形、翻转的外侧标签、中心图例以及按环独立的配色。
- 和弦图：外侧 `Wedge` 扇区与半透明贝塞尔 `PathPatch` 连接带。
- 城市降温组合图：堆叠城市条形、云雨图指标面板、城市图例以及带连接均值的箱线图。
