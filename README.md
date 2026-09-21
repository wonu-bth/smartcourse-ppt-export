# smartcourse-ppt-export

把「只能在网页里翻看、无法下载」的课件 PPT 一键导出为 **PDF + PPTX**。

适用于把课件渲染成逐页图片的课程平台（典型 URL 长这样）：

```
https://<域名>/doc/<课件ID>/thumb/1.png
https://<域名>/doc/<课件ID>/thumb/2.png
...
```

例如华中科技大学 smartcourse 平台（超星架构）。任何 agent 环境（WorkBuddy、
Claude Code 等）都可以直接阅读 [`SKILL.md`](SKILL.md) 后使用本工具；普通用户
按下面的说明操作即可。

## 准备工作（只需一次）

1. 安装 Python 3.10 或更高版本：https://www.python.org/downloads/
   （安装时勾选 **Add Python to PATH**）
2. 打开命令行（Win + R 输入 `cmd` 回车），执行：

   ```bash
   pip install pillow img2pdf python-pptx
   ```

## 使用方法

### 第 1 步：拿到课件链接（1 分钟）

1. 在浏览器里打开课件页面，把 PPT 往后翻几页（触发加载）
2. 按 `F12` 打开开发者工具 → 点「网络 / Network」标签 → 刷新页面
3. 点类型筛选里的「Img」，在列表里找到 `1.png`
4. 右键它 → 复制 → **复制链接地址**

### 第 2 步：一条命令导出

```bash
python scripts/export_slides.py "把上一步复制的链接粘贴到这里" -o "课件名称"
```

就这么多。脚本会自动：

- 探测总页数并逐页下载（连错 3 页自动停止）
- 生成 `课件名称.pdf` 和 `课件名称.pptx`，原始大图在 `课件名称/` 文件夹里备用

### 其他写法

```bash
# 只有课件 ID（链接里 /doc/ 和 /thumb/ 之间那串字母数字）时：
python scripts/export_slides.py 911f063fa250bae64bc37222cbed0b4f -o "第一章_绪论"

# 只导出 PDF（不做 PPTX）：
python scripts/export_slides.py "<链接>" --pdf-only

# 先下载前 3 页试试效果：
python scripts/export_slides.py "<链接>" --limit 3
```

## 常见问题

| 现象 | 原因与解决 |
|---|---|
| 报 HTTP 500 | 通常是链接不完整：`thumb/` 之前的所有路径（包括 `/doc/8d/` 里那两位前缀）必须原样保留。请重新复制粘贴完整链接，不要手打或删改 |
| 第一页就 404 | 课件 ID 抄错了一个字符（ID 很长，请复制粘贴） |
| 下载下来的不是图片 / 提示登录 | 该资源需要登录态：用 `--cookie "名字=值; ..."` 把浏览器里的 Cookie 传进来（复制方法见 SKILL.md） |
| 提示缺少模块 | 重新执行 `pip install pillow img2pdf python-pptx` |
| PPT 打开是整页图片、文字改不了 | 平台本来就只提供图片版，这是正常现象 |

## 许可与声明

- 代码以 MIT 许可开源（见 [LICENSE](LICENSE)）
- 请仅用于个人学习，遵守所在平台的服务条款，尊重授课教师的版权
