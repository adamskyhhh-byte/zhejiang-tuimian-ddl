# 来源维护与数据纠错

## 新增学院或研究所

1. 在 `data/units.json` 登记培养单位，引用已有 `schoolId`。国科大相关研究所应归入国科大，不再新增一所名单外学校。
2. 填写真实官方 `directoryUrl`、招生栏目 `admissionUrl`、学科方向、核心／交叉关联和盘点备注。未完成核验时使用 `pending`，不要猜测“没有招生”。
3. 在 `data/sources.json` 增加官方招生列表来源和已知详情来源。稳定 `id` 一经发布尽量保留；网页改版可以更新 URL。
4. 运行指定来源抓取，检查提取结果与原文，再运行全部验证。

来源配置除了公开来源字段，还支持：

| 字段 | 用途 |
| --- | --- |
| `kind` | `listing`、`notice` 或 `pdf` |
| `adapter` | 普通 HTML 使用 `html`；浙江大学公开报名 API 使用 `zju_admissions`；国防科大学院发文、详情与附件使用 `nudt_admissions` |
| `unitId` / `unitIds` | 对应一个或多个招生单位 |
| `contentSelector` | 官方页正文 CSS selector |
| `linkSelector` | 列表详情链接 selector，默认 `a[href]` |
| `includePatterns` / `excludePatterns` | 限制候选标题和 URL，避免本校推荐资格、录取公示等误命中 |
| `scope` | 学院段落正则；一页多个学院时使用单位 ID 到正则的映射 |
| `allowedHosts` | 明确允许的官方链接主机名 |
| `render` | 仅确有必要的公开动态页设置 `true` |
| `identityKey` | 已人工确认同项目／批次的跨公告修订关联 |
| `noticeScope` | `auto` 自动识别共享校级栏目，`school` 仅使用明确对应单位的报名段落，`unit` 用于已核实的学院专属通知 |
| `batch` | 明确批次名，不将第二批当第一批延期 |
| `forceAfterDays` | 定期忽略条件缓存重新下载，默认 7 天 |
| `maxPages` | 列表翻页上限，默认 3 页；按实际栏目调整 |
| `enabled` | 是否进行抓取；禁用后仍保留过去的数据 |
| `preAdmissionEvidence` | 仅对人工逐页确认的公告指定预报名阶段证据正则；长篇学院介绍后才出现申请流程时使用。不能仅凭“推免”二字对整个学校栏目放行 |

不得为方便解析把校级统一日期套用到所有学院。PDF 和附件也是证据来源，材料截止、面试日期、直博专用截止都不得作为硕士报名截止。

## 人工修正

院系改名或同院别名在 `data/unit-aliases.json` 保留原 ID、规范 ID 和官方依据。已经确认误收的项目在 `data/review-decisions.json` 的 `excludedOpportunities` 中按 ID 记录 `reason` 与 `evidenceUrls`；重复项目通过 `opportunityAliases` 指向保留的项目 ID。排除和合并只影响公开快照，原始状态与历史继续保存在 Git，不能把误收公告标成“取消招生”。

编辑 `data/overrides.json`，以项目稳定 ID 为键，写明 `reason` 和需要覆盖的字段。例如以下仅展示格式，不是实际招生数据：

```json
{
  "实际项目稳定ID": {
    "reason": "根据详情所列官方更正通知核对硕士报名截止，记录更正通知链接。",
    "applicationEnd": {
      "value": "2026-09-15",
      "precision": "date",
      "raw": "报名截止至2026年9月15日，原文未给具体时刻",
      "sourceId": "实际官方来源ID"
    },
    "verification": "verified"
  }
}
```

只写日期就使用 `date`；精确时间必须包含时区，例如 `2026-09-15T17:00:00+08:00`。人工修正不会被日后抓取静默覆盖；若官方信息发生实质变化，结合变更与冲突提示复核人工覆盖值，不能长期锁住一个已经失效的截止时间。

已逐页确认当前正文，但自动解析仍有缺口时，override 可保存 `reviewedSourceHashes`（来源 ID 到已核对正文 hash 的映射）及 `reviewedAutomaticHash`（`tuimian.storage.review_signature(state["opportunities"][id])`）。必须包含时间依据、正文父页与附件，完成核对后才能设置，不能为清除冲突批量刷新这些值。自动采集值/来源集合或附件核验版本变化时，旧人工值仍保留，但核验状态转为冲突。

HTML 支持正文 PDF 播放器（含 PDF.js `file` 参数）；扫描 PDF 保存二进制 hash，自动无法提取时需目视核对。父页移除的附件记录在 `retiredSources`，旧附件仍可下载也不能恢复自动核验。`reviewRevision` 是持久核验版本，不能手动归零。仅公布“建议”时间不能作为硬性截止。

网页在报名截止未知但材料截止已确认时，列表、详情和月历展示“材料提交截止”；3/7 天提醒也包含这些材料时限。此显示不推定报名开放或结束。其他无法确认日期的记录应写出原因，不能统一写“尚未开始”。

修改后执行：

人工确认考核形式后可在对应 override 写入 `assessmentMode: "online"`、`"offline"` 或 `"hybrid"`；缺少明确证据保留 `"unknown"`。只有明确硕士联合培养项目才写 `programTags: ["joint"]`，并在 `reason` 写清适用专业、方向与官方链接；这些字段与报名时间的核验状态独立。

```sh
uv run python -m tuimian export --root .
uv run python -m tuimian validate --root .
pnpm check
pnpm test
pnpm build
```

## 数据新鲜度和故障恢复

- `lastAttemptAt` 是尝试时间；`lastSuccessAt` 是来源成功读取时间；`lastParsedAt` 是成功提取内容时间。不能互相替代。
- 网站返回错误、验证码、空正文或扫描件无法识别时保留历史有效记录，并显示失败原因。
- `data/state.json` 是运行所需的持久状态，不是可随意删除的缓存。包含项目 ID、已发现通知和历史；恢复旧版本前先复制到 `temp` 并核对差异。
- 发布失败时 Pages 保持前一次可用版本。修复后手动运行工作流；不要为了“绿色成功”隐藏错误或清空项目。
- 若全部来源检查失败，已校验的失败状态会保存到 Git，但工作流停止发布，网页仍显示前一次可用快照；最新失败原因需在 Actions 运行摘要中查看。部分来源失败时可以发布保留历史数据的新快照。
- 仅需要重建网页时，手动工作流关闭 `crawl`，无需重复请求高校站点。
- 来源暂不可达时可暂时停用该 source，但应保留覆盖备注，不能改成“未发现公告”。

## 新招生年度

1. 将当前季数据与状态归档到一个明确年度目录或 Git release，保留历史 ID 和快照；先备份，再切换。
2. 选调名单年度与入学年度独立更新。只有新的官方名单及附件经过核对后才更新学校集合，并记录增删和专业限定变化。
3. 更新采集器年度配置、源配置中的年份条件、种子记录和网页默认年度；运行测试，确保旧通知不会进入新季。
4. 首次全量盘点和官方来源核验完成后再发布新季；不要仅将去年所有日期年份加一。

当前版本有意只发布 2026 秋季／2027 级，年度切换需要维护者完成上述变更和验证，不会在元旦自动滚动。
