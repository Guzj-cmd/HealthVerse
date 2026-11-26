# HealthVerse 源码提交说明

## 提交定位

本目录是独立的 Java Web 源码提交版，采用与参考压缩包相同类别的 Maven WAR 组织：Java Servlet 后端、JSP 入口、静态资源、资源配置、脚本、示例及扩展目录彼此分离。

## 已实现内容

- 七个可切换的高保真页面：空间感知、身体模型、协同设计、自我实验、健康记忆、Agent 架构、课程设计档案；
- 可点击物体、视觉证据、AI 纠正、隐私控制、参数调节、方案撤销、实验状态、记忆管理和人物详情；
- `/api/agent`：远程 Anthropic Messages 兼容 Agent 与本地规则回退；
- `/api/health`：后端可用性与配置状态检查；
- 真实摄像头和本地视频导入、MediaPipe 33 点、训练姿态分类器、EfficientDet-Lite0 目标检测；
- 基于人体与目标框的二维空间关系、真实帧时间时序、证据约束 Agent；
- 三步关键点校准、分阶段短时实验、证据门槛、可见/可停用/可删除的 localStorage 记忆；
- `/api/health` 同步联邦协调器真实状态，联邦客户端与协调端支持不同设备联网运行；
- 真实密钥仅从环境变量或本机忽略文件读取。

## 明确边界

- 不包含 LiDAR、三维空间重建或医疗诊断；单目画面不输出真实厘米或深度；
- 原始视觉不持久化；只有用户确认的归一化校准、实验记录和可控记忆保存在浏览器；
- 真实多设备联邦轮次必须由至少两台设备产生不同匿名指纹；本机多进程测试不会冒充多设备；
- 默认联邦协调器可见单个参数更新，不宣称安全聚合或差分隐私；
- `database/` 与 `mobile/` 是与提交工程同构的扩展位置，目录内文档已明确标注状态。

## 构建检查

在项目根目录执行：

```powershell
.\mvnw.cmd clean test
.\mvnw.cmd package
node machine-learning/browser-export/test_spatial_inference.mjs
python -m unittest discover -s machine-learning/federated/tests -v
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
- `/api/health` 的 `federated` 是否准确显示未配置、不可达、本机测试或真实多设备状态；
- 未配置模型时 `/api/agent` 是否返回本地回退建议；
- 导入视频后浏览器控制台是否无模块/MIME/模型 404，姿态、目标和时序是否更新；
- 校准保存内容是否不包含原始关键点，证据不足实验是否不进入偏好记忆；
- 配置模型后是否保持密钥不出现在页面、日志和 Git 中；
- 压缩包内是否保留完整 Maven 项目根目录，而不是只提交 `target/`。
