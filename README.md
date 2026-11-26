# HealthVerse：个人健康 AI 工作台

团队成员从[协作开发与联调对接文档](docs/TEAM-HANDOFF.md)开始，可以找到本地启动步骤、前后端接口、模型入口和联调验收清单。

HealthVerse 是一个面向现实空间的交互设计课程原型。系统将视觉观察、用户任务、环境约束、反事实方案和短时自我实验组织成可纠正、可撤销的协同闭环。AI 被设计为协作者，而不是自动诊断或替用户作决定的裁判。

## 真实运行路径

1. 启用摄像头或导入本地视频；浏览器用 MediaPipe Pose、训练后的姿态分类器和 EfficientDet-Lite0 处理真实画面；
2. 查看姿态、工作区物体、人—物二维关系和按真实帧时间累计的时序证据；
3. 纠正 AI、说明任务需要，或暂停本次提醒；证据约束 Agent 不得虚构厘米、深度或长期健康结论；
4. 在“个人身体模型”中采集真实关键点并只保存归一化比例；
5. 在“环境协同设计”中比较可撤销方案，再以独立基线阶段和方案阶段做短时验证；
6. 两个阶段各达到最小姿态证据门槛后，用户确认的结果才可进入可见、可停用、可删除的个人记忆；
7. 在隐私控制中查看真实联邦协调器状态，并区分加入意愿、本机联邦测试和已验证多设备轮次。

页面占位插图和课程人物角色会明确标注“示意/虚构”；摄像头、导入视频、关键点、目标框、时序、校准和用户实验记录来自当前真实会话。所有输出均为非医疗辅助信息。

## 当前模型与冻结评估

| 能力 | 数据与切分 | 冻结结果 | 网页状态 |
|---|---|---:|---|
| 上身姿态 | MultiPosture，按受试者隔离；3 名未见受试者测试 | Accuracy 0.9874，Macro-F1 0.9813 | 已导出并在浏览器接入 |
| 下身姿态 | MultiPosture，同一受试者隔离测试 | Accuracy 0.9347，Macro-F1 0.9598 | 已导出并在浏览器接入 |
| 跨场景关系 | Charades 官方训练分区，留场景且移除重叠参与者 | Macro-mAP 0.3695；相对基线 +0.1080 | 作为泛化证据；不替代浏览器目标检测 |
| 低打扰证据门 | BEHAVE，参与者留一 | Accuracy 0.9574，Macro-F1 0.8220 | 用于“无动作/请求确认”安全边界 |
| 活动建议策略 | HeartSteps V1，37 人、6112 决策点、5 折参与者隔离 | DR uplift 0.1092，95% cluster CI [0.0046, 0.2134] | 研究模块；不冒充人体工学建议 |
| 联邦姿态模型 | MultiPosture 真实受试者客户端，本机 FedAvg | Accuracy 0.9271，Macro-F1 0.9117 | 联邦客户端/协调端可联网运行；多设备需真实设备验证 |

100% 是优化方向，不是预设结论。冻结测试集不得反复用于调参；当前错误与限制保留在各运行目录的 `metrics.json`、`model_card.md` 和迭代记录中。

## 项目结构

```text
HealthVerse/
├─ pom.xml
├─ README.md
├─ SUBMISSION_GUIDE.md
├─ IMPLEMENTATION_STATUS.md            当前功能、证据与限制
├─ database/                         持久化扩展说明
├─ machine-learning/                 真实数据训练、评估、联邦与浏览器导出
├─ mobile/HealthVerseCompanion/      移动端扩展占位
├─ samples/                          Agent 请求示例
├─ scripts/                          本地烟雾测试与 Satori 规划桥
└─ src/
   ├─ main/
   │  ├─ java/com/example/healthverse/
   │  │  ├─ controller/              Servlet 接口
   │  │  ├─ service/                 Agent 调用与本地回退
   │  │  ├─ config/                  安全配置读取
   │  │  ├─ filter/                  可选 Web 过滤器
   │  │  ├─ pojo/                    请求与响应对象
   │  │  └─ util/                    通用工具
   │  ├─ resources/                  安全默认配置与本机模板
   │  └─ webapp/
   │     ├─ public/index.jsp         应用入口
   │     ├─ assets/css/              页面样式
   │     ├─ assets/js/               页面交互
   │     └─ WEB-INF/web.xml          Servlet 映射
   └─ test/                          单元测试
```

