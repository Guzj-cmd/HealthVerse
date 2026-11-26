(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const appContext = document.querySelector('meta[name="app-context"]')?.content?.replace(/\/$/, '') || '';

  const labels = {
    sense: '实时空间感知',
    body: '个人身体模型',
    design: '环境协同设计',
    experiment: '健康自我实验',
    memory: '个人健康记忆',
    research: '课程设计档案'
  };

  const state = {
    view: 'sense',
    paused: false,
    selectedPlan: 'a',
    tourIndex: -1,
    experimentPhase: 'ready',
    appliedPlan: false,
    timerSeconds: 180,
    timerHandle: null,
    storyboardHandle: null,
    lastFocus: null,
    mediaStream: null,
    mediaObjectUrl: null,
    visionRaf: null,
    poseLandmarker: null,
    poseModelPromise: null,
    visionModulePromise: null,
    visionFilesetPromise: null,
    objectDetector: null,
    objectModelPromise: null,
    objectTracker: null,
    lastObjectInferenceAt: 0,
    objectDetections: [],
    latestLandmarks: null,
    spatialRelations: [],
    spatialRuntime: null,
    spatialRuntimePromise: null,
    temporalTracker: null,
    temporalSnapshot: null,
    latestPosture: null,
    sessionStartedAt: null,
    calibrationSamples: [],
    pendingCalibration: null,
    experimentBaseline: null,
    experimentCandidateStart: null,
    experimentResult: null,
    sessionCorrections: [],
    federatedBackend: null,
    localProfile: null,
    visionMode: null,
    visionLabel: null,
    visionSessionToken: 0,
    lastVideoTime: -1,
    lastInferenceAt: 0,
    inferenceFrames: 0,
    inferenceWindowStarted: 0,
    postureModel: null,
    postureRuntime: null,
    postureModelPromise: null,
    postureCandidate: null,
    postureCandidateSince: 0,
    lastPostureInferenceAt: 0
  };

  const crumb = $('#crumb');
  const mainContent = $('#mainContent');
  const toastNode = $('#toast');
  const modalBackdrop = $('#modalBackdrop');
  const modalBody = $('#modalBody');
  const modalClose = $('#modalClose');
  const startCameraBtn = $('#startCameraBtn');
  const videoFileInput = $('#videoFileInput');
  const stopSourceBtn = $('#stopSourceBtn');
  const visionVideo = $('#visionVideo');
  const visionCanvas = $('#visionCanvas');
  const liveVisionStage = $('#liveVisionStage');
  const scenePlaceholder = $('#scenePlaceholder');
  const sourceStatus = $('#sourceStatus');

  const POSTURE_LABELS = {
    TUP: '躯干中性', TLF: '躯干前倾', TLB: '躯干后倾', TLL: '躯干左倾', TLR: '躯干右倾',
    LAP: '双腿分开', LWA: '双腿宽开', LCS: '双腿合拢', LCR: '右腿交叉',
    LCL: '左腿交叉', LLR: '双腿偏右', LLL: '双腿偏左'
  };

  const POSTURE_GUIDANCE = {
    TLF: '如果这个前倾不是当前任务所需，可以让背部稍作支撑或把内容移近；也可以忽略。',
    TLB: '如果后倾影响当前操作，可以轻微调整椅背或桌面距离；也可以保持现状。',
    TLL: '左倾已持续出现，可以尝试把常用物品移近身体中线；先确认是否由任务造成。',
    TLR: '右倾已持续出现，可以尝试把常用物品移近身体中线；先确认是否由任务造成。'
  };

  const MIN_PHASE_EVIDENCE_MS = 5000;

  const PROFILE_STORAGE_KEY = 'healthverse.profile.v1';

  function emptyLocalProfile() {
    return {
      schema: 'healthverse.local-profile.v1',
      privacy: { saveExperiments: true, personalization: true, federatedOptIn: false },
      calibration: null,
      memories: [],
      experiments: [],
      updatedAt: null
    };
  }

  function loadLocalProfile() {
    try {
      const parsed = JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) || 'null');
      if (parsed?.schema !== 'healthverse.local-profile.v1') return emptyLocalProfile();
      return {
        ...emptyLocalProfile(), ...parsed,
        privacy: { ...emptyLocalProfile().privacy, ...(parsed.privacy || {}) },
        memories: Array.isArray(parsed.memories) ? parsed.memories : [],
        experiments: Array.isArray(parsed.experiments) ? parsed.experiments : []
      };
    } catch (error) {
      return emptyLocalProfile();
    }
  }

  function persistLocalProfile() {
    if (!state.localProfile) return;
    state.localProfile.updatedAt = new Date().toISOString();
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(state.localProfile));
    renderMemories();
  }

  function addConfirmedMemory(title, source, detail) {
    if (!state.localProfile?.privacy.personalization) return;
    const id = `memory-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    state.localProfile.memories.push({ id, title, source, detail, enabled: true, createdAt: new Date().toISOString() });
    persistLocalProfile();
  }

  function renderMemories() {
    const container = $('#memoryItems');
    if (!container || !state.localProfile) return;
    const memories = state.localProfile.memories;
    updateVisionMetric('#memoryCount', `已保存 ${memories.length} 条`);
    renderPersonalModelSummary();
    if (!memories.length) {
      container.innerHTML = '<p class="empty-memory">尚无经用户确认的个人记忆。</p>';
      return;
    }
    container.innerHTML = memories.map((memory) => `
      <div class="memory-item" data-memory-id="${escapeHtml(memory.id)}">
        <div><b>${escapeHtml(memory.title)}</b><small>${escapeHtml(memory.source)} · ${memory.enabled ? '已启用' : '已停用'}</small></div>
        <button class="toggle ${memory.enabled ? 'on' : ''}" data-memory-toggle="${escapeHtml(memory.id)}" type="button" aria-label="${memory.enabled ? '停用' : '启用'}该记忆"><i></i></button>
        <button class="delete-memory" data-memory-delete="${escapeHtml(memory.id)}" type="button">删除</button>
      </div>`).join('');
  }

  function renderPersonalModelSummary() {
    if (!state.localProfile) return;
    const calibration = state.localProfile.calibration;
    const enabledMemories = state.localProfile.memories.filter((memory) => memory.enabled).length;
    const latestExperiment = state.localProfile.experiments.at?.(-1)
      || state.localProfile.experiments[state.localProfile.experiments.length - 1];
    updateVisionMetric('#profileGraphCalibration', calibration ? `${calibration.sampleCount} 次校准` : '尚未校准');
    updateVisionMetric('#profileGraphTask', state.sessionStartedAt ? '当前视觉会话' : '尚未确认');
    updateVisionMetric('#profileGraphEnvironment', state.objectDetections.length ? `${state.objectDetections.length} 个物体` : '等待输入');
    updateVisionMetric('#profileGraphMemories', `${enabledMemories} 条启用`);
    updateVisionMetric('#profileGraphExperiment', latestExperiment?.evidenceStatus === 'qualified'
      ? `舒适度 ${latestExperiment.comfort}/10`
      : (latestExperiment ? '证据不足记录' : '尚无记录'));
    if (calibration) {
      updateVisionMetric('#comfortReachLabel', `舒适范围 · ${calibration.sampleCount} 次采集`);
      updateVisionMetric('#extendedReachLabel', '扩展范围 · 仅作比例预览');
    } else {
      updateVisionMetric('#comfortReachLabel', '舒适范围待校准');
      updateVisionMetric('#extendedReachLabel', '扩展范围待校准');
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[character]);
  }

  let toastTimeout;
  function toast(message, duration = 2600) {
    if (!toastNode) return;
    window.clearTimeout(toastTimeout);
    toastNode.textContent = message;
    toastNode.classList.add('show');
    toastTimeout = window.setTimeout(() => toastNode.classList.remove('show'), duration);
  }

  const POSE_CONNECTIONS = [
    [0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],
    [11,12],[11,13],[13,15],[15,17],[15,19],[15,21],[17,19],
    [12,14],[14,16],[16,18],[16,20],[16,22],[18,20],[11,23],[12,24],
    [23,24],[23,25],[25,27],[27,29],[29,31],[27,31],
    [24,26],[26,28],[28,30],[30,32],[28,32]
  ];

  function setSourceStatus(text, mode = 'idle') {
    if (!sourceStatus) return;
    sourceStatus.textContent = text;
    sourceStatus.dataset.state = mode;
  }

  function updateVisionMetric(id, text) {
    const node = $(id);
    if (node) node.textContent = text;
  }

  function updateAgentStatus(summary, detail) {
    updateVisionMetric('#agentStatusSummary', summary);
    updateVisionMetric('#agentStatusDetail', detail);
  }

  async function ensureVisionRuntime() {
    try {
      if (!state.visionModulePromise) {
        state.visionModulePromise = import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/+esm');
      }
      const visionModule = await state.visionModulePromise;
      if (!state.visionFilesetPromise) {
        state.visionFilesetPromise = visionModule.FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm'
        );
      }
      return { visionModule, vision: await state.visionFilesetPromise };
    } catch (error) {
      state.visionModulePromise = null;
      state.visionFilesetPromise = null;
      throw error;
    }
  }

  async function ensureSpatialRuntime() {
    if (state.spatialRuntime) return state.spatialRuntime;
    if (!state.spatialRuntimePromise) {
      const runtimeUrl = appContext ? `${appContext}/assets/js/spatial-inference.mjs` : './spatial-inference.mjs';
      state.spatialRuntimePromise = import(runtimeUrl).then((runtime) => {
        state.spatialRuntime = runtime;
        state.temporalTracker = new runtime.TemporalEvidenceTracker();
        state.objectTracker = new runtime.ObjectEvidenceTracker({ minimumHits: 2, ttlMs: 1800 });
        return runtime;
      });
    }
    return state.spatialRuntimePromise;
  }

  async function ensurePoseLandmarker() {
    if (state.poseLandmarker) return state.poseLandmarker;
    if (state.poseModelPromise) return state.poseModelPromise;
    state.poseModelPromise = (async () => {
      const { visionModule, vision } = await ensureVisionRuntime();
      const options = {
        baseOptions: {
          modelAssetPath: `${appContext}/assets/models/mediapipe/pose_landmarker_lite.task`,
          delegate: 'GPU'
        },
        runningMode: 'VIDEO',
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
        minPosePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5
      };
      try {
        state.poseLandmarker = await visionModule.PoseLandmarker.createFromOptions(vision, options);
      } catch (gpuError) {
        delete options.baseOptions.delegate;
        state.poseLandmarker = await visionModule.PoseLandmarker.createFromOptions(vision, options);
      }
      return state.poseLandmarker;
    })();
    try {
      return await state.poseModelPromise;
    } catch (error) {
      state.poseModelPromise = null;
      throw error;
    }
  }

  async function ensureObjectDetector() {
    if (state.objectDetector) return state.objectDetector;
    if (state.objectModelPromise) return state.objectModelPromise;
    state.objectModelPromise = (async () => {
      const { visionModule, vision } = await ensureVisionRuntime();
      const options = {
        baseOptions: {
          modelAssetPath: `${appContext}/assets/models/mediapipe/efficientdet_lite0.tflite`
        },
        runningMode: 'VIDEO',
        maxResults: 12,
        scoreThreshold: 0.18,
        categoryAllowlist: [
          'tv', 'laptop', 'chair', 'dining table', 'keyboard', 'mouse', 'cup', 'bottle', 'book', 'cell phone',
          'remote', 'backpack', 'handbag', 'couch', 'bed', 'clock', 'potted plant'
        ]
      };
      state.objectDetector = await visionModule.ObjectDetector.createFromOptions(vision, options);
      return state.objectDetector;
    })();
    try {
      return await state.objectModelPromise;
    } catch (error) {
      state.objectModelPromise = null;
      throw error;
    }
  }

  async function ensurePostureClassifier() {
    if (state.postureModel && state.postureRuntime) return state.postureModel;
    if (state.postureModelPromise) return state.postureModelPromise;
    const runtimeUrl = appContext ? `${appContext}/assets/js/posture-inference.mjs` : './posture-inference.mjs';
    const modelUrl = `${appContext}/assets/models/posture-classifiers-v1.json`;
    state.postureModelPromise = Promise.all([
      import(runtimeUrl),
      fetch(modelUrl).then((response) => {
        if (!response.ok) throw new Error(`model HTTP ${response.status}`);
        return response.json();
      })
    ]).then(([runtime, artifact]) => {
      state.postureRuntime = runtime;
      state.postureModel = artifact;
      updateVisionMetric('#modelEvidence', `真实模型 ${artifact.version} · 已加载`);
      return artifact;
    }).catch((error) => {
      state.postureModelPromise = null;
      updateVisionMetric('#modelEvidence', '真实姿态模型 · 加载失败');
      throw error;
    });
    return state.postureModelPromise;
  }

  function resetPostureInference() {
    state.postureCandidate = null;
    state.postureCandidateSince = 0;
    state.lastPostureInferenceAt = 0;
    updateVisionMetric('#confidenceText', '—');
    const bar = $('#confidenceBar');
    if (bar) bar.style.width = '0%';
    state.latestPosture = null;
  }

  function formatDuration(milliseconds) {
    const seconds = Math.max(0, Math.round((milliseconds || 0) / 1000));
    if (seconds < 60) return `${seconds}秒`;
    return `${Math.floor(seconds / 60)}分${String(seconds % 60).padStart(2, '0')}秒`;
  }

  function updateTemporalEvidence(label, confidence, timestamp) {
    if (!state.temporalTracker) return;
    state.temporalSnapshot = state.temporalTracker.update(label, confidence, timestamp);
    const current = state.temporalSnapshot.current;
    const total = state.temporalSnapshot.totals[label] || 0;
    updateVisionMetric('#temporalMetric', current
      ? `${POSTURE_LABELS[current.label] || current.label}持续 ${formatDuration(current.durationMs)}`
      : '时序事件等待中');
    updateVisionMetric('#sessionBehavior', `${POSTURE_LABELS[label] || label}累计 ${formatDuration(total)}`);
    if (state.sessionStartedAt) {
      updateVisionMetric('#taskDuration', `当前会话：${formatDuration(Date.now() - state.sessionStartedAt)}`);
    }
    updateVisionMetric('#interruptReason', current && current.durationMs >= 5000
      ? `“${POSTURE_LABELS[current.label] || current.label}”已持续 ${formatDuration(current.durationMs)}，此时显示一条可忽略建议。`
      : '尚未达到持续触发阈值，不打断当前任务。');
  }

  function applyPostureInference(landmarks, timestamp) {
    if (!state.postureModel || !state.postureRuntime || timestamp - state.lastPostureInferenceAt < 250) return;
    state.lastPostureInferenceAt = timestamp;
    const prediction = state.postureRuntime.classifyPose(state.postureModel, landmarks);
    const upper = prediction.upper;
    const lower = prediction.lower;
    state.latestPosture = { upper, lower, at: Date.now() };
    updateTemporalEvidence(upper.label, upper.confidence, timestamp);
    const confidence = Math.round(upper.confidence * 100);
    updateVisionMetric('#confidenceText', `${confidence}%`);
    const bar = $('#confidenceBar');
    if (bar) bar.style.width = `${confidence}%`;
    updateVisionMetric('#modelEvidence', `${POSTURE_LABELS[upper.label] || upper.label} ${confidence}% · 下身：${POSTURE_LABELS[lower.label] || lower.label}`);

    if (upper.confidence < prediction.confidenceThreshold) {
      state.postureCandidate = null;
      state.postureCandidateSince = 0;
      $('#agentFinding').textContent = '模型正在等待更多证据';
      $('#agentReason').textContent = '当前分类置信度不足，因此不生成姿态建议。可以继续活动或调整摄像头视角。';
      updateAgentStatus('收集证据', '当前模型置信度未达到部署阈值');
      return;
    }
    if (upper.label === 'TUP') {
      state.postureCandidate = null;
      state.postureCandidateSince = 0;
      $('#agentFinding').textContent = '当前躯干关系较稳定';
      $('#agentReason').textContent = `真实训练模型识别为“${POSTURE_LABELS[upper.label]}”（${confidence}%）。姿态变化本身是正常的，系统不会要求你始终保持同一姿势。`;
      updateAgentStatus('保持观察', '当前无需生成姿态建议');
      return;
    }
    if (state.postureCandidate !== upper.label) {
      state.postureCandidate = upper.label;
      state.postureCandidateSince = timestamp;
    }
    const sustained = (timestamp - state.postureCandidateSince) / 1000;
    if (sustained < 5) {
      $('#agentFinding').textContent = `正在确认“${POSTURE_LABELS[upper.label]}”是否持续`;
      $('#agentReason').textContent = `真实模型置信度 ${confidence}%，已持续 ${sustained.toFixed(1)} / 5.0 秒。按照 CHI 的低打扰反馈方法，单帧或短暂动作不会触发建议。`;
      updateAgentStatus('低打扰等待', `持续 ${sustained.toFixed(1)} / 5.0 秒，尚未触发`);
      return;
    }
    $('#agentFinding').textContent = `${POSTURE_LABELS[upper.label]}已持续 5 秒`;
    $('#agentReason').textContent = `${POSTURE_GUIDANCE[upper.label]} 这是基于关键点关系的非医疗建议，原始画面仍只在本机处理。`;
    updateAgentStatus('建议可用', '已有姿态置信度与持续时间证据');
  }

  function renderObjects(context, width, height) {
    if (!context || !state.objectDetections.length || $('#scene')?.classList.contains('hide-objects')) return;
    context.save();
    context.font = `${Math.max(14, Math.round(width / 70))}px "Microsoft YaHei", sans-serif`;
    context.textBaseline = 'top';
    state.objectDetections.forEach((item, index) => {
      const x = item.box.x * width;
      const y = item.box.y * height;
      const boxWidth = item.box.width * width;
      const boxHeight = item.box.height * height;
      const label = `${item.label} ${Math.round(item.score * 100)}%`;
      context.strokeStyle = index % 2 ? '#a69bc1' : '#91a9d0';
      context.fillStyle = 'rgba(251, 248, 241, .92)';
      context.lineWidth = Math.max(2, width / 500);
      context.setLineDash(index % 2 ? [9, 5] : [15, 4, 3, 4]);
      context.strokeRect(x, y, boxWidth, boxHeight);
      const textWidth = context.measureText(label).width + 14;
      const textY = Math.max(0, y - 24);
      context.fillRect(x, textY, textWidth, 23);
      context.fillStyle = '#171717';
      context.fillText(label, x + 7, textY + 3);
    });
    context.restore();
  }

  function updateSpatialEvidence() {
    if (!state.spatialRuntime) return;
    const objectsCopy = state.objectDetections;
    updateVisionMetric('#objectMetric', objectsCopy.length
      ? `物体 ${objectsCopy.length}：${state.spatialRuntime.summarizeObjects(objectsCopy)}`
      : '支持的工作区物体 0');
    state.spatialRelations = state.latestLandmarks
      ? state.spatialRuntime.inferSpatialRelations(state.latestLandmarks, objectsCopy)
      : [];
    const review = state.spatialRelations.find((item) => item.severity === 'review');
    const relation = review || state.spatialRelations[0];
    updateVisionMetric('#relationMetric', relation ? relation.label : '等待人–物关系');
    updateVisionMetric('#spatialSummary', relation ? relation.label : '尚未建立关系');
    updateVisionMetric('#spatialSummaryDetail', relation
      ? `${relation.evidence}；置信度 ${Math.round(relation.confidence * 100)}%`
      : '需要同时看到人体和支持的工作区物体');
    if (review && (!state.latestPosture || state.latestPosture.upper.label === 'TUP')) {
      $('#agentFinding').textContent = review.label;
      $('#agentReason').textContent = `${review.evidence}。${review.recommendation} 这是二维单目证据，不声称真实厘米距离。`;
      updateAgentStatus('请求确认', '已形成二维人–物关系证据');
    }
    renderPersonalModelSummary();
  }

  function setLiveStage(active) {
    if (liveVisionStage) liveVisionStage.hidden = !active;
    if (scenePlaceholder) scenePlaceholder.hidden = active;
    $('#scene')?.classList.toggle('has-live-input', active);
    if (stopSourceBtn) stopSourceBtn.disabled = !active;
    if (startCameraBtn) startCameraBtn.setAttribute('aria-pressed', String(active && state.visionMode === 'camera'));
    const objectOverlay = $('[data-overlay="objects"]');
    if (objectOverlay) {
      objectOverlay.disabled = false;
      objectOverlay.title = active ? '显示或隐藏 EfficientDet 真实检测框' : '';
    }
  }

  function resetVisionMetrics() {
    updateVisionMetric('#poseMetric', '等待人体');
    updateVisionMetric('#neckMetric', '头颈偏移 —');
    updateVisionMetric('#shoulderMetric', '肩线角度 —');
    updateVisionMetric('#visionPoseMetric', '姿态关键点 —');
    updateVisionMetric('#visionFpsMetric', '分析帧率 —');
    updateVisionMetric('#objectMetric', '工作区物体 —');
    updateVisionMetric('#relationMetric', '等待人–物关系');
    updateVisionMetric('#temporalMetric', '时序事件等待中');
  }

  function stopVisionInput({ announce = true } = {}) {
    state.visionSessionToken += 1;
    if (state.visionRaf) cancelAnimationFrame(state.visionRaf);
    state.visionRaf = null;
    if (visionVideo) {
      visionVideo.pause();
      visionVideo.srcObject = null;
      visionVideo.removeAttribute('src');
      visionVideo.controls = false;
      visionVideo.load();
    }
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
    if (state.mediaObjectUrl) {
      URL.revokeObjectURL(state.mediaObjectUrl);
      state.mediaObjectUrl = null;
    }
    if (visionCanvas) {
      const context = visionCanvas.getContext('2d');
      context?.clearRect(0, 0, visionCanvas.width, visionCanvas.height);
    }
    state.visionMode = null;
    state.visionLabel = null;
    state.paused = false;
    state.lastVideoTime = -1;
    state.inferenceFrames = 0;
    state.lastObjectInferenceAt = 0;
    state.objectDetections = [];
    state.objectTracker?.reset();
    state.latestLandmarks = null;
    state.spatialRelations = [];
    if (state.temporalTracker) {
      state.temporalTracker.close(performance.now());
      state.temporalSnapshot = state.temporalTracker.snapshot(performance.now());
    }
    resetPostureInference();
    setLiveStage(false);
    resetVisionMetrics();
    updateVisionMetric('#visionSourceMetric', '尚未启用视觉输入');
    updateVisionMetric('#visionSummary', '等待连接');
    updateVisionMetric('#visionSummaryDetail', '启用摄像头或导入视频后开始本地分析');
    updateVisionMetric('#modelEvidence', state.postureModel ? `真实模型 ${state.postureModel.version} · 等待视觉输入` : '真实姿态模型 · 等待视觉输入');
    setSourceStatus('等待真实输入 · 本地处理', 'idle');
    $('#scene')?.classList.remove('paused');
    $('.status-pill.live')?.classList.remove('paused');
    if (pauseBtn) {
      pauseBtn.textContent = '暂停分析';
      pauseBtn.setAttribute('aria-pressed', 'false');
      pauseBtn.disabled = true;
    }
    updateVisionMetric('#visionStatusPill', '等待视觉输入');
    updateVisionMetric('#taskDuration', '当前会话：等待真实输入');
    updateAgentStatus('等待证据', '尚未形成建议');
    state.sessionStartedAt = null;
    renderPersonalModelSummary();
    if (videoFileInput) videoFileInput.value = '';
    if (announce) toast('视觉输入已停止，摄像头轨道与视频缓存已释放。');
  }

  function landmarkVisible(landmark) {
    return landmark && (landmark.visibility == null || landmark.visibility > 0.35);
  }

  function midpoint(first, second) {
    return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
  }

  function renderPose(result) {
    if (!visionCanvas || !visionVideo) return;
    const width = visionVideo.videoWidth || 1280;
    const height = visionVideo.videoHeight || 720;
    if (visionCanvas.width !== width || visionCanvas.height !== height) {
      visionCanvas.width = width;
      visionCanvas.height = height;
    }
    const context = visionCanvas.getContext('2d');
    context.clearRect(0, 0, width, height);
    const landmarks = result?.landmarks?.[0];
    if (!landmarks) {
      state.latestLandmarks = null;
      updateVisionMetric('#poseMetric', '画面中未检测到人体');
      updateVisionMetric('#visionPoseMetric', '姿态关键点 0');
      renderObjects(context, width, height);
      updateSpatialEvidence();
      return;
    }
    state.latestLandmarks = landmarks;

    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.strokeStyle = '#91a9d0';
    context.fillStyle = '#fbf8f1';
    context.lineWidth = Math.max(3, width / 360);
    POSE_CONNECTIONS.forEach(([from, to]) => {
      const first = landmarks[from];
      const second = landmarks[to];
      if (!landmarkVisible(first) || !landmarkVisible(second)) return;
      context.beginPath();
      context.moveTo(first.x * width, first.y * height);
      context.lineTo(second.x * width, second.y * height);
      context.stroke();
    });
    landmarks.forEach((landmark) => {
      if (!landmarkVisible(landmark)) return;
      context.beginPath();
      context.arc(landmark.x * width, landmark.y * height, Math.max(3, width / 300), 0, Math.PI * 2);
      context.fill();
      context.stroke();
    });
    renderObjects(context, width, height);

    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];
    const leftEar = landmarks[7];
    const rightEar = landmarks[8];
    const nose = landmarks[0];
    let neckAngle = null;
    let shoulderAngle = null;
    if (landmarkVisible(leftShoulder) && landmarkVisible(rightShoulder)) {
      const shoulders = midpoint(leftShoulder, rightShoulder);
      const head = landmarkVisible(leftEar) && landmarkVisible(rightEar) ? midpoint(leftEar, rightEar) : nose;
      if (landmarkVisible(head)) {
        const dx = Math.abs(head.x - shoulders.x);
        const dy = Math.max(0.001, Math.abs(shoulders.y - head.y));
        neckAngle = Math.round(Math.atan2(dx, dy) * 180 / Math.PI);
      }
      shoulderAngle = Math.round(Math.abs(Math.atan2(rightShoulder.y - leftShoulder.y, rightShoulder.x - leftShoulder.x) * 180 / Math.PI));
    }
    updateVisionMetric('#poseMetric', '已检测 33 个姿态关键点');
    updateVisionMetric('#visionPoseMetric', '姿态关键点 33');
    updateVisionMetric('#visionSummaryDetail', 'MediaPipe 已从当前真实画面检测到人体姿态');
    updateVisionMetric('#neckMetric', neckAngle == null ? '头颈偏移 —' : `头颈偏移 ${neckAngle}°`);
    updateVisionMetric('#shoulderMetric', shoulderAngle == null ? '肩线角度 —' : `肩线角度 ${shoulderAngle}°`);
    applyPostureInference(landmarks, performance.now());
    updateSpatialEvidence();
    if (neckAngle != null && !state.postureModel) {
      $('#agentFinding').textContent = neckAngle >= 12 ? '真实画面中检测到头部相对肩线偏移' : '真实画面中的头肩关系较稳定';
      $('#agentReason').textContent = `当前帧来自${state.visionMode === 'camera' ? '摄像头' : '导入视频'}，MediaPipe 估计头颈偏移约 ${neckAngle}°、肩线约 ${shoulderAngle ?? '—'}°。这是二维姿态线索，不是医疗诊断；你可以暂停、纠正或更换视角。`;
    }
  }

  function visionLoop(timestamp) {
    if (!visionVideo || !state.visionMode) return;
    if (!state.paused && visionVideo.readyState >= 2 && visionVideo.currentTime !== state.lastVideoTime && timestamp - state.lastInferenceAt >= 66) {
      state.lastVideoTime = visionVideo.currentTime;
      state.lastInferenceAt = timestamp;
      if (!state.inferenceWindowStarted) state.inferenceWindowStarted = timestamp;
      if (state.poseLandmarker) {
        try {
          renderPose(state.poseLandmarker.detectForVideo(visionVideo, performance.now()));
          state.inferenceFrames += 1;
          const elapsed = timestamp - state.inferenceWindowStarted;
          if (elapsed >= 1000) {
            updateVisionMetric('#visionFpsMetric', `分析帧率 ${Math.round(state.inferenceFrames * 1000 / elapsed)} fps`);
            state.inferenceFrames = 0;
            state.inferenceWindowStarted = timestamp;
          }
        } catch (error) {
          setSourceStatus('画面播放中 · 姿态分析暂不可用', 'warning');
        }
      }
      if (state.objectDetector && timestamp - state.lastObjectInferenceAt >= 500) {
        state.lastObjectInferenceAt = timestamp;
        try {
          const rawObjects = state.objectDetector.detectForVideo(visionVideo, performance.now());
          const normalizedObjects = state.spatialRuntime
            ? state.spatialRuntime.normalizeDetections(rawObjects, visionVideo.videoWidth, visionVideo.videoHeight, 0.18)
            : [];
          state.objectDetections = state.objectTracker
            ? state.objectTracker.update(normalizedObjects, timestamp)
            : normalizedObjects;
          updateSpatialEvidence();
        } catch (error) {
          console.warn('HealthVerse object inference failed for the current frame.', error);
        }
      }
    }
    state.visionRaf = requestAnimationFrame(visionLoop);
  }

  function beginVision(mode, label) {
    const sessionToken = ++state.visionSessionToken;
    state.visionMode = mode;
    state.visionLabel = label;
    state.paused = false;
    state.lastVideoTime = -1;
    state.inferenceFrames = 0;
    state.inferenceWindowStarted = performance.now();
    state.sessionStartedAt = Date.now();
    state.lastObjectInferenceAt = 0;
    state.objectDetections = [];
    state.spatialRelations = [];
    if (state.temporalTracker) state.temporalTracker.reset();
    setLiveStage(true);
    updateVisionMetric('#visionSourceMetric', label);
    updateVisionMetric('#visionSummary', mode === 'camera' ? '摄像头在线' : '视频已导入');
    updateVisionMetric('#visionSummaryDetail', '画面仅在当前浏览器中处理');
    setSourceStatus(`${label} · 正在加载姿态模型`, 'loading');
    if (pauseBtn) {
      pauseBtn.textContent = '暂停分析';
      pauseBtn.setAttribute('aria-pressed', 'false');
      pauseBtn.disabled = false;
    }
    updateVisionMetric('#visionStatusPill', mode === 'camera' ? '摄像头在线' : '视频分析中');
    updateAgentStatus('分析中', '正在收集姿态、物体关系与持续时间');
    renderPersonalModelSummary();
    if (state.visionRaf) cancelAnimationFrame(state.visionRaf);
    state.visionRaf = requestAnimationFrame(visionLoop);
    ensurePoseLandmarker().then(() => {
      if (state.visionSessionToken !== sessionToken) return;
      setSourceStatus(`${label} · MediaPipe 本地分析中`, 'live');
      toast('真实视觉输入已启用，姿态关键点仅在本机浏览器中处理。', 3600);
    }).catch(() => {
      if (state.visionSessionToken !== sessionToken) return;
      setSourceStatus(`${label} · 视频正常播放，姿态模型加载失败`, 'warning');
      toast('视频输入已启用；姿态模型暂不可用，原始画面仍不会上传。', 3600);
    });
    ensurePostureClassifier().catch(() => {
      toast('MediaPipe 仍可工作，但训练后的姿态分类器没有加载成功。', 3600);
    });
    ensureSpatialRuntime().then(() => ensureObjectDetector()).then(() => {
      if (state.visionSessionToken !== sessionToken) return;
      updateVisionMetric('#objectMetric', 'EfficientDet 已加载，等待物体');
      toast('真实物体检测已启用，检测框与原始画面一样只在浏览器内处理。', 3600);
    }).catch(() => {
      if (state.visionSessionToken !== sessionToken) return;
      updateVisionMetric('#objectMetric', '物体模型加载失败');
      toast('姿态分析仍可使用，物体检测模型暂未加载。', 3600);
    });
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia || !visionVideo) {
      toast('当前浏览器不支持摄像头访问，请改用“导入视频”。', 3600);
      return;
    }
    stopVisionInput({ announce: false });
    setSourceStatus('正在请求摄像头权限…', 'loading');
    if (startCameraBtn) startCameraBtn.disabled = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
      state.mediaStream = stream;
      visionVideo.controls = false;
      visionVideo.srcObject = stream;
      await visionVideo.play();
      beginVision('camera', '摄像头实时画面');
    } catch (error) {
      setSourceStatus('摄像头未启用 · 可导入视频', 'warning');
      toast(error?.name === 'NotAllowedError' ? '未获得摄像头权限，你仍可导入本地视频。' : '摄像头启动失败，请检查设备或改用视频文件。', 3800);
    } finally {
      if (startCameraBtn) startCameraBtn.disabled = false;
    }
  }

  async function importVideo(file) {
    if (!file || !visionVideo) return;
    const supportedExtension = /\.(mp4|webm|mov|m4v|ogv)$/i.test(file.name || '');
    if (!file.type.startsWith('video/') && !supportedExtension) {
      toast('请选择浏览器支持的视频文件。');
      return;
    }
    stopVisionInput({ announce: false });
    const importToken = state.visionSessionToken;
    state.mediaObjectUrl = URL.createObjectURL(file);
    visionVideo.controls = true;
    try {
      const loaded = new Promise((resolve, reject) => {
        visionVideo.addEventListener('loadeddata', resolve, { once: true });
        visionVideo.addEventListener('error', reject, { once: true });
      });
      visionVideo.src = state.mediaObjectUrl;
      visionVideo.load();
      await loaded;
      setLiveStage(true);
      setSourceStatus(`本地视频 · ${file.name} · 正在准备本地分析模型`, 'loading');
      updateVisionMetric('#visionSourceMetric', `本地视频 · ${file.name}`);
      updateVisionMetric('#visionStatusPill', '正在准备分析模型');
      await Promise.allSettled([
        ensurePoseLandmarker(),
        ensurePostureClassifier(),
        ensureSpatialRuntime().then(() => ensureObjectDetector())
      ]);
      if (state.visionSessionToken !== importToken || !state.mediaObjectUrl) return;
      visionVideo.currentTime = 0;
      await visionVideo.play();
      beginVision('file', `本地视频 · ${file.name}`);
    } catch (error) {
      stopVisionInput({ announce: false });
      setSourceStatus('视频无法读取 · 请更换文件', 'warning');
      toast('该视频无法由浏览器播放，请尝试 MP4、WebM 或 MOV。', 3800);
    }
  }

  startCameraBtn?.addEventListener('click', startCamera);
  videoFileInput?.addEventListener('change', () => importVideo(videoFileInput.files?.[0]));
  stopSourceBtn?.addEventListener('click', () => stopVisionInput());
  visionVideo?.addEventListener('ended', () => {
    if (state.visionMode !== 'file') return;
    if (state.visionRaf) cancelAnimationFrame(state.visionRaf);
    state.visionRaf = null;
    state.paused = true;
    setSourceStatus(`${state.visionLabel || '本地视频'} · 播放与分析完成`, 'complete');
    updateVisionMetric('#visionStatusPill', '视频分析完成');
    if (pauseBtn) {
      pauseBtn.textContent = '分析完成';
      pauseBtn.setAttribute('aria-pressed', 'true');
      pauseBtn.disabled = true;
    }
  });

  function showView(view, announce = false) {
    if (!labels[view]) return;
    const commit = () => {
      state.view = view;
      $$('.view').forEach((screen) => {
        const isActive = screen.dataset.screen === view;
        screen.classList.toggle('active', isActive);
        screen.setAttribute('aria-hidden', String(!isActive));
        screen.inert = !isActive;
      });
      $$('.nav-item').forEach((item) => {
        const isActive = item.dataset.view === view;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-current', isActive ? 'page' : 'false');
      });
      if (crumb) crumb.textContent = labels[view];
      if (mainContent) mainContent.scrollTo({ top: 0, behavior: 'auto' });
      document.title = `${labels[view]} · HealthVerse`;
    };
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (document.startViewTransition && !reduceMotion && state.view !== view) {
      document.startViewTransition(commit);
    } else {
      commit();
    }
    if (announce) toast(`已进入「${labels[view]}」`);
  }

  function openModal(content, focusSelector) {
    if (!modalBackdrop || !modalBody) return;
    state.lastFocus = document.activeElement;
    modalBody.innerHTML = content;
    modalBackdrop.hidden = false;
    document.body.classList.add('modal-open');
    requestAnimationFrame(() => {
      modalBackdrop.classList.add('open');
      const target = focusSelector ? $(focusSelector, modalBackdrop) : modalClose;
      target?.focus();
    });
  }

  function closeModal() {
    if (!modalBackdrop || modalBackdrop.hidden) return;
    modalBackdrop.classList.remove('open');
    document.body.classList.remove('modal-open');
    window.setTimeout(() => {
      modalBackdrop.hidden = true;
      modalBody.innerHTML = '';
      state.lastFocus?.focus?.();
    }, 160);
  }

  $$('.nav-item').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view, true)));
  $$('[data-go]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.go, true)));

  $('#helpBtn')?.addEventListener('click', () => openModal(`
    <span class="modal-kicker">ABOUT THE PROTOTYPE</span>
    <h2 id="modalTitle">HealthVerse 的交互原则</h2>
    <p>这是一个面向现实空间的个人健康 AI 工作台概念原型。它把 AI 定位为<strong>可被纠正的协作者</strong>，而不是替用户下诊断的裁判。</p>
    <div class="modal-list">
      <div><b>先理解情境</b><span>结合任务、时间、环境与个人意愿解释行为。</span></div>
      <div><b>让证据可见</b><span>展示观察依据、置信度和仍需确认的信息。</span></div>
      <div><b>把选择权交给人</b><span>方案可比较、可调整、可拒绝、可撤销。</span></div>
      <div><b>克制健康结论</b><span>短时体验不等同于长期健康收益。</span></div>
    </div>
  `));

  async function refreshFederatedStatus() {
    const target = $('#federatedStatus');
    if (!target) return;
    try {
      const response = await fetch(`${appContext}/api/health`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) throw new Error(`health HTTP ${response.status}`);
      const payload = await response.json();
      const federated = payload.federated || {};
      state.federatedBackend = federated;
      if (!federated.configured) {
        target.dataset.state = 'idle';
        target.innerHTML = '<b>协调器未配置</b><span>开关只保存加入意愿；当前不会上传更新。</span><small>部署时设置 HV_FED_STATUS_URL，并在各设备运行独立联邦客户端。</small>';
        return;
      }
      if (!federated.reachable) {
        target.dataset.state = 'warning';
        target.innerHTML = '<b>协调器暂不可达</b><span>没有训练更新从本浏览器发出。</span><small>请检查协调端、TLS 与网络配置。</small>';
        return;
      }
      const multiDevice = federated.runType === 'multi_device_federated_run';
      const privacy = federated.secureAggregation
        ? '协调器报告已启用安全聚合'
        : '协调器可见单个参数更新；不等于安全聚合或差分隐私';
      target.dataset.state = multiDevice ? 'verified' : 'online';
      target.innerHTML = `<b>${multiDevice ? '已验证真实多设备轮次' : '协调器在线 · 尚未验证多设备轮次'}</b>`
        + `<span>第 ${Number(federated.round || 0)} 轮 · 注册 ${Number(federated.registeredClients || 0)} 客户端 · ${Number(federated.distinctDevices || 0)} 个设备指纹</span>`
        + `<small>${escapeHtml(privacy)}；原始画面与关键点不由状态接口上传。</small>`;
    } catch (error) {
      state.federatedBackend = { configured: false, reachable: false, state: 'health_unavailable' };
      target.dataset.state = 'warning';
      target.innerHTML = '<b>无法读取联邦状态</b><span>当前不会上传更新。</span><small>网页后端健康接口不可用。</small>';
    }
  }

  $('#privacyBtn')?.addEventListener('click', () => {
    openModal(`
      <span class="modal-kicker">PRIVACY CONTROL</span>
      <h2 id="modalTitle">你的数据，你来决定</h2>
      <p>摄像头或导入视频只在当前浏览器内处理。停止输入时会立即关闭摄像头轨道并释放本地视频缓存；保存任何实验结论前仍需你的确认。</p>
      <div class="privacy-options">
        <label><span><b>实时画面分析</b><small>仅在当前会话处理</small></span><input id="privacyVision" type="checkbox" checked disabled></label>
        <label><span><b>保存实验结果</b><small>保存前必须由你确认</small></span><input id="privacyExperiments" type="checkbox" ${state.localProfile?.privacy.saveExperiments ? 'checked' : ''}></label>
        <label><span><b>个性化记忆</b><small>可随时停用或删除</small></span><input id="privacyPersonalization" type="checkbox" ${state.localProfile?.privacy.personalization ? 'checked' : ''}></label>
        <label><span><b>联邦训练加入意愿</b><small>默认关闭；保存意愿不等于已上传更新</small></span><input id="privacyFederated" type="checkbox" ${state.localProfile?.privacy.federatedOptIn ? 'checked' : ''}></label>
      </div>
      <div class="federated-status" id="federatedStatus" data-state="loading"><b>正在查询协调器</b><span>等待后端真实状态…</span></div>
      <div class="modal-actions privacy-actions">
        <button class="secondary-btn" data-modal-action="stop-camera" type="button">停止摄像头</button>
        <button class="danger-btn" data-modal-action="delete-session" type="button">删除本次会话数据</button>
      </div>
      <button class="primary-btn wide" data-modal-action="save-privacy" type="button">保存隐私设置</button>
    `);
    refreshFederatedStatus();
  });

  const tourSteps = [
    { view: 'sense', message: '第 1 步：AI 观察现实空间，并说明判断依据。' },
    { view: 'design', message: '第 2 步：比较多个方案，用户仍可拖动参数。' },
    { view: 'experiment', message: '第 3 步：用短时自我实验验证哪种方案更适合。' },
    { view: 'memory', message: '第 4 步：只在用户确认后更新个人健康记忆。' },
    { view: 'research', message: '最后：查看人物角色、情境剧本和关键任务路径。' }
  ];

  $('#tourBtn')?.addEventListener('click', (event) => {
    state.tourIndex = (state.tourIndex + 1) % tourSteps.length;
    const step = tourSteps[state.tourIndex];
    showView(step.view);
    event.currentTarget.textContent = state.tourIndex === tourSteps.length - 1 ? '重新演示' : '下一步';
    toast(step.message, 3600);
  });

  const pauseBtn = $('#pauseBtn');
  pauseBtn?.addEventListener('click', () => {
    state.paused = !state.paused;
    pauseBtn.textContent = state.paused ? '继续分析' : (state.visionMode ? '暂停分析' : '暂停感知');
    pauseBtn.setAttribute('aria-pressed', String(state.paused));
    $('#scene')?.classList.toggle('paused', state.paused);
    $('.status-pill.live')?.classList.toggle('paused', state.paused);
    updateVisionMetric('#visionStatusPill', state.paused ? '分析已暂停' : (state.visionMode === 'camera' ? '摄像头在线' : state.visionMode === 'file' ? '视频分析中' : '等待视觉输入'));
    if (state.visionMode) {
      const label = state.visionMode === 'camera' ? '摄像头实时画面' : '本地视频';
      setSourceStatus(state.paused ? `${label} · 分析已暂停` : `${label} · MediaPipe 本地分析中`, state.paused ? 'paused' : 'live');
    }
    toast(state.paused ? '感知已暂停，画面不会继续分析。' : '已恢复实时空间感知。');
  });

  $$('.toolbar-chip').forEach((button) => button.addEventListener('click', () => {
    button.classList.toggle('active');
    const active = button.classList.contains('active');
    button.setAttribute('aria-pressed', String(active));
    $('#scene')?.classList.toggle(`hide-${button.dataset.overlay}`, !active);
    toast(`${button.textContent.trim()}已${active ? '显示' : '隐藏'}`);
  }));

  const objectCopy = {
    monitor: {
      title: '显示器占位图',
      reason: '这是等待真实输入时的画面示意，不是当前检测结果。启用摄像头或导入视频后，系统才会建立眼部与屏幕的二维关系。'
    },
    cup: {
      title: '水杯位于惯用手一侧',
      reason: '只能比较水杯与手腕在二维画面中的相对距离，单目摄像头不能给出真实厘米。若需要频繁使用，可在预览中将它移近。'
    },
    chair: {
      title: '座椅状态已识别，尚无结论',
      reason: '当前画面能确认座椅与桌面关系，但无法判断坐垫支撑。你可以补充侧面视角，或直接告诉我主观感受。'
    }
  };

  $$('.object-tag').forEach((button) => button.addEventListener('click', () => {
    $$('.object-tag').forEach((tag) => tag.classList.remove('selected'));
    button.classList.add('selected');
    const copy = objectCopy[button.dataset.object];
    if (!state.visionMode) {
      if ($('#agentFinding')) $('#agentFinding').textContent = '占位插图不构成视觉证据';
      if ($('#agentReason')) $('#agentReason').textContent = '当前尚无真实视觉输入，因此这些标签只说明系统支持的物体类型，不代表已经识别你的环境。';
      updateAgentStatus('等待证据', '占位插图未进入 Agent 推理');
      toast('这是占位示意；请先启用摄像头或导入视频。');
      return;
    }
    if ($('#agentFinding')) $('#agentFinding').textContent = copy.title;
    if ($('#agentReason')) $('#agentReason').textContent = copy.reason;
    toast(`已查看${$('span', button)?.textContent || '物体'}与人的空间关系`);
  }));

  const correctionCopy = {
    wrong: ['识别错误', '已标记为识别错误，本次判断不会用于后续方案。'],
    needed: ['任务需要', '已记录：当前姿态由任务需要造成，Agent 将暂缓提醒。'],
    error: ['识别错误', '已标记为识别错误，本次判断不会用于后续方案。'],
    task: ['任务需要', '已记录：当前姿态由任务需要造成，Agent 将暂缓提醒。'],
    mute: ['不再提醒', '本次会话将不再提示这一问题，你可以在隐私控制中恢复。'],
    '识别错误': ['识别错误', '已标记为识别错误，本次判断不会用于后续方案。'],
    '任务需要': ['任务需要', '已记录：当前姿态由任务需要造成，Agent 将暂缓提醒。'],
    '不再提醒': ['不再提醒', '本次会话将不再提示这一问题，你可以在隐私控制中恢复。']
  };

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-correction]');
    if (!button) return;
    const key = button.dataset.correction || button.textContent.trim();
    const copy = correctionCopy[key] || [button.textContent.trim(), '已收到你的纠正。'];
    $$('[data-correction]').forEach((item) => item.classList.toggle('active', item === button));
    button.setAttribute('aria-pressed', 'true');
    $('#agentFinding').textContent = `用户已纠正：${copy[0]}`;
    $('#agentReason').textContent = copy[1];
    state.sessionCorrections.push({
      kind: key,
      posture: state.latestPosture?.upper?.label || null,
      relations: state.spatialRelations.map((item) => item.type),
      createdAt: new Date().toISOString()
    });
    toast(copy[1], 3200);
  });

  $('#evidenceBtn')?.addEventListener('click', () => {
    const hasLiveEvidence = Boolean(state.visionMode);
    const source = state.visionMode === 'camera' ? '实时摄像头' : state.visionMode === 'file' ? '本地视频' : '未连接';
    const objectEvidence = state.objectDetections.length
      ? state.objectDetections.slice(0, 6).map((item) => `${item.label} ${Math.round(item.score * 100)}%`).join('、')
      : '尚未检测到支持的工作区物体';
    const relationEvidence = state.spatialRelations.length
      ? state.spatialRelations.slice(0, 5).map((item) => `${item.label}：${item.evidence}`).join('；')
      : '尚未建立可报告的人–物关系';
    const temporalEvidence = state.temporalSnapshot?.current
      ? `${POSTURE_LABELS[state.temporalSnapshot.current.label] || state.temporalSnapshot.current.label}持续 ${formatDuration(state.temporalSnapshot.current.durationMs)}`
      : '尚未形成持续行为事件';
    const upperEvaluation = state.postureModel?.upper?.evaluation;
    const lowerEvaluation = state.postureModel?.lower?.evaluation;
    const modelEvaluation = upperEvaluation && lowerEvaluation
      ? `上身 Accuracy ${(upperEvaluation.accuracy * 100).toFixed(2)}%、Macro-F1 ${(upperEvaluation.macro_f1 * 100).toFixed(2)}%；下身 Accuracy ${(lowerEvaluation.accuracy * 100).toFixed(2)}%、Macro-F1 ${(lowerEvaluation.macro_f1 * 100).toFixed(2)}%。测试受试者与开发受试者隔离。`
      : '训练分类器尚未加载，不能报告冻结评估。';
    openModal(`
      <span class="modal-kicker">REAL VISUAL EVIDENCE</span>
      <h2 id="modalTitle">当前判断使用了什么真实证据？</h2>
      <div class="evidence-modal">
        <div class="evidence-frame"><span>${hasLiveEvidence ? 'LIVE' : 'NO INPUT'}</span><i class="evidence-line"></i><b>${escapeHtml(source)}</b></div>
        <ol>
          <li><b>输入来源</b><span>${hasLiveEvidence ? `${escapeHtml(source)}，原始画面未上传` : '尚未启用摄像头或导入视频'}</span></li>
          <li><b>姿态检测</b><span>${escapeHtml($('#poseMetric')?.textContent || '无检测结果')}</span></li>
          <li><b>部署模型冻结评估</b><span>${escapeHtml(modelEvaluation)}</span></li>
          <li><b>头肩线索</b><span>${escapeHtml([$('#neckMetric')?.textContent, $('#shoulderMetric')?.textContent].filter(Boolean).join(' · ') || '无检测结果')}</span></li>
          <li><b>真实物体检测</b><span>${escapeHtml(objectEvidence)}</span></li>
          <li><b>人–物关系</b><span>${escapeHtml(relationEvidence)}</span></li>
          <li><b>时序证据</b><span>${escapeHtml(temporalEvidence)}</span></li>
          <li class="uncertain"><b>仍不确定</b><span>${hasLiveEvidence ? '二维单视角不能确认真实厘米距离、深度、力量或长期健康影响' : '没有真实视觉输入时，系统不会声称已经观察你的姿态'}</span></li>
        </ol>
      </div>
      <p class="modal-note">MediaPipe 本地姿态估计 · 可暂停、纠正或立即停止，不是医疗诊断。</p>
    `);
  });

  $('#previewBtn')?.addEventListener('click', () => {
    const screenRelation = state.spatialRelations.find((item) => item.id === 'eye-screen-height');
    if (screenRelation) {
      const offset = Math.abs(screenRelation.measures?.verticalOffsetShoulderWidths || 0);
      planData.a.height = Math.max(4, Math.min(20, Math.round(offset * 10)));
      planData.a.summary = screenRelation.type === 'screen_above_eye' ? '降低屏幕的相对预览' : '抬高屏幕的相对预览';
      selectPlan('a');
      toast(`已使用真实关系证据生成预览：${screenRelation.evidence}。`);
    } else {
      toast('尚未同时检测到眼部与屏幕；已进入手动相对预览，不声称真实厘米调整量。', 3800);
    }
    window.setTimeout(() => showView('design'), 360);
  });

  async function submitAgentPrompt() {
    const input = $('#agentInput');
    const value = input?.value.trim();
    if (!value) {
      input?.focus();
      toast('请先输入你的目标或限制。');
      return;
    }
    const sendButton = $('#sendPrompt');
    const previousLabel = sendButton?.textContent || '发送';
    if (sendButton) {
      sendButton.disabled = true;
      sendButton.textContent = '思考中';
    }
    $('#agentFinding').textContent = 'Agent 正在结合空间证据推理';
    $('#agentReason').textContent = '正在分析你的目标、当前任务和已识别的人–物关系…';
    input.value = '';
    try {
      const response = await fetch(`${appContext}/api/agent`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          message: value,
          context: {
            task: state.sessionStartedAt ? `当前视觉会话已持续 ${formatDuration(Date.now() - state.sessionStartedAt)}` : '当前尚未开始视觉会话',
            visualSource: state.visionMode === 'camera' ? '用户授权的实时摄像头' : state.visionMode === 'file' ? '用户导入的本地视频' : '尚无真实视觉输入',
            observations: state.visionMode ? [
              $('#poseMetric')?.textContent || '姿态检测状态未知',
              $('#neckMetric')?.textContent || '头颈偏移未知',
              $('#shoulderMetric')?.textContent || '肩线角度未知'
            ] : ['尚未启用摄像头或导入视频，不能声称已观察真实姿态'],
            objects: state.objectDetections.map((item) => ({
              type: item.type, label: item.label, confidence: Number(item.score.toFixed(3)), box: item.box
            })),
            spatialRelations: state.spatialRelations.map((item) => ({
              type: item.type, label: item.label, severity: item.severity,
              confidence: Number(item.confidence.toFixed(3)), evidence: item.evidence
            })),
            temporalEvidence: state.temporalSnapshot,
            evidenceBoundary: '二维单目画面不提供真实厘米深度；不得生成医疗诊断',
            userControl: '用户要求方案可比较、可纠正、可撤销'
          }
        })
      });
      if (!response.ok) throw new Error(`Agent request failed: ${response.status}`);
      const payload = await response.json();
      $('#agentFinding').textContent = payload.title || 'Agent 已更新当前推理';
      $('#agentReason').textContent = payload.reply || '已将你的限制加入本次方案。';
      toast('真实 Agent 已返回结合当前空间证据的建议。');
    } catch (error) {
      $('#agentFinding').textContent = '已把你的限制加入当前推理';
      $('#agentReason').textContent = `“${value}” 已记录为本次会话约束。当前使用本地规则推理；生成方案时仍会优先保留你的选择。`;
      toast('Agent 接口暂不可用，已切换到本地规则。');
    } finally {
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.textContent = previousLabel;
      }
    }
  }

  $('#sendPrompt')?.addEventListener('click', submitAgentPrompt);
  $('#agentInput')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') submitAgentPrompt();
  });

  const rangeInput = $('#rangeInput');
  rangeInput?.addEventListener('input', () => {
    const value = Number(rangeInput.value);
    $('#rangeValue').textContent = `${value}%`;
    const scale = 0.76 + (value - 45) / 100;
    $('.field-outer')?.style.setProperty('transform', `translate(-50%, -50%) scale(${scale})`);
  });

  $$('.cal-step').forEach((step) => step.addEventListener('click', () => {
    $$('.cal-step').forEach((item) => item.classList.remove('active'));
    step.classList.add('active');
    toast(`已选择动作：${$('b', step)?.textContent}`);
  }));

  $('#captureBtn')?.addEventListener('click', (event) => {
    const steps = $$('.cal-step');
    const activeIndex = steps.findIndex((item) => item.classList.contains('active'));
    const current = steps[Math.max(0, activeIndex)];
    if (!state.latestLandmarks || !state.spatialRuntime) {
      toast('请先在“实时空间感知”启用摄像头或导入视频，再采集真实关键点。', 3800);
      return;
    }
    const action = $('b', current)?.textContent || `action-${activeIndex + 1}`;
    state.calibrationSamples.push({
      action,
      capturedAt: new Date().toISOString(),
      landmarks: state.latestLandmarks.map((point) => ({
        x: point.x, y: point.y, z: point.z, visibility: point.visibility
      }))
    });
    state.pendingCalibration = state.spatialRuntime.deriveBodyProfile(state.calibrationSamples);
    current?.classList.remove('active');
    current?.classList.add('done');
    const marker = $('i', current);
    if (marker) marker.textContent = '✓';
    const stepDetail = $('small', current);
    if (stepDetail) stepDetail.textContent = '已采集 · 当前真实关键点';
    const next = steps[Math.min(activeIndex + 1, steps.length - 1)];
    if (activeIndex < steps.length - 1) {
      next.classList.add('active');
      toast('动作已采集，继续完成下一项。');
    } else {
      event.currentTarget.textContent = '等待保存确认';
      event.currentTarget.disabled = true;
      const profile = state.pendingCalibration;
      openModal(`
        <span class="modal-kicker">LOCAL BODY CALIBRATION</span>
        <h2 id="modalTitle">保存本地个人校准？</h2>
        <p>已从 ${profile.sampleCount} 次真实 MediaPipe 关键点采集中计算归一化身体比例。原始视频和关键点序列不会写入记忆。</p>
        <div class="modal-list">
          <div><b>肩宽比例</b><span>${profile.shoulderWidthNorm?.toFixed(3) || '无法计算'}</span></div>
          <div><b>左/右手臂触达比例</b><span>${profile.leftReachNorm?.toFixed(3) || '—'} / ${profile.rightReachNorm?.toFixed(3) || '—'}</span></div>
          <div><b>数据位置</b><span>当前浏览器 localStorage</span></div>
        </div>
        <div class="modal-actions"><button class="secondary-btn" data-modal-action="discard-calibration" type="button">不保存</button><button class="primary-btn" data-modal-action="save-calibration" type="button">确认保存</button></div>
      `);
    }
  });

  const planData = {
    a: { label: '方案 A', summary: '仅调整显示器高度', height: 12, angle: 8 },
    b: { label: '方案 B', summary: '显示器升高 + 水杯左移', height: 15, angle: 6 }
  };

  function selectPlan(plan) {
    state.selectedPlan = plan;
    $$('.plan-card').forEach((card) => card.classList.toggle('active', card.dataset.plan === plan));
    const data = planData[plan];
    $('#planLabel').textContent = data.label;
    $('#planSummary').textContent = data.summary;
    $('#heightInput').value = data.height;
    updateMonitorHeight(data.height, data.angle);
  }

  function updateMonitorHeight(value, fixedAngle) {
    const amount = Number(value);
    const angle = fixedAngle ?? Math.max(4, Math.round(22 - amount * 1.15));
    $('#heightValue').textContent = `+${amount}% 画面高度`;
    $('#angleValue').textContent = `偏移级别 ${angle}`;
    $('#compareScene')?.style.setProperty('--monitor-lift', `${amount * 2.1}px`);
  }

  $$('.plan-card').forEach((card) => card.addEventListener('click', () => {
    selectPlan(card.dataset.plan);
    toast(`已切换到${planData[card.dataset.plan].label}`);
  }));

  $('#heightInput')?.addEventListener('input', (event) => updateMonitorHeight(event.currentTarget.value));

  $$('[data-compare]').forEach((button) => button.addEventListener('click', () => {
    $$('[data-compare]').forEach((item) => item.classList.toggle('active', item === button));
    const after = button.dataset.compare === 'after';
    $('#compareScene')?.classList.toggle('after', after);
    $('#compareScene')?.classList.toggle('before', !after);
    toast(after ? '正在查看调整后预览' : '正在查看原始布局');
  }));

  $('#rejectPlan')?.addEventListener('click', () => {
    selectPlan(state.selectedPlan === 'a' ? 'b' : 'a');
    toast('已为你切换到另一个可行方案。');
  });

  $('#editConstraint')?.addEventListener('click', () => openModal(`
    <span class="modal-kicker">EDIT CONSTRAINT</span>
    <h2 id="modalTitle">修改空间限制</h2>
    <p>Agent 会把这条限制用于当前方案生成，但不会覆盖你的长期偏好。</p>
    <label class="modal-field"><span>本次任务限制</span><input id="constraintInput" value="桌面右侧需要保留手写区域"></label>
    <button class="primary-btn wide" data-modal-action="save-constraint" type="button">保存并重新比较</button>
  `, '#constraintInput'));

  $('#applyPlan')?.addEventListener('click', () => {
    state.appliedPlan = true;
    const undo = $('#undoPlan');
    if (undo) {
      undo.hidden = false;
      undo.disabled = false;
    }
    toast(`${planData[state.selectedPlan].label}已选择，接下来进行短时验证。`);
    window.setTimeout(() => showView('experiment'), 360);
  });

  $('#undoPlan')?.addEventListener('click', (event) => {
    state.appliedPlan = false;
    state.experimentPhase = 'ready';
    stopTimer();
    event.currentTarget.hidden = true;
    $('#experimentState') && ($('#experimentState').textContent = '准备阶段');
    if ($('#experimentBtn')) {
      $('#experimentBtn').disabled = false;
        $('#experimentBtn').textContent = '开始记录原始布局基线';
    }
      state.timerSeconds = 180;
      state.experimentBaseline = null;
      state.experimentCandidateStart = null;
      renderTimer();
    toast('已撤销方案，空间与个人记忆均恢复到原始状态。', 3400);
    window.setTimeout(() => showView('design'), 320);
  });

  $('#protocolBtn')?.addEventListener('click', () => openModal(`
    <span class="modal-kicker">EXPERIMENT PROTOCOL</span>
    <h2 id="modalTitle">显示器高度短时对比</h2>
    <div class="modal-list numbered">
      <div><b>1. 基线</b><span>在原始布局下完成 3 分钟相同任务。</span></div>
      <div><b>2. 方案体验</b><span>调整显示器后完成 6 分钟相同任务。</span></div>
      <div><b>3. 指标</b><span>观察姿态变化、触达时间与主观舒适度。</span></div>
      <div><b>4. 用户确认</b><span>AI 只给出比较结果，由你决定是否保存。</span></div>
    </div>
    <p class="modal-note">该实验不能用于证明长期健康收益，也不替代专业医疗建议。</p>
  `));

  function renderTimer() {
    const minutes = Math.floor(state.timerSeconds / 60);
    const seconds = state.timerSeconds % 60;
    $('#timer').textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  function stopTimer() {
    window.clearInterval(state.timerHandle);
    state.timerHandle = null;
  }

  function startExperimentTimer(seconds, onComplete) {
    stopTimer();
    state.timerSeconds = seconds;
    renderTimer();
    state.timerHandle = window.setInterval(() => {
      state.timerSeconds = Math.max(0, state.timerSeconds - 1);
      renderTimer();
      if (state.timerSeconds === 0) {
        stopTimer();
        onComplete();
      }
    }, 1000);
  }

  function temporalRatio(snapshot, baselineTotals = null) {
    const totals = snapshot?.totals || {};
    const entries = Object.entries(totals).map(([label, value]) => [label, Math.max(0, value - (baselineTotals?.[label] || 0))]);
    const total = entries.reduce((sum, item) => sum + item[1], 0);
    const nonNeutral = entries.filter(([label]) => label !== 'TUP').reduce((sum, item) => sum + item[1], 0);
    return { total, nonNeutral, ratio: total > 0 ? nonNeutral / total : null };
  }

  function renderExperimentEvidence(result) {
    const baselinePercent = result.baseline.ratio == null ? null : Math.round(result.baseline.ratio * 100);
    const candidatePercent = result.candidate.ratio == null ? null : Math.round(result.candidate.ratio * 100);
    $('#baselinePostureBar')?.style.setProperty('width', `${baselinePercent || 0}%`);
    $('#candidatePostureBar')?.style.setProperty('width', `${candidatePercent || 0}%`);
    updateVisionMetric('#baselinePostureValue', baselinePercent == null ? '基线：证据不足' : `基线：${baselinePercent}%`);
    updateVisionMetric('#candidatePostureValue', candidatePercent == null ? '方案：证据不足' : `方案：${candidatePercent}%`);
    const relationCount = state.spatialRelations.length;
    $('#relationEvidenceBar')?.style.setProperty('width', `${Math.min(100, relationCount * 18)}%`);
    updateVisionMetric('#relationEvidenceValue', `当前有 ${relationCount} 条真实二维关系证据`);
    if (Number.isFinite(result.comfort)) {
      $('#comfortBar')?.style.setProperty('width', `${result.comfort * 10}%`);
      updateVisionMetric('#comfortValue', `用户评分 ${result.comfort}/10`);
    }
    const note = $('.experiment-note');
    if (note && result.evidenceStatus === 'insufficient') {
      const title = $('strong', note);
      const detail = $('p', note);
      if (title) title.textContent = '视觉时序证据不足';
      if (detail) detail.textContent = `基线与方案阶段各至少需要 ${MIN_PHASE_EVIDENCE_MS / 1000} 秒有效姿态证据；本次记录不会进入个性化偏好记忆。`;
    } else if (note && result.evidenceStatus === 'qualified') {
      const title = $('strong', note);
      const detail = $('p', note);
      if (title) title.textContent = '两个计时阶段均达到证据门槛';
      if (detail) detail.textContent = '结果仍是短时会话证据；是否保存以及如何解释由用户决定。';
    }
  }

  function cloneTemporalSnapshot() {
    return JSON.parse(JSON.stringify(state.temporalSnapshot || { totals: {} }));
  }

  function beginCandidateExperiment() {
    stopTimer();
    const finishedBaseline = cloneTemporalSnapshot();
    const baselineStartTotals = state.experimentBaseline?.startSnapshot?.totals || {};
    state.experimentBaseline.result = temporalRatio(finishedBaseline, baselineStartTotals);
    state.experimentBaseline.finishedAt = new Date().toISOString();
    state.experimentCandidateStart = { snapshot: finishedBaseline, startedAt: new Date().toISOString() };
    state.experimentPhase = 'candidate';
    $('#experimentState').textContent = `正在体验${planData[state.selectedPlan].label}`;
    $('#experimentBtn').textContent = '结束方案体验并填写评分';
    startExperimentTimer(360, finishExperiment);
    toast(`基线阶段已记录；现在开始${planData[state.selectedPlan].label}。`);
  }

  function openComfortRating() {
    openModal(`
      <span class="modal-kicker">SUBJECTIVE RATING</span>
      <h2 id="modalTitle">这次短时体验感受如何？</h2>
      <p>请输入当下主观舒适度。系统不会把这个短时评分解释为长期健康改善。</p>
      <label class="modal-field"><span>舒适度 1–10</span><input id="comfortInput" type="range" min="1" max="10" value="5"></label>
      <button class="primary-btn wide" data-modal-action="record-comfort" type="button">记录评分并查看结果</button>
    `, '#comfortInput');
  }

  function finishExperiment() {
    stopTimer();
    const baselineResult = state.experimentBaseline?.result
      || temporalRatio(state.temporalSnapshot, state.experimentBaseline?.startSnapshot?.totals || {});
    const candidateTotals = state.experimentCandidateStart?.snapshot?.totals || {};
    const baselineEvidence = baselineResult.total || 0;
    const candidateResult = temporalRatio(state.temporalSnapshot, candidateTotals);
    state.experimentResult = {
      id: `experiment-${Date.now()}`,
      plan: state.selectedPlan,
      startedAt: state.experimentBaseline?.startedAt || null,
      finishedAt: new Date().toISOString(),
      baseline: baselineResult,
      candidate: candidateResult,
      relations: state.spatialRelations.map((item) => ({ type: item.type, label: item.label, confidence: item.confidence })),
      comfort: null,
      source: 'live-browser-evidence',
      evidenceStatus: baselineEvidence >= MIN_PHASE_EVIDENCE_MS && candidateResult.total >= MIN_PHASE_EVIDENCE_MS
        ? 'qualified'
        : 'insufficient'
    };
    renderExperimentEvidence(state.experimentResult);
    state.experimentPhase = 'rating';
    $('#experimentState').textContent = '等待主观评分';
    $('#experimentBtn').textContent = '填写舒适度并查看结果';
    openComfortRating();
  }

  $('#experimentBtn')?.addEventListener('click', (event) => {
    if (state.experimentPhase === 'ready') {
      const note = $('.experiment-note');
      if (note) {
        const title = $('strong', note);
        const detail = $('p', note);
        if (title) title.textContent = '等待真实体验记录';
        if (detail) detail.textContent = '启动短时体验后，本页才记录当前会话数据；短期变化不能直接推断长期健康收益。';
      }
      state.experimentPhase = 'baseline';
      $('#experimentState').textContent = '正在记录原始布局基线';
      event.currentTarget.textContent = `结束基线并开始${planData[state.selectedPlan].label}`;
      state.experimentBaseline = { startSnapshot: cloneTemporalSnapshot(), startedAt: new Date().toISOString() };
      state.experimentCandidateStart = null;
      startExperimentTimer(180, beginCandidateExperiment);
      toast('基线记录已开始；请保持与方案阶段相同的任务。');
    } else if (state.experimentPhase === 'baseline') {
      beginCandidateExperiment();
    } else if (state.experimentPhase === 'candidate') {
      finishExperiment();
    } else if (state.experimentPhase === 'rating') {
      openComfortRating();
    } else {
      state.experimentPhase = 'saved';
      event.currentTarget.textContent = '结果已保存';
      event.currentTarget.disabled = true;
      const shouldSave = Boolean(state.localProfile?.privacy.saveExperiments && state.experimentResult);
      if (shouldSave) {
        state.localProfile.experiments.push(state.experimentResult);
        persistLocalProfile();
        if (state.experimentResult.evidenceStatus === 'qualified') {
          addConfirmedMemory(`${planData[state.selectedPlan].label}的短时舒适度 ${state.experimentResult.comfort}/10`, '用户确认的自我实验', '来自两个真实计时阶段的姿态时序与主观评分');
        }
      }
      toast(!shouldSave
        ? '根据你的隐私设置，本次实验没有写入本地存储。'
        : (state.experimentResult?.evidenceStatus === 'qualified'
          ? '已保存证据达标的短时体验记录；你可以在记忆页面停用或删除。'
          : '已保存为证据不足的审计记录，不会写入个性化偏好记忆。'));
      window.setTimeout(() => showView('memory'), 420);
    }
  });

  $('#skipExperiment')?.addEventListener('click', () => {
    stopTimer();
    state.experimentPhase = 'ready';
    state.experimentBaseline = null;
    state.experimentCandidateStart = null;
    state.timerSeconds = 180;
    renderTimer();
    $('#experimentState') && ($('#experimentState').textContent = '准备阶段');
    if ($('#experimentBtn')) $('#experimentBtn').textContent = '开始记录原始布局基线';
    toast('已跳过实验，空间和个人记忆均未改变。');
    window.setTimeout(() => showView('sense'), 360);
  });

  document.addEventListener('click', (event) => {
    const toggleId = event.target.closest('[data-memory-toggle]')?.dataset.memoryToggle;
    const deleteId = event.target.closest('[data-memory-delete]')?.dataset.memoryDelete;
    if (toggleId) {
      const memory = state.localProfile?.memories.find((item) => item.id === toggleId);
      if (!memory) return;
      memory.enabled = !memory.enabled;
      persistLocalProfile();
      toast(`${memory.title}已${memory.enabled ? '启用' : '停用'}。`);
    }
    if (deleteId) {
      const memory = state.localProfile?.memories.find((item) => item.id === deleteId);
      if (!memory) return;
      state.localProfile.memories = state.localProfile.memories.filter((item) => item.id !== deleteId);
      persistLocalProfile();
      toast(`已删除“${memory.title}”。`);
    }
  });

  $('#clearMemory')?.addEventListener('click', () => openModal(`
    <span class="modal-kicker">MEMORY CONTROL</span>
    <h2 id="modalTitle">管理全部记忆</h2>
    <p>停用不会删除记录；清空后无法在此原型中恢复。</p>
    <div class="modal-actions">
      <button class="secondary-btn" data-modal-action="disable-memory" type="button">全部停用</button>
      <button class="danger-btn" data-modal-action="delete-memory" type="button">清空全部记忆</button>
    </div>
  `));

  $('#exportBtn')?.addEventListener('click', () => {
    const payload = {
      product: 'HealthVerse',
      schema: 'healthverse.user-export.v1',
      exportedAt: new Date().toISOString(),
      localProfile: state.localProfile,
      currentSession: {
        startedAt: state.sessionStartedAt ? new Date(state.sessionStartedAt).toISOString() : null,
        source: state.visionMode,
        posture: state.latestPosture,
        objects: state.objectDetections,
        spatialRelations: state.spatialRelations,
        temporalEvidence: state.temporalSnapshot,
        corrections: state.sessionCorrections
      },
      note: '原始视频和完整关键点序列不在此导出中。本系统不提供医疗诊断。'
    };
    const file = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'healthverse-user-data.json';
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    toast('当前会话数据已导出为 JSON 文件。');
  });

  const personaData = {
    student: {
      role: '主要角色', name: '林然', meta: '21 岁 · 大学生 · 长时屏幕学习',
      fragment: '每天在宿舍或书房连续学习 4–6 小时；在意专注，不喜欢被频繁提醒。',
      goal: '在不打断学习节奏的前提下，让桌面更适合自己的任务。',
      need: '情境化提醒、低打扰交互、可视证据、可撤销方案。'
    },
    designer: {
      role: '次要角色', name: '陈曦', meta: '31 岁 · 交互设计师 · 混合办公',
      fragment: '经常在公司和家之间切换，设备和桌面布局不同；重视效率与控制感。',
      goal: '快速比较多个布局方案，并保留手绘和键鼠操作空间。',
      need: '反事实预览、参数调节、任务约束、跨场景记忆。'
    },
    older: {
      role: '边缘角色', name: '周岚', meta: '63 岁 · 退休教师 · 肩部活动受限',
      fragment: '日常使用平板阅读和视频通话；抬臂范围有限，不希望系统替她做决定。',
      goal: '让常用物品处于舒适可达范围，避免使用统一人体模板。',
      need: '自主校准、低负担操作、清晰反馈、隐私与记忆控制。'
    }
  };

  $$('[data-persona]').forEach((button) => button.addEventListener('click', () => {
    const persona = personaData[button.dataset.persona];
    openModal(`
      <span class="modal-kicker">${persona.role}</span>
      <h2 id="modalTitle">${persona.name}</h2>
      <p class="persona-meta">${persona.meta}</p>
      <div class="persona-detail">
        <div><span>用户片段</span><p>${persona.fragment}</p></div>
        <div><span>关键目标</span><p>${persona.goal}</p></div>
        <div><span>设计需求</span><p>${persona.need}</p></div>
      </div>
      <p class="modal-note">人物角色为课程原型中的虚构研究角色，不对应真实个人。</p>
    `);
  }));

  $('#playScenario')?.addEventListener('click', (event) => {
    const cards = $$('#storyboard article');
    window.clearInterval(state.storyboardHandle);
    let index = 0;
    cards.forEach((card, cardIndex) => card.classList.toggle('active', cardIndex === 0));
    event.currentTarget.textContent = '播放中…';
    event.currentTarget.disabled = true;
    state.storyboardHandle = window.setInterval(() => {
      index += 1;
      cards.forEach((card, cardIndex) => card.classList.toggle('active', cardIndex === index));
      if (index >= cards.length - 1) {
        window.clearInterval(state.storyboardHandle);
        event.currentTarget.textContent = '重新播放';
        event.currentTarget.disabled = false;
        toast('场景结束：用户确认后，Agent 才会更新个人模型。');
      }
    }, 900);
  });

  modalClose?.addEventListener('click', closeModal);
  modalBackdrop?.addEventListener('click', (event) => {
    if (event.target === modalBackdrop) closeModal();
  });

  modalBody?.addEventListener('click', (event) => {
    const action = event.target.closest('[data-modal-action]')?.dataset.modalAction;
    if (!action) return;
    if (action === 'save-privacy') {
      state.localProfile.privacy.saveExperiments = Boolean($('#privacyExperiments')?.checked);
      state.localProfile.privacy.personalization = Boolean($('#privacyPersonalization')?.checked);
      state.localProfile.privacy.federatedOptIn = Boolean($('#privacyFederated')?.checked);
      persistLocalProfile();
      toast(state.localProfile.privacy.federatedOptIn
        ? '已保存联邦训练加入意愿；网页没有自动上传任何更新。'
        : '隐私设置已保存，联邦训练保持关闭。');
    }
    if (action === 'stop-camera') {
      stopVisionInput();
    }
    if (action === 'delete-session') {
      stopVisionInput({ announce: false });
      state.appliedPlan = false;
      state.sessionCorrections = [];
      state.temporalTracker?.reset();
      state.temporalSnapshot = null;
      state.objectDetections = [];
      state.spatialRelations = [];
      stopTimer();
      $$('.object-tag').forEach((tag) => tag.classList.remove('selected'));
      $('#agentFinding') && ($('#agentFinding').textContent = '本次会话数据已删除');
      $('#agentReason') && ($('#agentReason').textContent = '视觉观察、临时约束和未确认结果已清除。长期记忆未受影响。');
      toast('本次会话数据已删除。');
    }
    if (action === 'save-constraint') {
      const value = $('#constraintInput')?.value.trim();
      const copy = $('.constraint p');
      if (value && copy) copy.textContent = `“${value}”`;
      toast('限制已更新，两个方案已重新比较。');
    }
    if (action === 'save-calibration') {
      state.localProfile.calibration = state.pendingCalibration;
      state.pendingCalibration = null;
      state.calibrationSamples = [];
      persistLocalProfile();
      const button = $('#captureBtn');
      if (button) button.textContent = '校准已保存';
      updateVisionMetric('#calibrationSummary', '已本地校准');
      updateVisionMetric('#calibrationDetail', `${state.localProfile.calibration.sampleCount} 次真实关键点采集，仅保存归一化比例`);
      addConfirmedMemory('个人活动范围已校准', '用户确认的本地校准', '仅保存归一化比例，不保存原始画面');
      toast('个人校准已保存；原始画面和关键点序列未写入记忆。');
    }
    if (action === 'discard-calibration') {
      state.pendingCalibration = null;
      state.calibrationSamples = [];
      const button = $('#captureBtn');
      if (button) { button.disabled = false; button.textContent = '采集当前动作'; }
      toast('本次校准已丢弃，没有写入本地记忆。');
    }
    if (action === 'record-comfort') {
      const comfort = Number($('#comfortInput')?.value);
      if (state.experimentResult && Number.isFinite(comfort)) {
        state.experimentResult.comfort = comfort;
        renderExperimentEvidence(state.experimentResult);
        state.experimentPhase = 'confirm';
        $('#experimentState').textContent = '等待用户确认';
        $('#experimentBtn').textContent = state.experimentResult.evidenceStatus === 'qualified'
          ? `确认${planData[state.selectedPlan].label}并保存记录`
          : '保存为证据不足记录';
        $('#experimentBtn').classList.add('confirm');
        toast('真实时序证据与主观评分已组合，请确认是否保存。');
      }
    }
    if (action === 'disable-memory') {
      state.localProfile.memories.forEach((memory) => { memory.enabled = false; });
      persistLocalProfile();
      toast('全部记忆已停用，记录仍可恢复。');
    }
    if (action === 'delete-memory') {
      state.localProfile.memories = [];
      state.localProfile.experiments = [];
      state.localProfile.calibration = null;
      persistLocalProfile();
      toast('全部个人记忆已清空。');
    }
    closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeModal();
    if (event.key === 'Tab' && modalBackdrop && !modalBackdrop.hidden) {
      const focusable = $$('button, input, [tabindex]:not([tabindex="-1"])', modalBackdrop).filter((node) => !node.disabled);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });

  window.addEventListener('pagehide', () => {
    stopVisionInput({ announce: false });
    state.poseLandmarker?.close?.();
    state.objectDetector?.close?.();
    stopTimer();
    window.clearInterval(state.storyboardHandle);
  });

  function initializeDreamField() {
    const field = $('.dream-field');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!field || reducedMotion.matches) return;
    let frame = 0;
    let targetX = 0;
    let targetY = 0;
    const render = () => {
      frame = 0;
      document.documentElement.style.setProperty('--dream-x', targetX.toFixed(3));
      document.documentElement.style.setProperty('--dream-y', targetY.toFixed(3));
    };
    window.addEventListener('pointermove', (event) => {
      targetX = (event.clientX / Math.max(window.innerWidth, 1) - .5) * 2;
      targetY = (event.clientY / Math.max(window.innerHeight, 1) - .5) * 2;
      if (!frame) frame = window.requestAnimationFrame(render);
    }, { passive: true });
    document.documentElement.addEventListener('mouseleave', () => {
      targetX = 0;
      targetY = 0;
      if (!frame) frame = window.requestAnimationFrame(render);
    });
  }

  initializeDreamField();
  state.localProfile = loadLocalProfile();
  if (state.localProfile.calibration) {
    updateVisionMetric('#calibrationSummary', '已本地校准');
    updateVisionMetric('#calibrationDetail', `${state.localProfile.calibration.sampleCount} 次真实关键点采集，仅保存归一化比例`);
  }
  renderMemories();
  selectPlan('a');
  showView('sense');
})();
