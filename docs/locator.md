# 多机型控件定位（Locator）

这个模块解决的是「换一台手机、改一次字体大小，坐标就失效」的问题。它不替换原有流程，而是给项目补上一层**语义定位**能力，让后续改造可以按控件找，而不是按像素点找。

## 定位优先级

```
页面指纹（先确认在哪个页面）
  ↓ 不匹配就拒绝执行
resource-id        ← 最稳，App 开发者给的标识
  ↓
text / content-desc
  ↓
xpath（可选）
  ↓
机型 profile 里的归一化比例   ← 最后的兜底，只在同机型同分辨率下复用
```

前四级只要命中任意一个就返回，**不会**在多级之间盲目重试导致重复点击。

## 页面指纹

每个页面用「任意一个关键节点」确认，例如：

| 页面 | 指纹（任一命中） |
| --- | --- |
| sku | `cn.damai:id/layout_sku` / `project_detail_perform_price_flowlayout` / `sku_panel_dates` |
| confirm | 文本「确认订单 / 提交订单 / 去结算」 |
| login | 文本「登录 / 手机号登录」 |
| detail | `cn.damai:id/btn_buy_view` 或底部购票栏容器 |

> 注意：`btn_buy_view` 在票档页底部也存在，所以指纹表里 **sku 必须排在 detail 前面**，否则票档页会被误判成详情页。`DEFAULT_PAGES` 已按此顺序定义。

## 票档页（SKU）的控件

| spec | 含义 | 依据 |
| --- | --- | --- |
| `sku_session_container` | 场次区域 | `project_detail_perform_flowlayout` |
| `sku_session_card` | 单个场次卡片 | `ll_perform_item`（限定在场次区域内） |
| `sku_price_container` | 票档区域 | `project_detail_perform_price_flowlayout` |
| `sku_price_card` | 单个票档卡片 | `ll_perform_item`（限定在票档区域内） |
| `sku_confirm` | 底部「确定」 | `btn_buy_view` |
| `sku_qty_plus` / `sku_qty_minus` | 数量加减 | `img_jia` / `img_jian` |

场次和票档卡片共用同一个 `ll_perform_item`，所以用 `scope_ids` 限定父容器，避免把场次当成票档。

### 按顺序选第 N 个卡片

```python
loc.tap_index("sku_price_card", 3)   # 从左到右、从上到下第 3 个票档
loc.tap_index("sku_session_card", 2) # 第 2 个场次
```

`tap_index` 按控件位置排序（先上后下、先左后右），与屏幕分辨率无关，替代原来“演前先数坐标”的做法。

## 确认订单页（confirm）

| spec | 含义 | 依据 |
| --- | --- | --- |
| `confirm_submit` | 底部「立即提交」 | 文本匹配（该按钮没有 resource-id） |
| `confirm_attendee_checkbox` | 观演人勾选框 | `cn.damai:id/checkbox` |
| `confirm_attendee_name` | 观演人姓名 | `cn.damai:id/text_name` |

页面指纹用文本「确认购买 / 实名观演人 / 立即提交」，对应 `DmOrderActivity`。

> 注意：`confirm_submit` 只负责“找到按钮”，**不会自动点击**；提交订单仍需人工确认。

定位某个控件时如果指定了 `page`，页面指纹不匹配会直接返回失败，避免在错误页面点中同名按钮。

## 设备 profile

首次在某台手机上运行时，可以执行一次校准：

```bat
check-locator.bat learn
```

它会把当前能解析到的控件中心，换算成相对屏幕的比例（0~1），保存到：

```
profiles/<机型>_<宽>x<高>_<dpi>.json
```

这些文件包含机型、序列号，已经在 `.gitignore` 里排除，不会上传。换手机后没有对应 profile 时，比例兜底自动失效，只走选择器，不会拿旧坐标乱点。

## 自检

正式开抢前先跑一次：

```bat
check-locator.bat
```

输出示例：

```json
{
  "page": "detail",
  "screen": [1080, 2400],
  "profile": "PixelTest_1080x2400_480",
  "specs": {
    "detail_cta": {"source": "resource-id", "point": [540, 2200]},
    "sku_buy": null
  }
}
```

- `page` 为 `null` 说明当前页面既不是详情页也不是选票页，检查手机是否停在了正确页面
- `specs` 里 `source` 是 `resource-id` / `text` / `desc` / `xpath` 最理想；出现 `profile-ratio` 说明选择器失效、在用比例兜底，建议更新 App 后重新校准
- 值为 `null` 表示当前页面没有这个控件，属正常
- `count` 表示匹配到几个，例如票档页 `sku_price_card` 的 `count` 就是当前可见票档数

页面还没被识别（`page: null`）时，先打开该页面再抓一份结构：

```bat
check-locator.bat scan
```

输出会列出当前页面的 `resource_ids`、`clickable_ids`、`texts`、`content_descs`，用来扩充 `DEFAULT_PAGES` / `DEFAULT_SPECS`。

## 代码接入

模块位置：`mobile/locator.py`。

```python
bot = DamaiBot(config)
bot.locator_selfcheck()          # 返回页面 + 各控件解析状态
bot.locator_tap("detail_cta")    # 按语义点击；失败抛 LocatorError
```

底层 API：

```python
from mobile.locator import Locator, ElementSpec

loc = Locator(device)
hit = loc.resolve("detail_cta")   # Hit(rect, source, node) 或 None
loc.tap("detail_cta")
loc.learn()                        # 校准并保存 profile
```

自定义控件：

```python
spec = ElementSpec(
    name="my_button",
    resource_ids=("com.example:id/btn",),
    texts=("立即购买",),
    page="detail",
    fallback_ratio=(0.5, 0.92),
    allow_ratio_fallback=False,   # 不信任比例时关掉兜底
)
loc.tap(spec)
```

## 边界

- 只做「找到并点击」，不改变业务状态机；什么时候点仍由原有流程决定
- 不做 OCR、不做图像模板匹配（离线依赖太重，留给后续按需加）
- 比例兜底只对同机型同分辨率可信；跨机型一律回落到选择器
- 选择器依赖大麦 App 的 `resource-id`，App 大版本更新后需要重新自检

## 为什么这样更稳

| 旧方式 | 新方式 |
| --- | --- |
| 坐标写死或首次运行缓存 | 每次按控件描述解析 |
| 换机型/字体后失效 | 选择器与分辨率无关 |
| 点错页面才发现 | 页面指纹先校验 |
| 失败后继续盲点 | 解析失败即报错，交回上层处理 |
| 无法验证环境 | `check-locator.bat` 提前自检 |
