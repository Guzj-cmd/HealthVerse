<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="app-context" content="${pageContext.request.contextPath}">
  <meta name="theme-color" content="#eef4f1">
  <link rel="icon" href="data:,">
  <title>HealthVerse · 个人健康 AI 工作台</title>
  <meta name="description" content="一个以视觉感知、空间协同设计和自我实验为核心的个人健康 AI 工作台概念原型。">
  <link rel="stylesheet" href="${pageContext.request.contextPath}/assets/css/healthverse.css">
</head>
<body>
  <div class="app-shell">
    <header class="chrome" aria-label="应用标题栏">
      <div class="window-dots" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="brandline">
        <span class="brand-mark" aria-hidden="true"><span></span></span>
        <span>HealthVerse</span><b>/</b><span id="crumb">实时空间感知</span>
      </div>
      <div class="chrome-actions">
        <button class="quiet-btn" id="tourBtn" type="button">演示路径</button>
        <button class="icon-btn" id="helpBtn" type="button" aria-label="查看设计说明">?</button>
      </div>
    </header>

    <div class="workspace">
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="home-glyph" aria-hidden="true"></div>
          <div><strong>HealthVerse</strong><span>PERSONAL HEALTH AI</span></div>
        </div>

        <nav class="main-nav" aria-label="主功能">
          <button class="nav-item active" data-view="sense" type="button"><i class="nav-icon">⌁</i><span>实时空间感知</span><em>01</em></button>
          <button class="nav-item" data-view="body" type="button"><i class="nav-icon">◌</i><span>个人身体模型</span><em>02</em></button>
          <button class="nav-item" data-view="design" type="button"><i class="nav-icon">◇</i><span>环境协同设计</span><em>03</em></button>
          <button class="nav-item" data-view="experiment" type="button"><i class="nav-icon">∿</i><span>健康自我实验</span><em>04</em></button>
          <button class="nav-item" data-view="memory" type="button"><i class="nav-icon">⌘</i><span>个人健康记忆</span><em>05</em></button>
          <button class="nav-item" data-view="architecture" type="button"><i class="nav-icon">⌬</i><span>Agent 闭环架构</span><em>06</em></button>
          <button class="nav-item course" data-view="research" type="button"><i class="nav-icon">▤</i><span>课程设计档案</span><em>07</em></button>
        </nav>

        <div class="privacy-card">
          <div class="privacy-top"><span class="pulse-dot"></span><strong>本地感知</strong></div>
            <p>画面仅用于当前会话。你可以随时暂停、纠正或删除记录。</p>
          <button id="privacyBtn" type="button">隐私控制</button>
        </div>
      </aside>

      <main class="content" id="mainContent">
        <section class="view active" data-screen="sense" aria-labelledby="senseTitle">
          <div class="screen-head">
            <div><span class="eyebrow">PAPER-GROUNDED LIVE WORKSPACE</span><h1 id="senseTitle">从情境观察到可撤销验证</h1><p>把人、物体、任务与时机组织成一条可求证、可纠正的空间健康闭环。</p></div>
            <div class="status-cluster"><span class="status-pill live"><i></i><span id="visionStatusPill">等待视觉输入</span></span><button class="secondary-btn" id="pauseBtn" type="button" disabled>暂停分析</button></div>
          </div>

          <div class="sense-grid">
            <article class="camera-card panel">
              <div class="method-panel-label label-a"><b>(a)</b><strong>Shared Spatial Perception</strong><span>共享空间感知 · People / Objects / Task / Timing</span></div>
              <div class="camera-toolbar">
                <span>视觉输入 <b class="demo-badge" id="sourceStatus" data-state="idle">等待真实输入 · 本地处理</b></span>
                <div><button class="toolbar-chip active" data-overlay="skeleton" type="button">姿态骨架</button><button class="toolbar-chip active" data-overlay="objects" type="button">场景标签</button></div>
              </div>
              <div class="source-controls" role="group" aria-label="选择真实视觉输入">
                <button class="toolbar-chip source-button" id="startCameraBtn" type="button">启用摄像头</button>
                <label class="toolbar-chip source-button upload-source" for="videoFileInput">导入视频</label>
                <input id="videoFileInput" type="file" accept="video/*" hidden>
                <button class="toolbar-chip source-button" id="stopSourceBtn" type="button" disabled>停止输入</button>
                <span class="source-privacy">视频仅在当前浏览器中处理，不上传原始画面</span>
              </div>
              <div class="scene" id="scene">
                <div class="live-vision-stage" id="liveVisionStage" hidden>
                  <video id="visionVideo" playsinline muted aria-label="真实摄像头或导入视频画面"></video>
                  <canvas id="visionCanvas" aria-label="MediaPipe 实时姿态关键点覆盖层"></canvas>
                  <div class="vision-hud" aria-live="polite">
                    <span id="poseMetric">等待人体</span>
                    <span id="neckMetric">头颈偏移 —</span>
                    <span id="shoulderMetric">肩线角度 —</span>
                    <span id="objectMetric">工作区物体 —</span>
                    <span id="relationMetric">等待人–物关系</span>
                  </div>
                </div>
                <div class="scene-placeholder" id="scenePlaceholder">
                <div class="scanline"></div>
                <svg viewBox="0 0 900 540" aria-hidden="true">
                  <defs>
                    <linearGradient id="wallGlow" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2e4654"/><stop offset="1" stop-color="#15252f"/></linearGradient>
                    <radialGradient id="fieldGlow"><stop offset="0" stop-color="#67e5cb" stop-opacity=".28"/><stop offset="1" stop-color="#67e5cb" stop-opacity="0"/></radialGradient>
                  </defs>
                  <rect width="900" height="540" fill="url(#wallGlow)"/>
                  <circle cx="374" cy="286" r="190" fill="url(#fieldGlow)"/>
                  <rect x="36" y="55" width="220" height="290" rx="8" fill="#8aa5b6"/>
                  <path d="M146 55v290M36 196h220" stroke="#506b7b" stroke-width="12"/>
                  <path d="M28 355h250" stroke="#21343e" stroke-width="20"/>
                  <path d="M415 337h420" stroke="#bea98e" stroke-width="26" stroke-linecap="round"/>
                  <path d="M451 350v185M790 350v185" stroke="#8a715c" stroke-width="20"/>
                  <rect x="582" y="170" width="210" height="134" rx="12" fill="#8ba7b8"/>
                  <rect x="598" y="186" width="178" height="96" rx="7" fill="#1d3341"/>
                  <path d="M687 304v34M652 338h72" stroke="#8ba7b8" stroke-width="14"/>
                  <rect x="808" y="274" width="42" height="66" rx="14" fill="#8fd8cc"/>
                  <path d="M312 454v81M226 454v81M220 450h150" stroke="#8299a4" stroke-width="18"/>
                  <path d="M265 327v132h140" stroke="#8299a4" stroke-width="22" fill="none"/>
                  <circle cx="350" cy="167" r="45" fill="#d4ccbe"/>
                  <path class="skeleton" d="M349 213l-29 90 47 105 130 17v93M329 252l-12 66M325 251l101 81 111-13" fill="none" stroke="#9fb5be" stroke-width="27" stroke-linecap="round" stroke-linejoin="round"/>
                  <path class="skeleton accent" d="M349 213l-29 90 47 105 130 17v93M329 252l-12 66M325 251l101 81 111-13" fill="none" stroke="#67e5cb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
                  <g class="joints" fill="#7ef1d8"><circle cx="349" cy="213" r="9"/><circle cx="320" cy="303" r="9"/><circle cx="367" cy="408" r="9"/><circle cx="497" cy="425" r="9"/><circle cx="497" cy="518" r="9"/><circle cx="426" cy="332" r="9"/><circle cx="537" cy="319" r="9"/></g>
                  <path d="M350 205h260" stroke="#7ef1d8" stroke-width="3" stroke-dasharray="10 10"/>
                  <path d="M610 205v-42h186v161" stroke="#f0b35f" stroke-width="3" stroke-dasharray="10 8" fill="none"/>
                </svg>
                <button class="object-tag warning" data-object="monitor" style="left:62%;top:18%" type="button"><span>显示器</span><b>画面示意</b></button>
                <button class="object-tag" data-object="cup" style="left:82%;top:53%" type="button"><span>水杯</span><b>画面示意</b></button>
                <button class="object-tag" data-object="chair" style="left:22%;top:74%" type="button"><span>座椅</span><b>画面示意</b></button>
                </div>
                <div class="scene-caption"><span id="visionSourceMetric">尚未启用视觉输入</span><span id="visionPoseMetric">姿态关键点 —</span><span id="visionFpsMetric">分析帧率 —</span><span id="temporalMetric">时序事件等待中</span></div>
              </div>
            </article>

            <aside class="agent panel" aria-label="Health Agent 分析面板">
              <div class="method-panel-label label-b"><b>(b)</b><strong>BDI Intent Model</strong><span>Observe → Infer → Confirm</span></div>
              <div class="agent-title"><span class="agent-orb"></span><div><h2>Health Agent</h2><p id="taskDuration">当前会话：等待真实输入</p></div></div>
              <div class="reasoning-card" aria-live="polite">
                <div class="card-kicker">观察 → 推断 → 求证</div>
                <div class="model-evidence" id="modelEvidence">真实姿态模型 · 等待视觉输入</div>
                <h3 id="agentFinding">等待真实视觉与任务输入</h3>
                <p id="agentReason">启用摄像头或导入视频后，Agent 才会依据实际姿态、物体关系和持续时间给出可撤销建议。</p>
                <div class="evidence-row"><span>模型置信度</span><div class="confidence"><i id="confidenceBar" style="width:0%"></i></div><b id="confidenceText">—</b></div>
                <div class="interrupt-note"><b>为什么现在提醒？</b><span id="interruptReason">等待真实姿态、物体和持续时间证据。</span></div>
              </div>
              <div class="correction-row" aria-label="纠正 AI 的判断">
                <span>这个判断不准确？</span>
                <button data-correction="wrong" type="button">识别错误</button>
                <button data-correction="needed" type="button">任务需要</button>
                <button data-correction="mute" type="button">不再提醒</button>
              </div>
              <div class="agent-actions">
                <button class="primary-btn" id="previewBtn" type="button">生成空间调整预览</button>
                <button class="secondary-btn wide" id="evidenceBtn" type="button">查看视觉证据</button>
              </div>
              <div class="consent-note"><span>自主权优先</span><p>这是一次可撤销的建议，不会自动改变你的环境。</p></div>
              <label class="prompt-box"><span>⌁</span><input id="agentInput" type="text" placeholder="告诉 AI 你的目标或限制…"><button id="sendPrompt" type="button" aria-label="发送">发送</button></label>
            </aside>
          </div>

          <section class="method-loop-map" aria-label="从空间观察到验证和记忆的交互闭环">
            <article class="method-stage method-stage-c">
              <div class="method-stage-title"><b>(c)</b><span><strong>Counterfactual Spatial Co-Design</strong><small>反事实空间协同设计</small></span></div>
              <div class="method-token-row" aria-hidden="true"><i>原布局</i><i>方案 A</i><i>方案 B</i></div>
              <p>固定用户约束，再比较可撤销布局，而不是直接改变现实环境。</p>
              <button class="secondary-btn" data-go="design" type="button">进入方案比较</button>
            </article>

            <svg class="method-flow-arrow arrow-cd" viewBox="0 0 150 72" role="img" aria-label="从方案比较进入短时验证">
              <path d="M8 43 C34 13, 72 64, 116 31" fill="none" stroke="#171717" stroke-width="5" stroke-linecap="round"/>
              <path d="M105 18 L137 27 L116 51" fill="none" stroke="#171717" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M11 49 C39 20, 70 69, 119 37" fill="none" stroke="#87669b" stroke-width="2" stroke-dasharray="12 5"/>
            </svg>

            <article class="method-stage method-stage-d">
              <div class="method-stage-title"><b>(d)</b><span><strong>Verify &amp; Evolve</strong><small>短时验证 · 用户确认 · 可删记忆</small></span></div>
              <div class="method-checkpoints"><i>1 预览</i><i>2 体验</i><i>3 确认</i></div>
              <p>用 A/B 短时体验验证建议；只有用户确认后，结果才进入个人记忆。</p>
              <button class="secondary-btn" data-go="experiment" type="button">开始短时验证</button>
            </article>

            <svg class="method-flow-arrow arrow-return" viewBox="0 0 180 72" role="img" aria-label="验证结果返回个人模型">
              <path d="M166 15 C112 4, 66 11, 25 46" fill="none" stroke="#171717" stroke-width="3" stroke-dasharray="19 6 4 5" stroke-linecap="round"/>
              <path d="M39 31 L16 50 L45 57" fill="none" stroke="#171717" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
              <text x="90" y="64" text-anchor="middle" fill="#5a4d59" font-size="13">confirmed memory only</text>
            </svg>
          </section>

          <div class="metric-grid">
            <article class="metric-card"><span>真实视觉输入</span><strong id="visionSummary">等待连接</strong><p id="visionSummaryDetail">启用摄像头或导入视频后开始本地分析</p></article>
            <article class="metric-card"><span>人–物空间关系</span><strong id="spatialSummary">尚未建立关系</strong><p id="spatialSummaryDetail">需要同时看到人体和工作区物体</p></article>
            <article class="metric-card"><span>时序行为</span><strong id="sessionBehavior">等待会话</strong><p>持续姿态使用真实帧时间累计</p></article>
            <article class="metric-card"><span>个人模型</span><strong id="calibrationSummary">待校准</strong><p id="calibrationDetail">使用真实关键点采集个人活动范围</p><button data-go="body" type="button">开始校准</button></article>
            <article class="metric-card"><span>Agent 工作状态</span><strong class="mint" id="agentStatusSummary">等待证据</strong><p id="agentStatusDetail">尚未形成建议</p></article>
          </div>
        </section>

        <section class="view" data-screen="body" aria-labelledby="bodyTitle">
          <div class="screen-head"><div><span class="eyebrow">PERSONAL BODY MODEL</span><h1 id="bodyTitle">让空间适应真实的你</h1><p>通过简单动作采集个人可达范围，不套用统一的人体标准。</p></div><span class="status-pill"><i></i>校准模式</span></div>
          <div class="body-layout">
            <article class="body-visual panel">
              <div class="body-stage">
                <div class="reach-field field-outer"></div><div class="reach-field field-inner"></div>
                <div class="body-avatar"><span class="head"></span><span class="torso"></span><span class="arm left"></span><span class="arm right"></span><span class="leg left"></span><span class="leg right"></span></div>
                <div class="axis-note top">舒适可达区</div><div class="axis-note bottom">扩展可达区</div>
              </div>
              <div class="stage-legend"><span><i class="legend-dot comfort"></i><b id="comfortReachLabel">舒适范围待校准</b></span><span><i class="legend-dot extended"></i><b id="extendedReachLabel">扩展范围待校准</b></span><span>归一化模型 · 非医疗测量</span></div>
            </article>
            <aside class="calibration panel">
              <span class="eyebrow">2 分钟自主采集</span><h2>活动范围校准</h2><p>按你觉得舒适的幅度完成动作。随时可以跳过。</p>
              <div class="step-list">
                <button class="cal-step active" type="button"><i>1</i><span><b>自然坐姿</b><small>等待采集当前真实关键点</small></span></button>
                <button class="cal-step" type="button"><i>2</i><span><b>向前触及</b><small>缓慢伸手触碰虚拟目标</small></span></button>
                <button class="cal-step" type="button"><i>3</i><span><b>左右转身</b><small>只需达到舒适位置</small></span></button>
              </div>
              <label class="range-label"><span>活动范围缩放预览</span><b id="rangeValue">65%</b><input id="rangeInput" type="range" min="45" max="90" value="65"></label>
              <button class="primary-btn wide" id="captureBtn" type="button">采集当前动作</button>
              <p class="microcopy">采集结果可单独删除，不用于疾病诊断。</p>
            </aside>
          </div>
        </section>

        <section class="view" data-screen="design" aria-labelledby="designTitle">
          <div class="screen-head"><div><span class="eyebrow">HUMAN–AI CO-DESIGN</span><h1 id="designTitle">比较方案，而不是接受唯一答案</h1><p>拖动参数、切换方案，再决定是否执行。</p></div><span class="status-pill"><i></i>方案预览</span></div>
          <div class="design-layout">
            <aside class="plan-list panel">
              <div class="plan-intro"><span class="eyebrow">反事实方案</span><h2>两个可撤销方案</h2><p>均满足“保持桌面整洁，不移动主机”的限制。</p></div>
                <button class="plan-card active" data-plan="a" type="button"><span>A · 轻量调整</span><strong>显示器相对抬高</strong><small>按画面比例预览 · 执行前需用户实测</small></button>
                <button class="plan-card" data-plan="b" type="button"><span>B · 组合调整</span><strong>屏幕对齐 + 常用物体靠近</strong><small>仅使用当前二维关系 · 不伪造厘米距离</small></button>
              <div class="constraint"><span>你的限制</span><p>“桌面右侧需要保留手写区域。”</p><button id="editConstraint" type="button">编辑</button></div>
            </aside>
            <article class="compare panel">
              <div class="compare-head"><div><span id="planLabel">方案 A</span><strong id="planSummary">仅调整显示器高度</strong></div><div class="segmented"><button class="active" data-compare="after" type="button">调整后</button><button data-compare="before" type="button">原始布局</button></div></div>
              <div class="compare-scene after" id="compareScene">
                <div class="mini-person"><i></i><b></b><em></em></div>
                <div class="mini-desk"></div><div class="mini-monitor"><span></span></div><div class="mini-cup"></div>
                <div class="sightline"></div><div class="angle-badge">二维对齐 <b id="angleValue">偏移级别 8</b></div>
                <div class="ghost-monitor"></div>
              </div>
              <div class="compare-controls">
                <label><span>相对调整量</span><b id="heightValue">+12% 画面高度</b><input id="heightInput" type="range" min="0" max="20" value="12"></label>
                <div class="impact-chips"><span class="good">调整后重新检测</span><span>手写区域不变</span><span>可随时撤销</span></div>
              </div>
              <div class="compare-footer"><button class="text-btn hidden" id="undoPlan" type="button" hidden>撤销，恢复原始布局</button><button class="secondary-btn" id="rejectPlan" type="button">换一个方案</button><button class="primary-btn" id="applyPlan" type="button">选择方案并开始验证</button></div>
            </article>
          </div>
        </section>

        <section class="view" data-screen="experiment" aria-labelledby="experimentTitle">
          <div class="screen-head"><div><span class="eyebrow">PERSONAL SELF-EXPERIMENT</span><h1 id="experimentTitle">验证“更适合我”，而不是证明“长期有效”</h1><p>比较两个短时学习场景，观察姿态、操作效率和主观舒适度。</p></div><button class="secondary-btn" id="protocolBtn" type="button">查看实验方案</button></div>
          <div class="experiment-grid">
            <article class="experiment-main panel">
              <div class="experiment-top"><div><span class="run-dot"></span><b id="experimentState">准备阶段</b><small>3 分钟基线 + 6 分钟方案 + 主观评分</small></div><div class="timer" id="timer">03:00</div></div>
              <div class="comparison-bars">
                <div class="bar-group"><span>非中性躯干姿态时长</span><div><i id="baselinePostureBar" style="width:0"></i><b id="baselinePostureValue">基线：等待记录</b></div><div class="candidate"><i id="candidatePostureBar" style="width:0"></i><b id="candidatePostureValue">方案：等待记录</b></div></div>
                <div class="bar-group"><span>工作区物体关系</span><div><i id="relationEvidenceBar" style="width:0"></i><b id="relationEvidenceValue">尚无可比较证据</b></div></div>
                <div class="bar-group"><span>主观舒适度</span><div class="candidate"><i id="comfortBar" style="width:0"></i><b id="comfortValue">完成后由用户输入</b></div></div>
              </div>
              <div class="experiment-note"><strong>等待真实体验记录</strong><p>启动短时体验后，本页才记录当前会话数据；短期变化不能直接推断长期健康收益。</p></div>
            </article>
            <aside class="experiment-side panel">
              <span class="eyebrow">实验协议</span><h2>显示器高度对比</h2>
              <ol><li class="active"><i>1</i><span><b>记录原始布局</b><small>开始后按真实帧时间记录</small></span></li><li><i>2</i><span><b>体验所选方案</b><small>保持同一任务</small></span></li><li><i>3</i><span><b>填写主观感受</b><small>用户本人评分</small></span></li><li><i>4</i><span><b>确认是否保存</b><small>可撤销</small></span></li></ol>
              <button class="primary-btn wide" id="experimentBtn" type="button">开始记录原始布局基线</button>
              <button class="text-btn" id="skipExperiment" type="button">跳过并保留原始布局</button>
            </aside>
          </div>
        </section>

        <section class="view" data-screen="memory" aria-labelledby="memoryTitle">
          <div class="screen-head"><div><span class="eyebrow">PERSONAL HEALTH WORLD MODEL</span><h1 id="memoryTitle">AI 的记忆应该可见、可改、可删除</h1><p>查看“人—任务—环境—反馈”之间的关系，并决定哪些信息可以保留。</p></div><button class="secondary-btn" id="exportBtn" type="button">导出我的数据</button></div>
          <div class="memory-layout">
            <article class="graph panel" aria-label="个人健康世界模型关系图">
              <svg viewBox="0 0 760 500" aria-hidden="true">
                <g stroke="#38515d" stroke-width="2"><path d="M375 250L190 122M375 250L591 127M375 250L190 382M375 250L580 386M190 122L591 127M190 382L580 386"/></g>
                <g class="graph-node main"><circle cx="375" cy="250" r="74"/><text id="profileGraphUser" x="375" y="242">当前用户</text><text id="profileGraphCalibration" x="375" y="270">尚未校准</text></g>
                <g class="graph-node"><circle cx="190" cy="122" r="58"/><text x="190" y="115">当前任务</text><text id="profileGraphTask" x="190" y="141">尚未确认</text></g>
                <g class="graph-node"><circle cx="591" cy="127" r="58"/><text x="591" y="120">视觉环境</text><text id="profileGraphEnvironment" x="591" y="146">等待输入</text></g>
                <g class="graph-node"><circle cx="190" cy="382" r="58"/><text x="190" y="375">可控记忆</text><text id="profileGraphMemories" x="190" y="401">0 条启用</text></g>
                <g class="graph-node"><circle cx="580" cy="386" r="64"/><text x="580" y="379">实验反馈</text><text id="profileGraphExperiment" x="580" y="405">尚无记录</text></g>
              </svg>
              <div class="graph-legend"><span><i></i>用户确认</span><span><i></i>视觉推断</span><span><i></i>实验结果</span></div>
            </article>
            <aside class="memory-list panel">
              <span class="eyebrow">可控记忆</span><h2 id="memoryCount">已保存 0 条</h2>
              <div id="memoryItems"><p class="empty-memory">尚无经用户确认的个人记忆。</p></div>
              <button class="secondary-btn wide" id="clearMemory" type="button">管理全部记忆</button>
            </aside>
          </div>
        </section>

        <section class="view" data-screen="architecture" aria-labelledby="architectureTitle">
          <div class="screen-head"><div><span class="eyebrow">PAPER-GROUNDED SYSTEM ARCHITECTURE</span><h1 id="architectureTitle">从情境理解到可撤回的个人学习闭环</h1><p>用顶会论文的机制语言重绘 HealthVerse，而不是把“视觉模型＋聊天框”拼在一起。</p></div><button class="secondary-btn" id="downloadArch" type="button">下载 SVG 架构图</button></div>
          <article class="paper-figure panel">
            <div class="figure-title"><span>(a)</span><strong>HealthVerse · Self-Evolving Spatial Health Agent</strong><small>概念原型 / paper-grounded redesign</small></div>
            <svg id="architectureSvg" viewBox="0 0 1480 860" role="img" aria-labelledby="archSvgTitle archSvgDesc">
              <title id="archSvgTitle">HealthVerse Agent 闭环架构</title>
              <desc id="archSvgDesc">包含共享视觉感知、BDI 意图模型、反事实协同设计、现实验证和可修正记忆五个阶段。</desc>
              <defs>
                <filter id="rough" x="-3%" y="-3%" width="106%" height="106%"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="7" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="1.4"/></filter>
                <filter id="rough2" x="-3%" y="-3%" width="106%" height="106%"><feTurbulence type="turbulence" baseFrequency="0.009 0.018" numOctaves="2" seed="19" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="2.1"/></filter>
                <filter id="rough3" x="-3%" y="-3%" width="106%" height="106%"><feTurbulence type="fractalNoise" baseFrequency="0.017" numOctaves="1" seed="31" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="1.8"/></filter>
                <filter id="rough4" x="-3%" y="-3%" width="106%" height="106%"><feTurbulence type="turbulence" baseFrequency="0.006 0.02" numOctaves="2" seed="43" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="2.5"/></filter>
                <marker id="archArrow" markerWidth="12" markerHeight="12" refX="10" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#151515"/></marker>
                <marker id="archArrowOpen" markerWidth="14" markerHeight="14" refX="11" refY="6" orient="auto"><path d="M1,1 L12,6 L1,11" fill="none" stroke="#151515" stroke-width="2.2"/></marker>
                <marker id="archArrowWide" markerWidth="16" markerHeight="14" refX="13" refY="6" orient="auto"><path d="M0,0 Q7,6 14,6 Q7,6 0,12 Z" fill="#151515"/></marker>
                <pattern id="hatchBlue" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 10L10 0" stroke="#76a8d8" stroke-width="2" opacity=".45"/></pattern>
                <pattern id="hatchMint" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 10L10 0" stroke="#75b38c" stroke-width="2" opacity=".5"/></pattern>
              </defs>

              <g class="rough-box panel-blue" filter="url(#rough)"><rect x="20" y="28" width="350" height="770" rx="22"/><rect class="inner-line" x="30" y="38" width="330" height="750" rx="18"/></g>
              <text class="panel-label" x="40" y="75">(a) Shared Spatial Perception</text>
              <g class="paper-card observation-card"><rect x="48" y="102" width="294" height="104" rx="16"/><text x="195" y="135">REAL-WORLD OBSERVATION</text><text class="zh" x="195" y="174">人体 · 物体 · 任务 · 时间</text></g>
              <g class="film-strip" transform="translate(62 232)"><rect width="268" height="112" rx="12"/><rect class="frame" x="12" y="12" width="70" height="72"/><rect class="frame" x="99" y="12" width="70" height="72"/><rect class="frame active" x="186" y="12" width="70" height="72"/><path d="M30 65l16-28 18 28M118 65l16-28 18 28M205 65l16-28 18 28"/><text x="134" y="103">Oₜ₋₂ · Oₜ₋₁ · Oₜ</text></g>
              <path class="arch-arrow down-a" d="M195 350c-7 18 8 38 0 58"/>
              <g class="paper-card attention-card"><rect x="48" y="416" width="294" height="135" rx="16"/><text x="195" y="452">JOINT ATTENTION</text><text class="zh" x="195" y="488">指向 / 凝视 / 语言共同定位</text><g class="attention-dots"><circle cx="104" cy="520" r="13"/><circle cx="150" cy="520" r="13"/><circle cx="196" cy="520" r="13"/><path d="M218 520h78"/></g></g>
              <path class="arch-arrow down-b" d="M195 558c8 18-6 37 0 58"/>
              <g class="paper-card evidence-card"><rect x="48" y="624" width="294" height="136" rx="16"/><text x="195" y="658">EVIDENCE CARDS</text><text class="zh" x="195" y="696">来源 · 置信度 · 状态 · 有效期</text><g transform="translate(74 716)"><rect width="72" height="26" rx="7"/><rect x="84" width="72" height="26" rx="7"/><rect x="168" width="72" height="26" rx="7"/></g></g>

              <g class="rough-box panel-peach" filter="url(#rough2)"><rect x="397" y="28" width="660" height="352" rx="22"/><rect class="inner-line" x="407" y="38" width="640" height="332" rx="18"/></g>
              <text class="panel-label" x="420" y="75">(b) BDI Intent Model · Observe → Infer → Confirm</text>
              <g class="bdi-box belief"><rect x="432" y="108" width="170" height="202" rx="18"/><text x="517" y="140">BELIEF</text><text class="zh" x="517" y="175">我知道什么？</text><text class="small" x="455" y="215">H  身体能力</text><text class="small" x="455" y="246">E  环境状态</text><text class="small" x="455" y="277">R  人–物关系</text></g>
              <path class="arch-arrow h-a" d="M610 208c22-8 39 7 62 0"/>
              <g class="bdi-box desire"><rect x="680" y="108" width="170" height="202" rx="18"/><text x="765" y="140">DESIRE</text><text class="zh" x="765" y="175">用户想实现什么？</text><text class="small" x="702" y="222">任务目标</text><text class="small" x="702" y="254">明确限制</text><text class="small" x="702" y="286">用户确认</text></g>
              <path class="arch-arrow h-b" d="M858 208c18 2 35-7 62 0"/>
              <g class="bdi-box intention"><rect x="928" y="108" width="96" height="202" rx="18"/><text x="976" y="140">INTENT</text><text class="zh" x="976" y="180">下一步</text><text class="small center" x="976" y="225">提醒</text><text class="small center" x="976" y="257">求证</text><text class="small center" x="976" y="289">静默</text></g>
              <path class="confirm-loop" d="M976 324c0 36-420 36-420 0"/>
              <text class="loop-label" x="742" y="355">low confidence → ask first</text>

              <g class="rough-box panel-lilac" filter="url(#rough3)"><rect x="397" y="405" width="660" height="393" rx="22"/><rect class="inner-line" x="407" y="415" width="640" height="373" rx="18"/></g>
              <text class="panel-label" x="420" y="452">(c) Counterfactual Spatial Co-Design</text>
              <g class="plan-box plan-a"><rect x="436" y="486" width="170" height="174" rx="16"/><text x="521" y="518">PLAN A</text><path d="M470 616h102M481 552h80v54M520 552v-30"/><rect x="500" y="540" width="40" height="32" fill="url(#hatchBlue)"/><text class="zh" x="521" y="646">仅抬高显示器</text></g>
              <text class="plus" x="628" y="582">+</text>
              <g class="plan-box plan-b"><rect x="662" y="486" width="170" height="174" rx="16"/><text x="747" y="518">PLAN B</text><path d="M696 616h102M707 552h80v54M746 552v-30"/><rect x="726" y="540" width="40" height="32" fill="url(#hatchMint)"/><circle cx="785" cy="590" r="12"/><text class="zh" x="747" y="646">显示器＋物品移动</text></g>
              <path class="arch-arrow h-c" d="M846 576c18-12 44 10 64 0"/>
              <g class="paper-card compare-card"><rect x="918" y="486" width="106" height="174" rx="16"/><text x="971" y="520">COMPARE</text><text class="small center" x="971" y="558">effort</text><text class="small center" x="971" y="590">comfort</text><text class="small center" x="971" y="622">constraint</text></g>
              <g class="constraint-note"><rect x="454" y="694" width="552" height="64" rx="14"/><text x="730" y="720">USER CONSTRAINT</text><text class="zh" x="730" y="748">“右侧保留手写区域” · 可拖动 · 可拒绝 · 可撤销</text></g>

              <g class="rough-box panel-yellow" filter="url(#rough4)"><rect x="1084" y="28" width="376" height="770" rx="22"/><rect class="inner-line" x="1094" y="38" width="356" height="750" rx="18"/></g>
              <text class="panel-label" x="1108" y="75">(d) Verify & Evolve</text>
              <g class="verify-step step-a"><rect x="1122" y="108" width="300" height="92" rx="16"/><text x="1272" y="140">1 · ACT IN SPACE</text><text class="zh" x="1272" y="176">用户执行选定方案</text></g>
              <path class="arch-arrow down-c" d="M1272 206c-5 13 7 29 0 48"/>
              <g class="verify-step step-b"><rect x="1122" y="262" width="300" height="92" rx="16"/><text x="1272" y="294">2 · VISUAL VERIFY</text><text class="zh" x="1272" y="330">同一证据标准检查结果</text></g>
              <path class="arch-arrow down-d" d="M1272 360c9 14-8 30 0 48"/>
              <g class="verify-step step-c"><rect x="1122" y="416" width="300" height="112" rx="16"/><text x="1272" y="448">3 · SELF-EXPERIMENT</text><text class="zh" x="1272" y="484">假设 · 干预 · 指标 · 停止条件</text><text class="small center" x="1272" y="510">short-term evidence only</text></g>
              <path class="arch-arrow down-e" d="M1272 534c-8 16 6 31 0 48"/>
              <g class="memory-stack"><rect x="1148" y="590" width="244" height="140" rx="18"/><rect x="1136" y="602" width="244" height="140" rx="18"/><rect x="1124" y="614" width="244" height="140" rx="18"/><text x="1246" y="650">REVISABLE MEMORY</text><text class="zh" x="1246" y="688">确认 / 拒绝 / 过期 / 删除</text><g transform="translate(1165 708)"><rect width="50" height="25" rx="7"/><rect x="62" width="62" height="25" rx="7"/><rect x="136" width="58" height="25" rx="7"/></g></g>

              <path class="arch-arrow cross one" d="M370 206h58"/>
              <path class="arch-arrow cross two" d="M1058 210h54"/>
              <path class="arch-arrow cross three" d="M1058 602h54"/>
              <path class="return-loop" d="M1304 780c-80 68-970 72-1086 10"/>
              <text class="loop-label return" x="760" y="836">user feedback updates evidence and memory — never the base model automatically</text>
            </svg>
            <div class="figure-caption"><strong>机制来源：</strong><a href="https://doi.org/10.1145/3706598.3714188" target="_blank" rel="noreferrer">Satori / BDI</a><span>·</span><a href="https://doi.org/10.1145/3772318.3791059" target="_blank" rel="noreferrer">Eye2Eye / 共同注意与可修正记忆</a><span>·</span><a href="https://doi.org/10.1145/3772318.3791551" target="_blank" rel="noreferrer">CASEbot / 自我实验</a><span>·</span><a href="https://doi.org/10.1145/3613904.3642140" target="_blank" rel="noreferrer">RASSAR / 空间证据</a><p>本图为 HealthVerse 重新组织与绘制；术语沿用论文机制，版式与文字均非原图复制。</p></div>
          </article>
          <div class="architecture-notes">
            <article class="panel"><span>核心对象</span><h3>Evidence Card</h3><p>每个判断保存来源、置信度、状态、有效期和纠正历史。</p></article>
            <article class="panel"><span>主动策略</span><h3>Observe / Ask / Act</h3><p>高置信度给轻量提示；低置信度先求证；高打断成本保持静默。</p></article>
            <article class="panel"><span>闭环边界</span><h3>Verify before Memory</h3><p>只有现实执行结果和用户确认，才能更新个人模型。</p></article>
          </div>
        </section>

        <section class="view" data-screen="research" aria-labelledby="researchTitle">
          <div class="screen-head"><div><span class="eyebrow">COURSE DESIGN FILE</span><h1 id="researchTitle">从人物角色到关键任务，一条可评估的设计链</h1><p>课程要求已经落实到三类角色、情境剧本、核心需求与可点击任务路径。</p></div><span class="status-pill complete"><i></i>课程要素已覆盖</span></div>
          <div class="research-stack">
            <section class="panel section-block"><div class="section-heading"><div><span class="eyebrow">PERSONAS</span><h2>三类关键人物角色</h2></div><p>从用户片段聚类为行为变量，再形成可用于设计决策的人物角色。</p></div>
              <div class="persona-grid">
                <button class="persona-card" data-persona="student" type="button"><div class="portrait portrait-student" aria-label="林然的人物照片（情境化虚构角色）"><span></span><small>虚构角色照片</small></div><div><span>主要角色</span><h3>林然 · 21 岁</h3><p>大学生 / 长时屏幕学习</p><ul><li>目标：减少打断，保持专注</li><li>痛点：统一标准忽略任务情境</li></ul></div><b>查看详情</b></button>
                <button class="persona-card" data-persona="designer" type="button"><div class="portrait portrait-designer" aria-label="陈曦的人物照片（情境化虚构角色）"><span></span><small>虚构角色照片</small></div><div><span>次要角色</span><h3>陈曦 · 31 岁</h3><p>交互设计师 / 混合办公</p><ul><li>目标：快速比较多个布局</li><li>痛点：建议缺少可视证据</li></ul></div><b>查看详情</b></button>
                <button class="persona-card" data-persona="older" type="button"><div class="portrait portrait-older" aria-label="周岚的人物照片（情境化虚构角色）"><span></span><small>虚构角色照片</small></div><div><span>边缘角色</span><h3>周岚 · 63 岁</h3><p>退休教师 / 肩部活动受限</p><ul><li>目标：常用物品轻松可达</li><li>痛点：默认人体模型不适用</li></ul></div><b>查看详情</b></button>
              </div>
            </section>

            <section class="panel section-block evidence-chain"><div class="section-heading"><div><span class="eyebrow">FRAGMENTS → PERSONAS</span><h2>人物角色形成的中间步骤</h2></div><p>以下为课程原型使用的示意性研究材料，并非真实被试结论。</p></div>
              <div class="chain-grid">
                <article><span>观察片段</span><p>“写论文时我不想被频繁提醒，但停下来喝水时可以提醒。”</p><small>学习情境访谈 · F03</small></article><em>→</em>
                <article><span>行为变量</span><p>提醒时机敏感度高；重视任务连续性；愿意在自然停顿时接收建议。</p><small>变量：打断容忍度 / 自主性</small></article><em>→</em>
                <article><span>模式聚类</span><p>长时屏幕任务 + 低打断偏好 + 需要证据后决策。</p><small>聚类 A：情境型学习者</small></article><em>→</em>
                <article><span>角色结论</span><p>主要人物角色“林然”：AI 应先理解任务，再在合适时机求证。</p><small>指导实时感知页设计</small></article>
              </div>
            </section>

            <section class="panel section-block scenario-block"><div class="section-heading"><div><span class="eyebrow">SCENARIO → NEEDS</span><h2>关键情境场景剧本</h2></div><button class="secondary-btn" id="playScenario" type="button">播放场景</button></div>
              <div class="scenario-grid">
                <div class="storyboard" id="storyboard">
                  <article class="active"><span>1</span><div class="story-icon">◫</div><b>持续学习</b><p>林然在书房完成论文，系统先识别当前任务。</p></article>
                  <article><span>2</span><div class="story-icon">⌁</div><b>发现不确定性</b><p>出现颈部前倾，但 AI 不直接判定为错误。</p></article>
                  <article><span>3</span><div class="story-icon">◎</div><b>主动求证</b><p>系统请求侧面视角，并展示判断依据。</p></article>
                  <article><span>4</span><div class="story-icon">◇</div><b>共同选择</b><p>用户比较方案、调整参数并决定执行。</p></article>
                  <article><span>5</span><div class="story-icon">✓</div><b>验证与学习</b><p>短时实验后由用户确认是否更新记忆。</p></article>
                </div>
                <aside class="needs"><h3>由场景发现的核心需求</h3><ul><li><b>情境理解</b><span>结合任务、时间与用户意愿解释行为</span></li><li><b>证据透明</b><span>能查看、纠正 AI 的视觉依据</span></li><li><b>方案可控</b><span>支持比较、撤销和手动调节</span></li><li><b>结论克制</b><span>区分短期体验与长期健康收益</span></li><li><b>记忆主权</b><span>允许查看、修改与删除个人模型</span></li></ul></aside>
              </div>
            </section>

            <section class="panel section-block"><div class="section-heading"><div><span class="eyebrow">KEY TASK PATH</span><h2>关键任务执行路径</h2></div><p>原型中的主按钮、菜单和结果状态均可点击。</p></div>
              <div class="task-flow detailed"><button data-go="sense" type="button"><i>01</i><b>进入“实时空间感知”</b><span>结果：显示人–物关系</span></button><em></em><button data-go="sense" type="button"><i>02</i><b>点击“显示器 / 视觉证据”</b><span>结果：查看依据并纠正 AI</span></button><em></em><button data-go="design" type="button"><i>03</i><b>点击“生成调整预览”</b><span>结果：比较方案 A / B</span></button><em></em><button data-go="experiment" type="button"><i>04</i><b>选择方案并开始验证</b><span>结果：得到短时对比</span></button><em></em><button data-go="memory" type="button"><i>05</i><b>确认保存个人偏好</b><span>结果：可撤销地更新记忆</span></button></div>
            </section>

            <section class="principle-grid">
              <article class="panel"><span>概念模型</span><h3>AI 是协作者，不是裁判</h3><p>系统观察、推断、求证；用户拥有最后决定权。</p></article>
              <article class="panel"><span>可用性</span><h3>状态始终可见</h3><p>感知、推断、等待确认和实验状态均有明确反馈。</p></article>
              <article class="panel"><span>情感化</span><h3>减少焦虑与道德评判</h3><p>用“可能”“待确认”替代绝对化健康诊断。</p></article>
              <article class="panel"><span>社会责任</span><h3>健康数据由用户控制</h3><p>提供暂停、纠正、撤销、导出和删除入口。</p></article>
            </section>
          </div>
        </section>
      </main>
    </div>
  </div>

  <div class="modal-backdrop" id="modalBackdrop" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <button class="modal-close" id="modalClose" type="button" aria-label="关闭">×</button>
      <div id="modalBody"></div>
    </section>
  </div>
  <div class="toast" id="toast" role="status" aria-live="polite"></div>

  <script src="${pageContext.request.contextPath}/assets/js/healthverse.js"></script>
</body>
</html>
