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
- 必须匹配 `target_date`（页面文本包含）
- 价格必须 ≤ `target_price`，`allow_lower_price` 控制是否接受更低价
- 连续 `refresh_every_s` 秒无变化才下拉刷新，0 表示不刷新
- 同一状态 `cooldown_s` 秒内不重复通知

## 通知

Windows 本地弹窗 + 提示音，无网络延迟。

## 下一步

自动导航到确认页（停在“立即提交”前）尚未接入。
