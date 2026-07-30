# 配置说明

配置文件是 JSONC，可以保留 `//` 注释。真实配置文件被 `.gitignore` 忽略，不要把姓名、设备序列号或具体演出信息提交到 GitHub。

## 两种模式

### 额外选择型

保持：

```jsonc
"preselected_sku": false,
"session_index": 1,
"price_index": 1
```

开售后脚本会按顺序点击场次和票档。请按页面横向从左到右数，第一张可点击卡片是 `1`，第二张是 `2`；如果出现换行，就先数上一行，再数下一行。它们不是日期、金额或票档名称。

如果页面没有场次选择，填：

```jsonc
"session_index": null
```

`price` 只作为配置备注和旧路径辅助信息，极速路径以 `price_index` 为准。票档排序会受售罄状态影响，必须在同一场次下先演练。

### 连点型

保持：

```jsonc
"preselected_sku": true,
"skip_attendee_selection": true,
"skip_quantity_adjustment": true
```

这表示预约阶段已经锁定场次、票档、观演人和数量。开售后不扫描文字、不选择卡片，只对预约后的购买按钮执行快速连点。若观演人或数量没有预选，分别把对应的 `skip_...` 改为 `false`，并先用演练确认页面行为。

## 常改字段

| 字段 | 填法 |
| --- | --- |
| `serial` | 单手机填 `null`；多手机填 `check-device.bat` 显示的序列号 |
| `keyword` | 大麦 App 内能定位演出的关键词 |
| `users` | 已保存的观演人姓名列表，列表长度代表人数 |
| `city` / `date` | 页面上的城市和场次日期原文 |
| `session_index` | 额外选择型的场次编号，横向从左到右数，从 `1` 开始；无场次页为 `null` |
| `price_index` | 额外选择型的票档编号，横向从左到右数，从 `1` 开始 |
| `sell_start_time` | ISO 时间，例如 `2026-08-16T10:18:00+08:00`；不定时填 `null` |
| `if_commit_order` | `false` 演练，`true` 正式提交 |
| `auto_navigate` | 建议 `false`，提前手动停在详情页 |

## 连点首击偏移

`cta_first_tap_delay_ms` 只影响开售后第一击：

```jsonc
"cta_first_tap_delay_ms": 0
```

可比较 `0`、`10`、`20`。三个 `start-preselected*.bat` 演练入口会通过环境变量临时覆盖这个值，不会改写配置文件。正式模式使用正式配置里的值。

## JSONC 修改规则

- 字符串使用双引号。
- 每一项之间保留逗号，最后一项不要多写逗号。
- 时间必须是完整 ISO 格式，时区建议写 `+08:00`。
- 修改后先运行演练；如果提示“配置文件格式错误”，优先检查上一行逗号和引号。
