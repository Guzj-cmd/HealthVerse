# Satori bridge for HealthVerse

这个侧车把 HealthVerse 的场景上下文映射为 Satori 风格的 `Belief -> Desire -> Intention` 计划，并保留 Satori 的结构化步骤、视觉检查点和对象列表。

## 实际复用范围

- 上游：[`VIDA-NYU/satori-assistance`](https://github.com/VIDA-NYU/satori-assistance)
- 核验提交：`dd09f303043cd90a9e486518bf9878f301f14677`
- 许可证：MIT，全文见 `LICENSE-SATORI`
- 直接复用并适配：`pipelines/task/task_planner_pipeline.py` 中的 XML 任务计划解析器，以及 `Step / Checkpoint / StepStatusCheckPrompts / Objects` 数据契约
- HealthVerse 新增：`Belief / Desire / Intention` 输入映射、打断成本策略、置信度阈值、纠正与记忆写入状态

没有复制 Satori 的 HoloLens、`ptgctl`、OpenCV、PyTorch 或 GPT-4V 运行栈。那些模块依赖专用视觉流与设备，无法作为 Java WAR 的轻量依赖运行。

## 运行

Python 3.9+，无第三方依赖。

```powershell
python .\smoke_test.py
python .\bridge.py --input .\sample_request.json
.\start.ps1
```

HTTP 接口：

```text
GET  http://127.0.0.1:8788/health
POST http://127.0.0.1:8788/plan
```

Java 应用可以通过环境变量 `SATORI_BRIDGE_URL=http://127.0.0.1:8788/plan` 启用这一可选规划层；未启动侧车时，主 Agent 的本地规则与远程模型回退仍可工作。

## 输出边界

bridge 只生成任务计划与可撤销建议，不执行现实空间操作，不写入长期记忆，也不作医疗诊断。`memory_write` 始终保持为 `pending_user_confirmation`，直到用户在主应用中确认。
