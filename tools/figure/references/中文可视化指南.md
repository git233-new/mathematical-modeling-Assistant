# 数据可视化指南

本指南提供数学建模论文中常用图表的代码模板，包括Python和Matlab两种实现。

## 1. 折线图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

x = np.linspace(0, 10, 100)
y1 = np.sin(x)
y2 = np.cos(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y1, 'b-', linewidth=2, label='sin(x)')
plt.plot(x, y2, 'r--', linewidth=2, label='cos(x)')

plt.xlabel('X轴标签', fontsize=12)
plt.ylabel('Y轴标签', fontsize=12)
plt.title('标题', fontsize=14)
plt.legend(loc='best')
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('line_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
x = linspace(0, 10, 100);
y1 = sin(x);
y2 = cos(x);

figure;
plot(x, y1, 'b-', 'LineWidth', 2);
hold on;
plot(x, y2, 'r--', 'LineWidth', 2);

xlabel('X轴标签');
ylabel('Y轴标签');
title('标题');
legend('sin(x)', 'cos(x)');
grid on;
hold off;
saveas(gcf, 'line_plot.png');
```

## 2. 柱状图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

categories = ['类别A', '类别B', '类别C', '类别D']
values1 = [23, 45, 56, 78]
values2 = [35, 52, 43, 65]

x = np.arange(len(categories))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
bars1 = ax.bar(x - width/2, values1, width, label='组1', color='steelblue')
bars2 = ax.bar(x + width/2, values2, width, label='组2', color='coral')

ax.set_xlabel('类别', fontsize=12)
ax.set_ylabel('数值', fontsize=12)
ax.set_title('柱状图标题', fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels(categories)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.7)

for bar in bars1:
    height = bar.get_height()
    ax.annotate(f'{height}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('bar_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
categories = {'类别A', '类别B', '类别C', '类别D'};
values1 = [23, 45, 56, 78];
values2 = [35, 52, 43, 65];

figure;
bar([values1; values2]);
set(gca, 'XTickLabel', categories);
xlabel('类别');
ylabel('数值');
title('柱状图标题');
legend('组1', '组2');
grid on;
saveas(gcf, 'bar_plot.png');
```

## 3. 散点图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

np.random.seed(42)
x = np.random.randn(100)
y = x + np.random.randn(100) * 0.5

plt.figure(figsize=(10, 6))
plt.scatter(x, y, c='blue', alpha=0.6, edgecolors='black', linewidth=0.5)

plt.xlabel('X轴标签', fontsize=12)
plt.ylabel('Y轴标签', fontsize=12)
plt.title('散点图标题', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)

z = np.polyfit(x, y, 1)
p = np.poly1d(z)
plt.plot(x, p(x), "r--", linewidth=2, label=f'拟合直线: y={z[0]:.2f}x+{z[1]:.2f}')
plt.legend()

plt.tight_layout()
plt.savefig('scatter_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
x = randn(100, 1);
y = x + randn(100, 1) * 0.5;

figure;
scatter(x, y, 'filled');

xlabel('X轴标签');
ylabel('Y轴标签');
title('散点图标题');
grid on;

p = polyfit(x, y, 1);
x_fit = linspace(min(x), max(x), 100);
y_fit = polyval(p, x_fit);
hold on;
plot(x_fit, y_fit, 'r--', 'LineWidth', 2);
legend('数据点', sprintf('拟合直线: y=%.2fx+%.2f', p(1), p(2)));
hold off;

saveas(gcf, 'scatter_plot.png');
```

## 4. 饼图

### Python实现
```python
import matplotlib.pyplot as plt

labels = ['A类', 'B类', 'C类', 'D类']
sizes = [25, 35, 20, 20]
explode = (0, 0.1, 0, 0)
colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']

plt.figure(figsize=(8, 8))
plt.pie(sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.1f%%', shadow=True, startangle=90)
plt.axis('equal')
plt.title('饼图标题', fontsize=14)
plt.savefig('pie_chart.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
labels = {'A类', 'B类', 'C类', 'D类'};
sizes = [25, 35, 20, 20];
explode = [0, 0.1, 0, 0];

figure;
pie(sizes, explode, labels);
title('饼图标题');
saveas(gcf, 'pie_chart.png');
```

## 5. 热力图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

data = np.random.rand(10, 10)
labels = [f'变量{i+1}' for i in range(10)]

fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(data, cmap='YlOrRd')

ax.set_xticks(np.arange(10))
ax.set_yticks(np.arange(10))
ax.set_xticklabels(labels)
ax.set_yticklabels(labels)

plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

for i in range(10):
    for j in range(10):
        text = ax.text(j, i, f'{data[i, j]:.2f}',
                       ha="center", va="center", color="black", fontsize=8)

fig.colorbar(im, ax=ax)
plt.title('热力图标题', fontsize=14)
plt.tight_layout()
plt.savefig('heatmap.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
data = rand(10, 10);

figure;
imagesc(data);
colorbar;
colormap('YlOrRd');
set(gca, 'XTick', 1:10);
set(gca, 'YTick', 1:10);
set(gca, 'XTickLabel', arrayfun(@(x) sprintf('变量%d', x), 1:10, 'UniformOutput', false));
set(gca, 'YTickLabel', arrayfun(@(x) sprintf('变量%d', x), 1:10, 'UniformOutput', false));
title('热力图标题');
saveas(gcf, 'heatmap.png');
```

## 6. 误差棒图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

x = np.arange(1, 6)
y = [4, 6, 5, 8, 7]
yerr = [0.5, 0.3, 0.4, 0.6, 0.2]

plt.figure(figsize=(10, 6))
plt.errorbar(x, y, yerr=yerr, fmt='o-', capsize=5, capthick=2,
             markersize=8, linewidth=2, color='steelblue')

plt.xlabel('实验序号', fontsize=12)
plt.ylabel('测量值', fontsize=12)
plt.title('误差棒图标题', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('errorbar_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
x = 1:5;
y = [4, 6, 5, 8, 7];
yerr = [0.5, 0.3, 0.4, 0.6, 0.2];

figure;
errorbar(x, y, yerr, 'o-', 'LineWidth', 2, 'CapSize', 5, 'MarkerSize', 8);

xlabel('实验序号');
ylabel('测量值');
title('误差棒图标题');
grid on;
saveas(gcf, 'errorbar_plot.png');
```

## 7. 子图布局

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

axes[0, 0].plot(x, np.sin(x), 'b-')
axes[0, 0].set_title('子图1')

axes[0, 1].plot(x, np.cos(x), 'r-')
axes[0, 1].set_title('子图2')

axes[1, 0].plot(x, np.tan(x), 'g-')
axes[1, 0].set_title('子图3')
axes[1, 0].set_ylim(-5, 5)

axes[1, 1].plot(x, np.exp(-x/5), 'm-')
axes[1, 1].set_title('子图4')

fig.suptitle('总标题', fontsize=16, y=1.02)
plt.tight_layout()
plt.savefig('subplots.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
x = linspace(0, 10, 100);

figure;
subplot(2, 2, 1);
plot(x, sin(x));
title('子图1');

subplot(2, 2, 2);
plot(x, cos(x));
title('子图2');

subplot(2, 2, 3);
plot(x, tan(x));
title('子图3');
ylim([-5, 5]);

subplot(2, 2, 4);
plot(x, exp(-x/5));
title('子图4');

suptitle('总标题');
saveas(gcf, 'subplots.png');
```

## 8. 3D图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

x = np.arange(-5, 5, 0.25)
y = np.arange(-5, 5, 0.25)
X, Y = np.meshgrid(x, y)
Z = np.sin(np.sqrt(X**2 + Y**2))

surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none', alpha=0.8)

ax.set_xlabel('X轴')
ax.set_ylabel('Y轴')
ax.set_zlabel('Z轴')
ax.set_title('3D表面图')

fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
plt.savefig('3d_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
[x, y] = meshgrid(-5:0.25:5, -5:0.25:5);
z = sin(sqrt(x.^2 + y.^2));

figure;
surf(x, y, z);
colormap('viridis');
xlabel('X轴');
ylabel('Y轴');
zlabel('Z轴');
title('3D表面图');
colorbar;
saveas(gcf, '3d_plot.png');
```

## 9. 直方图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

np.random.seed(42)
data1 = np.random.normal(0, 1, 1000)
data2 = np.random.normal(3, 1, 1000)

plt.figure(figsize=(10, 6))
plt.hist(data1, bins=30, alpha=0.7, label='数据1', color='steelblue')
plt.hist(data2, bins=30, alpha=0.7, label='数据2', color='coral')

plt.xlabel('数值', fontsize=12)
plt.ylabel('频数', fontsize=12)
plt.title('直方图标题', fontsize=14)
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('histogram.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
data1 = randn(1000, 1) * 1 + 0;
data2 = randn(1000, 1) * 1 + 3;

figure;
histogram(data1, 30, 'FaceAlpha', 0.7);
hold on;
histogram(data2, 30, 'FaceAlpha', 0.7);
hold off;

xlabel('数值');
ylabel('频数');
title('直方图标题');
legend('数据1', '数据2');
grid on;
saveas(gcf, 'histogram.png');
```

## 10. 箱线图

### Python实现
```python
import matplotlib.pyplot as plt
import numpy as np

data = [np.random.normal(0, 1, 100),
        np.random.normal(3, 1, 100),
        np.random.normal(1.5, 1.5, 100)]

fig, ax = plt.subplots(figsize=(10, 6))
bp = ax.boxplot(data, labels=['组1', '组2', '组3'], patch_artist=True)

colors = ['#ff9999', '#66b3ff', '#99ff99']
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)

ax.set_xlabel('组别', fontsize=12)
ax.set_ylabel('数值', fontsize=12)
ax.set_title('箱线图标题', fontsize=14)
ax.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('boxplot.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Matlab实现
```matlab
data1 = randn(100, 1);
data2 = randn(100, 1) + 3;
data3 = randn(100, 1) + 1.5;

figure;
boxplot([data1, data2, data3], 'Labels', {'组1', '组2', '组3'});

xlabel('组别');
ylabel('数值');
title('箱线图标题');
grid on;
saveas(gcf, 'boxplot.png');
```

## 图表设计原则

### 1. 清晰性
- 图表应清晰展示数据
- 避免过多的装饰元素
- 标注应完整、准确

### 2. 美观性
- 选择合适的颜色搭配
- 保持图表比例协调
- 注意留白和布局

### 3. 准确性
- 数据应真实可靠
- 坐标轴刻度应合理
- 避免误导性的可视化

### 4. 完整性
- 应包含标题
- 应标注坐标轴名称和单位
- 应有图例（如适用）
- 多图应有统一编号

### 5. 格式要求
- 分辨率不低于300 DPI
- 推荐使用PNG或PDF格式
- 图表尺寸应适合论文排版
