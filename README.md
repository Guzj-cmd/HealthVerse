# HealthVerse：个人健康 AI 工作台

HealthVerse 是一个面向现实空间的交互设计课程原型。系统将视觉观察、用户任务、环境约束、反事实方案和短时自我实验组织成可纠正、可撤销的协同闭环。AI 被设计为协作者，而不是自动诊断或替用户作决定的裁判。

## 核心演示路径

1. 在“实时空间感知”中查看人物、物体和空间关系，并点击显示器查看证据；
2. 纠正 AI、说明任务需要，或暂停本次提醒；
3. 在“环境协同设计”中比较方案 A / B，拖动显示器高度并保留桌面约束；
4. 在“健康自我实验”中比较短时姿态、操作效率和主观舒适度；
5. 由用户确认是否把结果保存为可见、可停用、可删除的个人记忆；
6. 在“Agent 闭环架构”和“课程设计档案”中查看论文机制、人物角色、场景剧本和关键任务路径。

页面中的人物、数据和实验结果均为课程概念原型的示意内容，不是医疗检测结果。

## 项目结构

```text
HealthVerse/
├─ pom.xml
├─ README.md
├─ SUBMISSION_GUIDE.md
├─ database/                         持久化扩展说明
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
- 摄像头、视觉证据与人物角色均为概念演示，不在当前提交版中上传或持久化。
