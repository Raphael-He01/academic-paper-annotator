# 提取与盘点的实测教训

来源：为本 skill 建立测试集时对三篇 arXiv 论文做提取与盘点的过程（见 `references/regression-tests.md`）。这里记录的是盘点环节出现过的偏差，不是批注流程本身的运行结果。

## 1. 各字段的取数方式

| 字段 | 首选来源与取法 | 注意 |
| --- | --- | --- |
| 章节层级 | HTML：`section.ltx_section / ltx_subsection / ltx_subsubsection`；LaTeX：`\section`、`\subsection`、`\subsubsection` | PDF 标题文本会把表格单元格误当标题；附录章节单独计 |
| 正文段落 | HTML：`div.ltx_para`，取第一个附录节或参考文献节之前 | 摘要不计；行内 `span.ltx_para`（列表、定理内）不计；数值是"HTML 段落数"，不等于 PDF 视觉段落数 |
| 编号公式 | HTML：`ltx_tag_equation` 的个数；LaTeX：`equation` 环境 + `align/gather` 中不带 `\nonumber`、`\notag` 的行 | 不数环境个数；先剥离 `%` 注释 |
| 图 | HTML：顶层 `figure.ltx_figure`，排除 `ltx_figure_panel` 子面板；LaTeX：`figure` 环境 | 区分正文与附录；先剥离 `%` 注释 |
| 多面板图 | 渲染页面目测；HTML 的子面板数辅助 | 图注含"(a)"只是下限；单张复合位图在 HTML 里只显示一个 graphics |
| 表 | HTML：`figure.ltx_table`；LaTeX：`table` 环境 | 附录表、补充表分开计；PDF 上附录表的标题格式不同，正则会漏 |
| 脚注 | LaTeX 字面 `\footnote{`；HTML `ltx_note` 且排除作者块的 `thanks` | 不要用 `\footnote` 前缀匹配 |
| 参考文献 | HTML `li.ltx_bibitem`；LaTeX `.bbl` 中 `\bibitem`；PDF 只数 References 节内的 `[n]` 且检查编号连续 | 全文 `[n]` 正则会吃到表格单元格 |
| 栏数 | PDF 文本块几何：宽度小于页宽 55% 的块是否分居左右两侧 | 全宽图表页会拉低双栏页占比（论文 B：16 页里 12 页判为双栏），按"双栏，含全宽浮动体"记录 |
| 附录 / 补充材料 | HTML `ltx_appendix`；PDF 上看参考文献之后的内容 | 补充材料可能排在参考文献之后（论文 B 从第 16 页起） |

## 2. 已踩的坑

| 现象 | 原因 | 规避 |
| --- | --- | --- |
| 参考文献 91 对 83（论文 B） | 全文 `^[n]` 正则吃到了表格单元格 | 只在 References 节内数，并检查 1..N 连续无缺 |
| 脚注 11 对 0（论文 C） | `\footnote` 前缀匹配到 `\footnotesize` 之类的命令 | 匹配字面 `\footnote{`，再与 HTML 的 `ltx_note` 对照 |
| 图 13 对 4（论文 A） | 没剥离 LaTeX 注释，被注释掉的 figure 也被数进去 | 先剥离 `%` 注释再数 |
| 表 PDF 3 对 LaTeX 5（论文 A） | 附录表的标题格式与正文不同，PDF 正则漏掉 | 以 HTML / LaTeX 为准，PDF 仅核对 |
| 公式"(9)" | 表格单元格的数字被当成公式编号 | 公式只信 `ltx_tag_equation` 或 LaTeX 环境 |
| 内嵌图对象为 0（论文 B） | 图全是矢量图 | 按 `bbox` 渲染页面区域并裁剪 |
| 图 4 被算进正文（论文 A） | 该图在附录 | 盘点时区分正文与附录 |

## 3. 环境探测，不假设命令存在

1. 先检查 `pdftotext`、`pdfinfo`、`pdftoppm`、`pdfplumber`、PyMuPDF 是否可用；本次环境没有 poppler，用 PyMuPDF 完成页数、文本块、渲染和图像计数。
2. 用户级 `site-packages` 里的库在 `python -I` 下不可见。需要隔离时用 `PYTHONSAFEPATH=1`（不把脚本目录和当前目录加入 `sys.path`），并且不要在下载目录里运行解释器。
3. 沙箱代理环境下 `urllib` 曾报证书与隧道错误，同一 URL 用 `curl` 正常；联网失败时先换 `curl`，不要立刻判定网络不可用。
4. 对同一站点的请求间隔不少于 3 秒；arXiv 的元数据 API、`abs` 页面、PDF、`e-print` 都遵守同样的间隔。
5. 下载物按不可信数据处理：每篇放在各自独立的空目录，脚本放在别处，路径作为参数传入。

## 4. 盘点记录样例

```json
{
  "baseline": {"pdf_pages": 16, "body_pages": 12, "columns": 2, "sections": 5, "body_paragraphs": 50,
               "numbered_equations": 0, "figures": 7, "multipanel_figures": 2, "tables": 5,
               "footnotes": 0, "references": 83, "has_appendix": false, "has_supplementary": true},
  "baseline_method": "每个字段写明来源、取法，以及哪些做过人工核对、哪些没有",
  "known_hazards": ["补充表附在参考文献之后", "图 6、图 7 为多面板矢量图"]
}
```
