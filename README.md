# 浙江选调院校 · 硕士预推免 DDL

查看 2026 年秋季报名、2027 级入学的计算机及相关方向硕士预推免信息，按报名状态和截止时间筛选，追踪官方公告新增与修订。

[访问网页](https://adamskyhhh-byte.github.io/zhejiang-tuimian-ddl/) · [公开源码](https://github.com/adamskyhhh-byte/zhejiang-tuimian-ddl) · [每日更新记录](https://github.com/adamskyhhh-byte/zhejiang-tuimian-ddl/actions/workflows/update-and-deploy.yml)

学校范围为浙江 2026 年度常规选调与定向紧缺专业院校名单并集，共 **68 个院校／机构**。国科大相关研究所按培养单位列出。名单归属只用于确定收录范围，不代表某校所有专业均符合选调岗位条件。

## 使用

- 首页默认按截止时间展示正在报名的项目，可切换 3 天内、7 天内、今日新增／变更。
- 筛选学校、地区、学科、核心／交叉相关、学硕／专硕、名单类别和状态；筛选 URL 可以分享。
- 支持 TOP2、港三、华五、C9、985、211、双非、四非、研究院、联培标签，以及线上／线下／混合／未核验考核形式；同组多选取并集，数字为项目数。[类别口径](docs/filter-categories.md)
- 收藏保存在当前浏览器，换设备或清除浏览器数据后不会同步。
- 列表、月历与学校覆盖页面提供不同入口；详情保留报名与材料截止、官方原文和修改记录。
- 只收硕士预推免及同阶段后续批次、延期、更正；不收夏令营、正式推免、仅直博公告。

**请检查具体项目的原文与来源新鲜度。** 日期未给时刻时不会显示伪精确倒计时；“未发现公告”“开放时间未知”“抓取失败”和“已截止”是不同状态。全部 68 个机构进入目录不等于其所有学院已经完成盘点；当前缺口在覆盖页面和 [盘点记录](docs/coverage.md) 中列明。

## 本地运行

需要 Node.js 22+、pnpm 10 和 uv。依赖通过 `pnpm-lock.yaml` 和 `uv.lock` 固定。

```sh
pnpm install --frozen-lockfile
uv sync --locked --all-extras
pnpm dev
```

Vite 的本地地址以终端输出为准。已有 `public/data/catalog.json` 可直接展示，不要求先联网抓取。

```sh
# 全部官方来源增量更新并生成静态快照
uv run python -m tuimian crawl --root .

# 仅检查指定来源，便于修复适配器
uv run python -m tuimian crawl --root . --source SOURCE_ID

# 离线从持久状态、初始记录和人工修正导出，不伪造联网检查时间
uv run python -m tuimian export --root .

# 校验模型和实体引用
uv run python -m tuimian validate --root .
```

普通网页使用 HTTPX，PDF 使用 pypdf。只有配置 `render: true` 的动态公开页面需要安装浏览器：

```sh
uv run playwright install chromium
```

## 验证

```sh
uv run pytest tests/python
pnpm check
pnpm test
pnpm build
uv run playwright install chromium
uv run pytest tests/browser
```

浏览器测试在隔离的本地服务与测试数据上验证交互，真实数据核验另外运行，避免网络波动掩盖解析回归。

## 数据和自动更新

| 内容 | 位置 |
| --- | --- |
| 学校名单、资格限制 | `data/schools.json` |
| 名单年、报名季与入学年 | `data/settings.json` |
| 学院／研究所盘点 | `data/units.json` |
| 官方栏目与公告适配配置 | `data/sources.json` |
| 带官方证据的初始线索 | `data/seeds.json` |
| 人工纠错 | `data/overrides.json` |
| 院系别名与官方依据 | `data/unit-aliases.json` |
| 误收排除与重复项目合并 | `data/review-decisions.json` |
| 持久 ID、抓取状态、公告历史 | `data/state.json` |
| 前端公开静态快照 | `public/data/catalog.json` |

GitHub Actions 每天 **北京时间 07:23** 运行。一个工作流完成测试、抓取、验证、构建、保存状态和 Pages 发布，部分来源失败保留其上次数据。每个来源超过 36 小时未成功检查会单独提示；一次总体工作流成功不能刷新失败来源的核验时间。

Actions 的定时触发可能延迟或被平台暂停。可以在 **Actions → Update and deploy → Run workflow** 手动补跑；关闭 `crawl` 仅重新发布已有快照。没有仓库活动 60 天的公开项目可能停用 schedule，需要在 Actions 页面重新启用。[GitHub 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 部署和维护

使用 GitHub Pages 的 Actions 发布源，默认分支为 `master`。网页构建自动读取 Pages 子路径；无需服务器、AI API key 或自定义域名。

新仓库首次部署需在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。工作流使用最小分任务权限，并固定外部 Action 提交。仓库若启用禁止机器人直接提交的保护规则，需提供专门的数据更新分支／合并流程后再启用抓取写回。

详细操作见 [来源配置、人工纠错与年度切换](docs/maintenance.md)；数据模型见 [数据契约](plan/data-contract.md)，实际覆盖及测试结果见 [验收记录](docs/verification.md)。

## 来源与许可

- [浙江 2026 年度官方选调公告及附件](https://xds.ecnu.edu.cn/68/b9/c51123a747705/page.psp)
- 前端基于 [CS-BAOYAN-DDL](https://github.com/CS-BAOYAN/CS-BAOYAN-DDL) 修改，保留 MIT 许可与 Axi404 版权。
- 高校通知只保存结构化事实和必要短证据；完整通知以详情中的官方链接为准。

完整说明见 [版权归属](docs/attribution.md) 与 [LICENSE](LICENSE)。
