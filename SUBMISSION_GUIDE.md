# HealthVerse 源码提交说明

## 提交定位

本目录是独立的 Java Web 源码提交版，采用与参考压缩包相同类别的 Maven WAR 组织：Java Servlet 后端、JSP 入口、静态资源、资源配置、脚本、示例及扩展目录彼此分离。

## 已实现内容

- 七个可切换的高保真页面：空间感知、身体模型、协同设计、自我实验、健康记忆、Agent 架构、课程设计档案；
- 可点击物体、视觉证据、AI 纠正、隐私控制、参数调节、方案撤销、实验状态、记忆管理和人物详情；
- `/api/agent`：远程 Anthropic Messages 兼容 Agent 与本地规则回退；
- `/api/health`：后端可用性与配置状态检查；
- 真实密钥仅从环境变量或本机忽略文件读取。

## 明确未实现

- 当前提交不包含真实摄像头识别、MediaPipe、LiDAR、三维空间重建或医疗诊断；
- 当前提交不持久化健康或视觉数据；
- `database/` 与 `mobile/` 是与提交工程同构的扩展位置，目录内文档已明确标注状态。

## 构建检查

在项目根目录执行：

```powershell
.\mvnw.cmd clean test
.\mvnw.cmd package
```

若没有 Maven Wrapper，可执行：

```powershell
mvn clean test package
```

成功后应生成 `target/HealthVerse_Submission.war`。将其部署到 Tomcat 9，并运行：

```powershell
.\scripts\agent-smoke.ps1
```

## 提交前检查

- `target/` 是否包含可部署 WAR；
- `src/main/webapp/public/index.jsp` 是否能打开全部页面；
- `/api/health` 是否返回 JSON；
- 未配置模型时 `/api/agent` 是否返回本地回退建议；
- 配置模型后是否保持密钥不出现在页面、日志和 Git 中；
- 压缩包内是否保留完整 Maven 项目根目录，而不是只提交 `target/`。
