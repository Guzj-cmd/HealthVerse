# HealthVerse 实现与迭代记录

## 当前横向闭环

| 环节 | 当前实现 | 验证证据 |
|---|---|---|
| 真实输入 | `getUserMedia` 摄像头、本地视频导入、停止并释放媒体 | Playwright 以 D 盘 Charades MP4 实测 |
| 人体 | MediaPipe Pose 33 点 + MultiPosture 训练分类器 | 浏览器真实画面；受试者隔离测试指标 |
| 环境 | EfficientDet-Lite0 VIDEO 模式、支持工作区 COCO 类别 | 浏览器真实检测调用与覆盖框 |
| 人—物—空间 | 眼—屏二维对齐、座椅接触、手—物相对触达 | `test_spatial_inference.mjs` 11 项断言 |
| 时序行为 | 使用视频帧时间累计姿态持续时长，5 秒低打扰门槛 | 浏览器状态与证据面板 |
| Agent | 真实空间证据进入 `/api/agent`；未知事实必须标未知 | 系统提示与本地回退；不允许虚构厘米/诊断 |
| 个人校准 | 三次真实关键点采集；只保存归一化派生量 | localStorage 实测不含 landmarks/video |
| 短时实验 | 3 分钟基线、6 分钟方案、用户评分、可提前结束 | 两阶段独立快照与真实帧时间；每阶段最少 5 秒证据门槛 |
| 个人记忆 | 用户确认后保存，可停用、删除、导出 | localStorage 实测；证据不足记录不进入偏好 |
| 联邦隐私 | HMAC/TLS 客户端—协调端、裁剪、真实状态探针 | 2 个真实受试者网络客户端完成一轮；同机仅 1 设备指纹 |

## 关键迭代

1. **静态原型**：手绘论文图风格和七页流程，但含固定姿态、固定记忆与演示数字。
2. **真实姿态模型**：MultiPosture 受试者隔离训练、冻结测试、浏览器模型导出；移除“规则生成姿态”。
3. **场景与策略扩展**：BEHAVE/Charades/Edinburgh/HeartSteps 真实数据实验，失败或未达门槛的模型不进入网页能力声明。
4. **真实空间闭环**：加入 EfficientDet、二维关系、时序证据、摄像头/视频输入和证据约束 Agent。
5. **个人验证闭环**：校准、两阶段短时实验、用户评分、可控记忆；删除所有未输入前的固定健康结论。
6. **联邦运行闭环**：网页后端读取真实协调器状态；同机两个客户端聚合后仍标记 `local_federated_test`，不伪造多设备。
7. **失败驱动修正**：浏览器测试发现 JSP 中文编码、`.mjs` MIME、模型根路径和证据为空仍可保存等问题，均加入回归修复。

## 2026-11-26 本机验证

- `node --check src/main/webapp/assets/js/healthverse.js`：通过。
- `node machine-learning/browser-export/test_spatial_inference.mjs`：11 项断言通过。
- `mvnw.cmd test`：Java 联邦状态测试 2/2 通过。
- `python -m unittest discover -s machine-learning/federated/tests -v`：8/8 通过。
- Playwright：初始页 0 错误；真实视频成功产生 33 点覆盖、训练姿态模型加载和物体检测启动。
- 联邦网络：`subject-1` 与 `subject-2` 的真实 MultiPosture 数据完成一轮参数聚合；原始数据上传为 false；2 客户端但 1 设备指纹，因此运行类型保持本机测试。

## 修改前后截图

- 修改前静态原型：`docs/screenshots/before-static-prototype.jpg`
- 修改后真实视频与姿态/空间推理：`docs/screenshots/after-live-video.png`
- 修改后隐私与联邦运行状态：`docs/screenshots/after-privacy-federated.png`

截图只用于展示可见运行状态；模型指标、网络聚合与隐私边界分别以冻结评估文件、协调器状态和自动化测试为准。

## 仍需外部条件才能证明的事项

- 真实多设备联邦验证需要至少两台独立设备连接同一 TLS 协调器。代码会根据不同匿名设备指纹自动升级状态，但本机不能作为多设备证据。
- 摄像头到关键点检测器的端到端覆盖率需要新的、经同意采集的真实摄像头基准；公开 MultiPosture 只提供关键点。
- 所有模型均为研究/课程原型，不是医疗器械或长期健康效果证据。