该层级与用户提供的 Java Servlet/JSP Maven WAR 提交包保持同类结构；未实现的数据库与移动端能力只保留明确标注的扩展目录，不以空壳冒充已完成功能。

## 环境要求

- JDK 8 或兼容版本；
- Maven 3.8+，或项目随附的 Maven Wrapper；
- Tomcat 9。
- 支持 WebAssembly/WebGL 的现代浏览器；首次加载 MediaPipe 与 EfficientDet 模型时需要网络。

## Agent 配置

不配置远程模型时，后端会使用可解释的本地回退建议，网页仍可完整演示。

推荐在启动 Tomcat 的同一环境中设置：

```powershell
$env:AI_PROVIDER = "anthropic"
$env:AI_API_URL = "https://your-compatible-gateway.example/v1/messages"
$env:AI_API_KEY = "仅保存在本机的令牌"
$env:AI_MODEL = "模型名称"
```

也可以复制 `src/main/resources/ai.local.properties.example` 为 `ai.local.properties`，只在本机填写配置。`*.local.properties` 已被 Git 忽略并从 WAR 排除。真实令牌不能写入 README、示例文件、前端 JavaScript 或版本库。

本地 Claude 兼容配置存在时，后端可在未显式设置 `AI_*` 的情况下尝试读取；仍以显式环境变量为最高优先级。启动日志和接口响应不会输出令牌。

### Satori 论文代码桥接（可选）

提交包实际包含 Satori 的 MIT 许可 XML 任务计划解析器及 HealthVerse 适配层，位于 `scripts/satori-bridge/`。先启动侧车，再将其地址交给 Java Agent：

```powershell
.\scripts\satori-bridge\start.ps1
$env:SATORI_BRIDGE_URL = "http://127.0.0.1:8788/plan"
```

Java 后端会把侧车返回的 `Belief / Desire / Intention`、结构化步骤和检查点作为远程模型的附加上下文。未启动侧车时自动跳过，不影响主 Agent；本地回环地址也不会经过模型网关代理。复用范围、固定的上游提交和许可证见 `scripts/satori-bridge/README.md`、`NOTICE.md` 与 `LICENSE-SATORI`。

## 联邦学习运行与网页状态

协调器与客户端位于 `machine-learning/federated/`。不同设备使用同一 TLS 协调器和独立本地数据；原始视频、图像、关键点和特征不会进入协调器。网页只读取协调器的非敏感 `/status`：

```powershell
$env:HV_FED_SECRET = "替换为随机长密钥"
python machine-learning/federated/coordinator.py --host 0.0.0.0 --port 8787 `
  --secret $env:HV_FED_SECRET --tls-cert server.crt --tls-key server.key --min-clients 2
$env:HV_FED_STATUS_URL = "https://coordinator.example:8787"
```

每台设备运行 `client.py`。只有同一轮收到至少两个不同设备指纹后，协调器才返回 `multi_device_federated_run`。同一电脑上的多个进程始终保持 `local_federated_test`。当前协议不把 HMAC/TLS 误称为安全聚合或差分隐私；完整边界见 `machine-learning/federated/README.md`。

## 构建与部署

Windows：

```bat
mvnw.cmd clean test package
```

Linux / macOS：

```bash
./mvnw clean test package
```

也可使用已安装的 Maven：

```bash
mvn clean test package
```

生成的 WAR 位于：

```text
target/HealthVerse_Submission.war
```

将 WAR 复制到 Tomcat 9 的 `webapps` 目录。默认访问地址通常为：

```text
http://localhost:8080/HealthVerse_Submission/
```

部署后可运行：

```powershell
.\scripts\agent-smoke.ps1
```

## 设计与数据边界

- 不把短期姿态变化表述为长期健康收益；
- 每条主动建议说明“为什么现在提醒”；
- 低置信度时先求证，不自动执行空间调整；
- 用户可以纠正、拒绝、暂停、撤销和删除；
- Agent 输入限制长度，远程接口失败时降级为本地规则；
- 摄像头或导入视频在当前浏览器处理；停止输入会释放媒体轨道与 Blob URL；
- 个人校准只在用户确认后保存归一化比例，不保存原始视频或关键点序列；
- 证据不足的短时实验只作为审计记录，不进入个性化偏好记忆；
- 单目二维画面不能提供真实厘米、深度或医疗结论；
- 课程人物角色是明确标注的虚构设计材料，不作为模型输入或真实用户数据。
