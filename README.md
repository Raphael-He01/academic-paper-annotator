# Academic Paper Annotator

把英文学术论文整理为可离线阅读的英中精读工作台：逐段原文与译文、分级批注、主张—证据矩阵、论证图、原图表与来源定位。

本项目是供助手使用的 **skill 与可复用构建／检查工具**。全文提取、翻译和论证判断由助手结合原文完成；Python 工具负责静态构建和确定性检查。

## 快速开始

1. 下载或克隆仓库，把 `academic-paper-annotator/` 整个文件夹复制到客户端约定的 skill 目录。Codex 通常为 `$CODEX_HOME/skills`，未设置时为 `~/.codex/skills`；已有同名版本请先备份。
2. 重新加载 skills 或开启新对话，确认出现 `academic-paper-annotator`。
3. 提供完整论文及可用补充材料，发送：

```text
请用 $academic-paper-annotator 完整精读这篇论文。
我的背景是相邻领域研究生，目的是理解论证并学习研究设计。
请按完整范围输出离线双语 HTML、来源覆盖和检查记录，交付前核对最终文件。
```

默认处理整篇，无需逐章发送“继续”。用户明确要求试读时，按用户限定的范围处理。内容未完成时不能冒称最终版；真正的材料或工具阻断需单独说明。

## 自包含演示

打开 [`examples/synthetic/index.html`](examples/synthetic/index.html) 查看自编演示。其六段双语内容、一幅图、一张表和 CSV 均为合成教学材料，说明为什么“召回率提高”不等于“总体效用更好”；没有患者、真实模型或实证研究结论。

演示包含三种阅读模式、批注、高亮开关、深读过滤、搜索导航、论证图和打印样式。查看无需 Python 或联网。

重建演示（Python 3.10+，无第三方依赖）：

```sh
python3 academic-paper-annotator/scripts/build_workbench.py --data examples/synthetic --output examples/synthetic/index.html
python3 academic-paper-annotator/scripts/validate_release.py --html examples/synthetic/index.html --units examples/synthetic/units.json --baseline examples/synthetic/baseline.json --figures examples/synthetic/figures.json --tables examples/synthetic/tables.json --analysis examples/synthetic/analysis.json --review examples/synthetic/review.json --report examples/synthetic/release-report.json
```

修改最终 HTML 后，旧审阅摘要会失效；构建器不会自动替你把内容或浏览器审阅标为通过。

## 交付检查

- 核对原文、译文与最终页面，而不只检查 JSON 非空。
- 按表 ID、行边界与单元格值核对表格；检查图注、原图与高亮实际存在。
- 阻断漏项、额外编造单元、正文错序、失效引用、失败提取、错误来源链接和过期审阅摘要。
- 将内容审阅、静态检查、脚本逻辑与浏览器验收分别记录；数字出现不等于数字解释正确。

判定为 `ready`、`ready_with_verification_limits`、`checkpoint` 或 `not_auditable`。演示目前为 `ready_with_verification_limits`：静态检查与脚本状态测试可复现，实际浏览器版面、键盘、打印和断网打开尚未验证。请参阅 [验证范围](docs/verification.md)。

## 开发与测试

Python 3.10+；Node.js 22+ 仅用于前端状态测试。无需 pip/npm 安装。

```sh
python3 -m unittest discover -s academic-paper-annotator/scripts -p 'test_*.py'
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/workbench.test.cjs
```

GitHub Actions 在 Python 3.10、3.12、3.14 上执行检查，并单独运行 Node 测试。远端实际运行结果以 Actions 页面为准。

## 文档与许可

- [数据格式及构建工具](academic-paper-annotator/references/workbench-data.md)
- [发布质量标准](academic-paper-annotator/references/release-quality.md)
- [完整 skill 说明](academic-paper-annotator/SKILL.md)
- [版本变化](CHANGELOG.md)
- [贡献与问题反馈](CONTRIBUTING.md)
- [授权说明](LICENSE) · [第三方材料](THIRD_PARTY.md)

skill 与代码保留创作者“允许分发与改编”的自定义授权，没有改成 MIT。公开演示使用自编材料；历史 ThyGPT 论文案例的方法与核验记录见回归说明，原论文全文与旧试用 ZIP 不在本仓库中。
