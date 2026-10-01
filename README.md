# tradecli

Codex 用的同花顺查询与批量交易插件：一个 npm CLI、一份配套 Skill、一个 Windows 执行端。
借鉴 [easytrader](https://github.com/shidenggui/easytrader) 的 Win32 适配方法，独立管理
运行环境、账户切换、持仓复核、策略计划、模拟及真实账户批量委托和结构化结果。

## 安装

需要 Node.js 22+，Windows 内已有 Python 3.11 和已登录的同花顺交易客户端。
Mac 使用 Parallels 的 `prlctl`，启用 Mac 主目录共享（默认 `\\Mac\Home`，可用
`config init --shared-home <Windows共享路径>` 指定）。Windows 必须处于可交互桌面。

```sh
npm install -g @petercjl/tradecli
tradecli skill install --agent codex
tradecli connections discover --json
tradecli config init --transport parallels --vm '<VM>' --exe 'C:\THS\xiadan.exe' --python 'C:\Python311\python.exe'
tradecli runtime install
tradecli doctor --json
tradecli accounts list --json
tradecli funds get --json
tradecli positions list --json
```

原生 Windows 通道已实现，但尚未完成真实环境验收；设置 `--transport windows`。
依赖安装可指定 `runtime install --wheelhouse <Windows目录>` 从已准备的 wheel 安装。
配置保存在 `TRADECLI_HOME`（默认 `~/.tradecli`）；已有配置不会自动覆盖。
Windows 执行端、独立虚拟环境和私有操作记录保存在用户 LOCALAPPDATA 下的 tradecli 目录。
安装不包含账号、密码、访问授权或自动登录。无需安装整个 easytrader。

## 账户与持仓

账户 ID 来自 `accounts list`。`accounts select --account <id>` 切换并保留当前账户；
查询指定 `--account <id>` 或多账户 `snapshots create --accounts <id,id>` 会在结束后恢复原账户。

`positions list` 返回私有截图和 `capture_id`，由 Codex 查看完整表格，再调用
`positions review --capture <id> --input <review.json>` 校验代码、数量、图片哈希和金额对账。
新持仓读取不复制、不导出表格，避免走复制验证码路径；它不是无人复核的自动结构化接口。
超出窗口的行不能声明完整。截图识别和对账通过才算持仓读取完成。
输入格式见配套 Skill。金额、股数和六位代码均使用字符串。

旧版本的未完成复制可用 `operations status/resume <id>` 恢复原请求；
验证由用户处理，恢复不重新复制。放弃需 `operations abandon <id> --yes`。
所有命令输出 JSON；失败退出码 2。`schema` 和 `capabilities` 提供当前契约。
数据代表客户端显示；保留对账警告和恢复失败。标签重复或切换后资金完全相同会报错。

## 模拟买卖

单笔限价模拟委托提供以下流程：

```sh
tradecli orders prepare --side buy --account <id> --code <六位代码> --price <价格> --quantity <股数>
tradecli orders submit-simulated --draft <draft-id> --account <id>
tradecli orders confirm-simulated --draft <draft-id> --account <id>
tradecli orders result --draft <draft-id>
tradecli orders acknowledge --draft <draft-id> --account <id>
tradecli orders ledger --account <id>
```

`prepare` 只填单并返回截图。提交与确认独立、一次性执行，必须绑定当前模拟账户、
买卖方向、代码、价格、股数和五分钟内的草稿。用户应先核对预览。
`acknowledge` 仅关闭与该草稿已记录回执一致的成功提示；`ledger` 打开当日委托供核对。
结果不明时查询回执和委托，不自动重发。委托受理不等于成交。
`orders inspect/open/clear/quantity-mode` 分别检查、打开表单、显式清空、切换为股数输入。
清空使用 `--yes`，只用于用户授权清理的草稿。
单笔提交命令只接受明确标识为模拟炒股的账户。真实账户使用下文的整批确认流程。
没有撤单、密码输入功能。

## 模拟批量任务

把 1–15 笔委托写入私有 JSON 文件，格式为
`{"orders":[{"side":"buy","code":"600001","price":"1.23","quantity":"100"}]}`。
数量和价格使用字符串；逐笔限价。先验证，再为当前模拟账户准备批次：
买入代码在同一批次内不能重复；已有持仓的卖出可以拆成多笔。

```sh
tradecli batches validate --input <orders.json>
tradecli batches prepare --input <orders.json> --account <模拟账户ID>
tradecli batches run-simulated --batch <返回的batch_id> --account <模拟账户ID> --digest <返回的digest> --yes
tradecli batches status --batch <batch_id>
```

`run-simulated` 在一次 Windows 执行进程内逐笔填单、核对确认框、提交、等待合同编号并清理表单。
每笔点击前记录状态；回执不明立即停批，后续订单保持未执行，整批不可自动重试。
成功回执只证明委托受理，不证明成交。执行后用 `orders ledger --account <id>` 核对当日委托。
详见 [批量执行契约](docs/batch-execution.md)。

市价委托计划只写方向、代码和股数：

```json
{"orders":[{"side":"buy","code":"600221","quantity":"100"},{"side":"sell","code":"300359","quantity":"100"}]}
```

先运行 `batches validate-market --input <orders.json>` 和
`batches prepare-market --input <orders.json> --account <模拟账户ID>`。
准备阶段校验清单并核对账户；用户确认账户、买卖方向、代码和股数。
用户确认后用 `batches run-simulated` 执行。Windows 执行端逐笔打开“市价委托”页面，
输入股票代码，读取该股票可用的市价策略和同花顺自动显示的参考价格，再输入股数。
实际策略随交易所和账户而异；如果股票不支持市价委托、字段变化或回执不明，整批停下。
真实账户使用 `batches prepare-real-market` 和 `batches run-real`，绑定账户类型与 ID。
执行前通过下面的策略计划流程完成持仓复核和整表确认。界面“最新价格”是参考显示，
市价委托的成交价格与成交股数以交易所回报为准。

## 策略计划与整批确认

配套 Skill 接受指定账户，默认当前账户，以及逐笔买卖股数或目标持股数。先读取并复核该账户
全部持仓，再把策略写为私有 JSON 文件，例如：

```json
{"targets":[{"code":"300359","quantity":"300"},{"code":"600221","name":"海航控股","quantity":"100"}]}
```

已持有股票的名称来自持仓复核；新买入股票需提供核实过的名称。运行：

```sh
tradecli batches plan-market --strategy <strategy.json> --review <positions-review.json> --account <账户ID>
```

返回每笔的代码、名称、当前股数、方向、买卖股数和计划后股数，以及可执行的 `orders_path`。
Skill 先用表格确认完整清单和账户，再准备并执行匹配的市价委托批次。
完成后按合同编号核对当日委托，并区分委托受理、实际成交、结果不明和未尝试的订单。
计划后股数只有在相应订单成交后才成为实际持股数。真实账户流程已通过自动化单元测试，
此前普通买卖入口在真实账户走过一次确认与提交路径；交易端以系统初始化前备份状态
拒绝该笔委托，未取得合同编号，后续卖单未执行。市价委托的提交、成功受理及成交路径
仍需在适合的交易时段实测。

## 聚宽模拟盘同步

`sync plan --strategy-name <模拟交易名称> --review <持仓复核文件> --account <账户ID>`
通过已安装的 `jqcli` 读取指定模拟交易的最新持仓，按股票代码集合生成卖出清单及待买入清单。
卖出单独成批执行。所有卖单在当日委托中核实为全额成交后，重新读取持仓和可用资金，
用 `sync quotes --plan <计划文件> --account <账户ID>` 从同花顺市价买入页面读取参考价格，
再用 `sync allocate --plan <计划文件> --review <新持仓复核文件> --fills <成交复核文件> --quotes <报价文件> --sell-batch <卖出批次ID>`
按剩余可用资金等额计算买入股数。买入股数取 100 股的整数倍，并留出价格变化及费用余量。
两阶段均须展示计划并由用户确认；委托受理不等于成交。同步计划与复核文件保存在本地私有目录。
市价参考价格只用于估算股数，实际成交价格由市场决定。

## 范围与维护

仅提供 Codex Skill；其源文件随 npm 包维护，安装位置为受管理链接。
`skill source/status/install/update` 查看和管理 Skill；用户已有同名 Skill 会保留并报错。
`update check` 检查更新；`update install --yes` 更新 npm 包。

```sh
npm ci
npm test
npm run check
```

发布使用 npm-release-kit、GitHub Actions 和 npm Trusted Publishing。
兼容性和测试边界见 [开发验收记录](docs/validation.md)。
MIT；上游声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
