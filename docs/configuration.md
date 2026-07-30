# 配置说明

先复制对应模板，其他内容保持不动。脚本默认要求你手动停在大麦详情页，所以不需要填写演出名称、城市、日期或票档文字。

只有你主动把 `auto_navigate` 改成 `true`，才需要另外补搜索用的演出信息。

## 额外选择型

使用 `rehearsal.jsonc.example` 和 `formal.jsonc.example`。

只改：

1. `sell_start_time`：开售时间，例如 `2026-08-16T10:18:00+08:00`。
2. `session_index`：场次编号；按页面横向从左到右数，第一项填 `1`。没有场次页填 `null`。
3. `price_index`：票档编号；按页面横向从左到右数，第一项填 `1`。

如果 App 已经预选观演人，保持模板中的 `skip_attendee_selection: true` 和 `users: []`。没有预选观演人时，改成 `false`，再把姓名放进 `users`。

## 连点型

使用 `preselected-rehearsal.jsonc.example` 和 `preselected-formal.jsonc.example`。

通常只改 `sell_start_time`。预约已经锁定场次、票档、观演人和数量，保持：

```jsonc
"preselected_sku": true,
"skip_attendee_selection": true,
"skip_quantity_adjustment": true
```

`session_index`、`price_index` 在连点型中不会参与开售后的点击。

## 三个连点时间

连点型的三个演练入口分别对应 T0、T0+10ms、T0+20ms。手机页面不会完整暴露购票状态，当前版本无法保证用代码及时读到“预约”变成“购票”的瞬间，所以先提供三档时间方案。后续版本会继续实验间隔参数；使用者只需比较哪个入口能稳定进入购票页。

正式配置中的 `cta_first_tap_delay_ms` 填选中的 `0`、`10` 或 `20`。演练入口会临时覆盖这个值，不会改写文件。

## 只需要记住

- 一台手机：`serial` 不动。
- 定时抢票：改 `sell_start_time`。
- 额外选择型：再改两个编号，横向从左到右、从 `1` 开始。
- 正式运行：使用 `formal` 模板和正式 `.bat`，只提交订单，不支付。
