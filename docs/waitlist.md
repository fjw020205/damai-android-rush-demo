# 候补监控（只读）

每 3–5 秒读取一次手机当前页面，识别「可候补 / 立即购买 / 有票」，命中目标日期和价格时弹本地通知。

## 运行

```powershell
.\.venv\Scripts\python.exe -m mobile.waitlist_watch --config config\waitlist.jsonc
```

先复制模板：

```powershell
copy config\waitlist.jsonc.example config\waitlist.jsonc
```

## 规则

- 只读页面，不点击购买
- **页面不支持下拉刷新**，默认用 `reenter`：返回详情页 → 重新点「立即预订」→ 重选场次，触发新请求
- 必须匹配 `target_date`（页面文本包含）或 SKU 页目标票档可售
- 价格必须 ≤ `target_price`，`allow_lower_price` 控制是否接受更低价
- 遇到排队/限流自动退避（3s → 4.5s → 6.7s … 最多 15s）
- 连续 `stale_limit` 次刷新页面完全无变化 → 强力刷新（`reenter` 模式下改为重进）
- 同一状态 `cooldown_s` 秒内不重复通知

## 通知

Windows 本地弹窗 + 提示音，无网络延迟。

## 下一步

自动导航已接入：命中后调用现有演练流程，进入确认页并停住，**不会提交订单**。

配置：

```jsonc
"auto_navigate": true,
"session_index": 2,
"price_index": 6
```

导航结果会弹本地通知：成功 = 已到确认页；失败 = 未到确认页（附退出码）。

## 自动提交（可选，默认关闭）

```jsonc
"auto_submit": true
```

开启后命中会**真实提交一次订单**（不付款），随后立即停止监控，不重试提交。

风险：

- 生成待支付订单，锁库存，超时自动取消
- 账号可能被风控、限购
- 提交前请确认目标日期/价格/场次/观演人
- 平台条款风险由使用者承担
