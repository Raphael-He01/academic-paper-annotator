# 可复用前端和发布检查数据

## 前端资产

`assets/workbench.css` / `assets/workbench.js` 来自 ThyGPT 成品使用的前端，已有静态检查和模拟 DOM 行为检查。它们是可复用起点，不是自动论文翻译器；浏览器视觉和打印仍需在目标环境检查。

接入时保持脚本依赖的结构：正文为 `.unit`，含 `id`、`data-depth`、`data-section` 和 `data-search`；英文区域为 `.original`，中文为 `.translation`；每段有 `details.annotation`。正文来源字段只读。工具栏需要 `controls`、`mode`、`annotations`、`deep`、`expand`、`collapse`、`print`、`current`、`progress`、`progress-text`、`search`、`search-go`、`prev`、`next`、`clear`、`results`。类别开关使用 `data-hl`，五类标记类为 `hl claim/concept/evidence/limitation/method`。搜索目标用 `data-search`。可直接使用 `scripts/build_workbench.py --data <数据目录> --output <最终HTML>`，也可按同一结构接入专用构建器。仓库的 `examples/synthetic` 是自编完整样例，能够离线重建。安装后的 skill 不依赖仓库中的样例才能运行。

## 通用构建器

```text
python3 scripts/build_workbench.py --data <数据目录> --output FINAL.html
```

数据目录包含 `paper.json`（title、authors、notice、guide、source_note、references）、下列 units／figures／tables／analysis 数据；图片路径相对数据目录，不允许越出该目录。构建器只输出 HTML，不会生成“审阅通过”记录。每次改动成品后，已有审阅记录的文件摘要不匹配就要重新审阅。

图像记录另提供 `image_path`。表格可有 title、caption、label_translations；数据原值保留在 rows，中文解释在原始单元之外。复杂跨行跨列表格和 JATS 引用排版可能需要专用构建，不得为了通过通用格式而简化或丢弃来源结构。论文需要公式时应保留离线公式图，单元可通过 image_path 嵌入原始裁剪。

analysis 可有 section_reviews、evaluation、learning、questions、relations（有向依赖）与 graph_labels。构建器为 relations 生成 SVG 及等价文字关系，不允许依赖图含环；反驳／限定的表达如需循环，应调整论证表示或使用专用图。

## 发布检查命令

仅依赖 Python 3.10+ 标准库；不会联网或修改论文文件：

```text
python3 scripts/validate_release.py --html FINAL.html --units units.json --baseline baseline.json --figures figures.json --tables tables.json --analysis analysis.json --review review.json --report release-report.json
```

Windows 可用本机可用的 `python` 代替 `python3`。检查脚本不会自动安装依赖或打开浏览器。文件路径不应写成创作者电脑的绝对路径。

## 数据契约

- `units.json`：单元数组。字段为正文 §4.2 所示；`unit_type` 至少区分 `body` / `abstract`；`original_text`、`translation_zh`、状态、批注和精确高亮片段必须真实对应内容。HTML 内同一单元 ID 下 `.original` 及 `.translation` 文本必须与数据一致。
- 有文献上标的正文另提供 `numeric_source_text`：从来源结构中仅去掉书目引用标记，用于避免将引用号误当译文数值。不得手工删掉真正结果数字以通过检查。数字字面值覆盖检查不证明单位、分母或数值语义正确。
- `baseline.json`：`required_unit_ids` 为独立范围清单；`unit_counts` 为按类型的来源盘点；`figure_count`、`table_count`、`reference_ids` 来自来源盘点，另记 `baseline_method`。数不准时写 null，检查返回 not_auditable，视为尚不可验收，不凭成品回填。
- `figures.json`：包含 `id`、`original_text`、`translation_zh` 的数组；最终页面有同名 ID、对应原图和完整双语图注。图像本身和面板完整性仍需视觉核对。
- `tables.json`：表格数组，每项 `id`、`rows`；`rows` 是保留原值及原顺序的单元格二维数组；检查按表 ID 和行边界比对，不把多个表格扁平拼接。HTML 每个原始单元内容用 `.cell-original` 包裹，中文解释放在该标记之外。
- `analysis.json`：`claims` 数组，每项 `id`、`units`（来源单元 ID 数组）、`quote`（逐字证据摘录）；每条声明的 ID 必须唯一且在 HTML 可定位，全部来源 ID 必须存在；其他分析字段按正文要求记录。
- `review.json`：`file_sha256` 对应最终 HTML；`content_review` 包含真实的 `status`（passed / pending / failed）、范围和发现；`browser_review` 为 passed、blocked 或 unavailable。后两种必须有 `reason` 和 `plan`，且不能把阻断说成通过。

`validate_release.py` 能阻断覆盖缺失、静态原文或表格值不一致、失效锚点、不完整译文状态、错误高亮、无来源证据、过期审阅摘要等问题。检查还比对正文渲染顺序、批注是否实际呈现、图注与图像是否存在、高亮实际片段与类别、外部或相对路径运行资源；完整工作台必须提供 analysis 数据。它不证明翻译质量、论文事实、图片完整解码、裁剪或浏览器效果。数值／限定词比对和内容审阅仍应按 §8 执行。

所有输入先做结构检查；无效根类型、null 数组或未知基线会写入新的 not_auditable 报告，不保留旧的 ready 报告。报告路径不得覆盖输入文件。

原文提取状态必须 verified，来源核验状态为 page_verified 或 sampled；failed、partial、unverified 或未记录的来源检查不能进入最终发布判定。上述状态仍需有实际来源核对依据，不允许为了过检查批量标为 verified。

返回码：0 为无静态发布阻断（可能仍有真实验证限制）；1 为检查发现阻断；2 为数据缺失或无法解析。报告的 `ready_with_verification_limits` 不等于完整浏览器验收。
