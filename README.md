# tradecli

Codex 用的同花顺只读查询插件：一个 npm CLI、一份配套 Skill、一个 Windows 执行端。
借鉴 [easytrader](https://github.com/shidenggui/easytrader) 的 Win32 适配方法，独立管理
运行环境、账户查询、验证码恢复和结构化结果。

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

## 查询和恢复

资金和持仓查询要求客户端处于资金股票页面；账户 ID 来自 `accounts list`。
指定 `--account <id>` 查询其他账户；`snapshots create --accounts <id,id>` 依次读取。
完成后恢复原账户。持仓读取会改变 Windows 剪贴板和表格选择。

遇到验证时返回 `operation_id`；用户手动完成后执行：

```sh
tradecli operations status <operation-id> --json
tradecli operations resume <operation-id> --json
```

恢复读取原请求，不重新发送复制。请求有效期五分钟，账户、进程、窗口和剪贴板
来源必须匹配。中断记录会阻止新查询；放弃时使用
`operations abandon <operation-id> --yes`，并人工检查当前界面和账户。
放弃只改变操作状态，不关闭弹窗或恢复账户。

所有命令输出 JSON；`ok:false` 退出码为 2。`schema` 和 `capabilities` 提供当前契约。
金额为十进制字符串；证券代码保留前导零。多账户快照为顺序采集。
数据代表客户端显示，不能证明与券商服务器实时同步。对账警告和恢复失败均会保留。
标签相同的账户或切换后资金完全相同的情况会保守报错。

## 范围与维护

0.1 系列提供账户、资金和持仓查询，无买卖、撤单、新股申购或密码输入命令。
界面自动操作并不等于模拟资金交易。验证码由用户处理；不承诺无人值守。
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
