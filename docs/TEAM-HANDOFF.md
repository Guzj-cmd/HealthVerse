# HealthVerse 协作开发与联调对接

这份文档面向共同维护青少年学习空间工作台的成员。当前页面包括实时空间感知、个人身体模型、环境协同设计、健康自我实验、个人健康记忆和课程设计档案。Health Agent 在实时空间感知页右侧。独立的架构图页面已移除。

## 从克隆到第一次请求

需要 JDK 8 或兼容版本、Tomcat 9 和现代浏览器。以下 PowerShell 命令在仓库根目录执行，假定 `CATALINA_HOME` 已指向本机 Tomcat 9，开发依赖缓存放在 D 盘。

```powershell
git clone https://github.com/Guzj-cmd/HealthVerse.git
cd HealthVerse
.\mvnw.cmd "-Dmaven.repo.local=D:\CodexData\HealthVerse\m2" package
if ($LASTEXITCODE -ne 0) { throw "构建失败，请先检查 Maven 输出" }
Copy-Item target\HealthVerse_Submission.war (Join-Path $env:CATALINA_HOME 'webapps') -Force
# Tomcat 尚未运行时执行
& (Join-Path $env:CATALINA_HOME 'bin\startup.bat')
```

等待部署完成，访问 [工作台](http://localhost:8080/HealthVerse_Submission/public/index.jsp)。应用默认上下文为 `/HealthVerse_Submission`，若修改 WAR 名称或端口，同时修改联调地址。首次启用摄像头或导入视频时，浏览器需要能访问视觉运行库和模型下载地址。摄像头需要授权，远程访问请使用 HTTPS。

## 改一个功能，需要和谁对接

以下按工作内容分工，具体负责人由团队认领。提交改动时把受影响的接口、资源和验收结果交给表中相邻模块的同伴。

| 工作内容 | 代码入口 | 联调约定 |
| --- | --- | --- |
| 页面、导航、交互 | [index.jsp](../src/main/webapp/public/index.jsp)、[healthverse.js](../src/main/webapp/assets/js/healthverse.js) | JSP 的元素 ID、导航键和按钮事件相互对应。修改页面入口时同步检查演示路径。 |
| 3D 学习空间 | [空间渲染](../src/main/webapp/assets/js/healthverse-spatial.js)、[空间样式](../src/main/webapp/assets/css/healthverse-spatial.css)、[资源出处](SPATIAL-EXPERIENCE.md) | 学生角色和桌面用于方案预览。选中方案、调整高度和切换原布局后，核对屏幕和物体位置。角色加载与摄像头授权分别验收。 |
| 浏览器视觉与训练 | [训练说明](../machine-learning/README.md)、[姿态推理](../src/main/webapp/assets/js/posture-inference.mjs)、[空间关系](../src/main/webapp/assets/js/spatial-inference.mjs) | 更换分类器时同步交付特征顺序、类别映射、测试集指标和浏览器可读的权重。当前页面加载 `assets/models/posture-classifiers-v1.json`。用同一段授权视频在浏览器回归。 |
| Java Agent | [Servlet 映射](../src/main/webapp/WEB-INF/web.xml)、[请求与响应对象](../src/main/java/com/example/healthverse/pojo/)、[服务层](../src/main/java/com/example/healthverse/service/) | 前端发送任务、约束和视觉摘要。改字段时同步修改请求组装、Java 类型、示例请求和接口测试。 |
| 联邦状态 | [协调器与客户端](../machine-learning/federated/)、[状态读取](../src/main/java/com/example/healthverse/service/FederatedStatusService.java) | 配置 `HV_FED_STATUS_URL` 后，在隐私控制中核对协调器状态。本机保存的参与意愿和真实客户端训练轮次分别记录。 |

## 浏览器与后端接口

下列路径均相对于应用上下文，返回 JSON。

| 方法与路径 | 请求 | 成功响应 |
| --- | --- | --- |
| `GET /api/health` | 无请求体 | `ok`、`agentConfigured`、`provider`、`safetyMode`、`federated`。其中 `agentConfigured` 表示已配置服务；模型请求是否成功以实际回复为准。 |
| `POST /api/agent` | UTF-8 JSON。必填字符串 `message`，最多 2000 个 Java 字符单位。可选对象 `context`。 | `title`、`reply`、`source` 为字符串，`degraded` 为布尔值。远程回复使用 `remote-agent`；本地回退也可以返回 HTTP 200，联调时检查 `degraded`。 |

发送 Agent 请求时，前端可附 `task`、`visualSource`、`observations`、`objects`、`spatialRelations`、`temporalEvidence`、`evidenceBoundary`、`userControl`。物体项含 `type/label/confidence/box`，关系项含 `type/label/severity/confidence/evidence`。原始视频在浏览器处理。远程 Agent 可接收消息和这些派生证据，联调使用获准的素材或样例请求。

后端校验失败会返回 `{"error":"错误码"}`。空消息对应 400 `message_required`，超长消息对应 400 `message_too_long`，JSON 解析失败对应 400 `invalid_json`，请求体超过 32 KiB 的声明长度或超过读取字符上限对应 413 `request_too_large`。

```powershell
$base = 'http://localhost:8080/HealthVerse_Submission'
Invoke-RestMethod "$base/api/health"
# 使用仓库内的课程示例消息执行一次完整联调
.\scripts\agent-smoke.ps1 -BaseUrl $base
# 空请求体对象应返回 HTTP 400 和 message_required
curl.exe -i -H 'Content-Type: application/json' --data '{}' "$base/api/agent"
```

若要联调远程模型，在启动 Tomcat 的进程环境中设置 `AI_PROVIDER`、`AI_API_URL`、`AI_MODEL`、`AI_API_KEY`，配置更改后重启实例。密钥通过团队私有渠道交接。Satori 侧车地址为可选配置 `SATORI_BRIDGE_URL`。完整配置见[项目说明](../README.md)。

## 提交前一起验收

1. **构建与首屏**。运行上面的 `package`，确认测试通过。打开工作台，检查六个入口及学生模型加载，再进入“人物细节”和“俯视”。
2. **真实输入**。导入一段包含人物和桌面物体的授权视频，检查播放、关键点、物体与关系提示。暂停后检查分析停止，结束输入后检查界面回到等待状态。另用已授权摄像头检查开始和停止。
3. **Agent**。发送示例请求，记录 HTTP 状态、`source` 和 `degraded`。在页面内给出“桌面右侧要留给写字”的限制，核对显示结果和当前输入证据。
4. **方案与记录**。切换方案 A/B、拖动屏幕高度、对比原始布局。进入自我实验后分别记录基线和方案阶段，确认保存后在个人健康记忆中核对记录，再测试删除。个人记录存于当前浏览器的 localStorage。
5. **交接**。在分支上提交并发起 PR，注明复现步骤、测试环境、实际结果和未测项。UI 变更附前后截图，模型变更附冻结评估结果。提交前检查暂存区，保留本机密钥、私人视频和受限训练集在本地。

当前可直接联调的交互包括旋转、预设视角、物体点选、方案对比和高度滑块。自由拖放书桌物体、点选人体部位读取证据仍属于设计建议。模型测试集的指标与青少年实景效果需要分别评估。
