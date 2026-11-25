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
    architecture: 'Agent 闭环架构',
    research: '课程设计档案'
  };

  const state = {
    view: 'sense',
    paused: false,
    selectedPlan: 'a',
    tourIndex: -1,
    experimentPhase: 'ready',
    appliedPlan: false,
    timerSeconds: 720,
    timerHandle: null,
    storyboardHandle: null,
    lastFocus: null,
    mediaStream: null,
    mediaObjectUrl: null,
    visionRaf: null,
    poseLandmarker: null,
    poseModelPromise: null,
    visionMode: null,
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

  async function ensurePoseLandmarker() {
    if (state.poseLandmarker) return state.poseLandmarker;
    if (state.poseModelPromise) return state.poseModelPromise;
    state.poseModelPromise = (async () => {
      const visionModule = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/+esm');
      const vision = await visionModule.FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm'
      );
      const options = {
        baseOptions: {
          modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
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

  async function ensurePostureClassifier() {
    if (state.postureModel && state.postureRuntime) return state.postureModel;
    if (state.postureModelPromise) return state.postureModelPromise;
    const runtimeUrl = appContext ? `${appContext}/assets/js/posture-inference.mjs` : './posture-inference.mjs';
    const modelUrl = appContext ? `${appContext}/assets/models/posture-classifiers-v1.json` : './models/posture-classifiers-v1.json';
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
  }

  function applyPostureInference(landmarks, timestamp) {
    if (!state.postureModel || !state.postureRuntime || timestamp - state.lastPostureInferenceAt < 250) return;
    state.lastPostureInferenceAt = timestamp;
    const prediction = state.postureRuntime.classifyPose(state.postureModel, landmarks);
    const upper = prediction.upper;
    const lower = prediction.lower;
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
      return;
    }
    if (upper.label === 'TUP') {
      state.postureCandidate = null;
      state.postureCandidateSince = 0;
      $('#agentFinding').textContent = '当前躯干关系较稳定';
      $('#agentReason').textContent = `真实训练模型识别为“${POSTURE_LABELS[upper.label]}”（${confidence}%）。姿态变化本身是正常的，系统不会要求你始终保持同一姿势。`;
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
      return;
    }
    $('#agentFinding').textContent = `${POSTURE_LABELS[upper.label]}已持续 5 秒`;
    $('#agentReason').textContent = `${POSTURE_GUIDANCE[upper.label]} 这是基于关键点关系的非医疗建议，原始画面仍只在本机处理。`;
  }

  function setLiveStage(active) {
    if (liveVisionStage) liveVisionStage.hidden = !active;
    if (scenePlaceholder) scenePlaceholder.hidden = active;
    $('#scene')?.classList.toggle('has-live-input', active);
    if (stopSourceBtn) stopSourceBtn.disabled = !active;
    if (startCameraBtn) startCameraBtn.setAttribute('aria-pressed', String(active && state.visionMode === 'camera'));
    const objectOverlay = $('[data-overlay="objects"]');
    if (objectOverlay) {
      objectOverlay.disabled = active;
      objectOverlay.title = active ? '当前真实输入仅启用 MediaPipe 姿态模型，不虚构物体检测结果' : '';
    }
  }

  function resetVisionMetrics() {
    updateVisionMetric('#poseMetric', '等待人体');
    updateVisionMetric('#neckMetric', '头颈偏移 —');
    updateVisionMetric('#shoulderMetric', '肩线角度 —');
    updateVisionMetric('#visionPoseMetric', '姿态关键点 —');
    updateVisionMetric('#visionFpsMetric', '分析帧率 —');
  }

  function stopVisionInput({ announce = true } = {}) {
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
    state.paused = false;
    state.lastVideoTime = -1;
    state.inferenceFrames = 0;
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
      updateVisionMetric('#poseMetric', '画面中未检测到人体');
      updateVisionMetric('#visionPoseMetric', '姿态关键点 0');
      return;
    }

    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.strokeStyle = '#3b9c7a';
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
    }
    state.visionRaf = requestAnimationFrame(visionLoop);
  }

  function beginVision(mode, label) {
    state.visionMode = mode;
    state.paused = false;
    state.lastVideoTime = -1;
    state.inferenceFrames = 0;
    state.inferenceWindowStarted = performance.now();
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
    if (state.visionRaf) cancelAnimationFrame(state.visionRaf);
    state.visionRaf = requestAnimationFrame(visionLoop);
    ensurePoseLandmarker().then(() => {
      if (state.visionMode !== mode) return;
      setSourceStatus(`${label} · MediaPipe 本地分析中`, 'live');
      toast('真实视觉输入已启用，姿态关键点仅在本机浏览器中处理。', 3600);
    }).catch(() => {
      if (state.visionMode !== mode) return;
      setSourceStatus(`${label} · 视频正常播放，姿态模型加载失败`, 'warning');
      toast('视频输入已启用；姿态模型暂不可用，原始画面仍不会上传。', 3600);
    });
    ensurePostureClassifier().catch(() => {
      toast('MediaPipe 仍可工作，但训练后的姿态分类器没有加载成功。', 3600);
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
    if (!file.type.startsWith('video/')) {
      toast('请选择浏览器支持的视频文件。');
      return;
    }
    stopVisionInput({ announce: false });
    state.mediaObjectUrl = URL.createObjectURL(file);
    visionVideo.controls = true;
    visionVideo.src = state.mediaObjectUrl;
    try {
      await new Promise((resolve, reject) => {
        visionVideo.addEventListener('loadeddata', resolve, { once: true });
        visionVideo.addEventListener('error', reject, { once: true });
      });
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

  $('#privacyBtn')?.addEventListener('click', () => openModal(`
    <span class="modal-kicker">PRIVACY CONTROL</span>
    <h2 id="modalTitle">你的数据，你来决定</h2>
    <p>摄像头或导入视频只在当前浏览器内处理。停止输入时会立即关闭摄像头轨道并释放本地视频缓存；保存任何实验结论前仍需你的确认。</p>
    <div class="privacy-options">
      <label><span><b>实时画面分析</b><small>仅在当前会话处理</small></span><input type="checkbox" checked></label>
      <label><span><b>保存实验结果</b><small>保存前必须由你确认</small></span><input type="checkbox" checked></label>
      <label><span><b>个性化记忆</b><small>可随时停用或删除</small></span><input type="checkbox" checked></label>
    </div>
    <div class="modal-actions privacy-actions">
      <button class="secondary-btn" data-modal-action="stop-camera" type="button">停止摄像头</button>
      <button class="danger-btn" data-modal-action="delete-session" type="button">删除本次会话数据</button>
    </div>
    <button class="primary-btn wide" data-modal-action="save-privacy" type="button">保存隐私设置</button>
  `));

  const tourSteps = [
    { view: 'sense', message: '第 1 步：AI 观察现实空间，并说明判断依据。' },
    { view: 'design', message: '第 2 步：比较多个方案，用户仍可拖动参数。' },
    { view: 'experiment', message: '第 3 步：用短时自我实验验证哪种方案更适合。' },
    { view: 'memory', message: '第 4 步：只在用户确认后更新个人健康记忆。' },
    { view: 'architecture', message: '第 5 步：查看从感知、意图到验证与记忆的完整 Agent 闭环。' },
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
      title: '显示器可能低于舒适视线',
      reason: '你持续注视屏幕，并在过去 18 分钟出现 6 次颈部前倾。屏幕位置可能需要调整，但我还需要侧面视角确认。'
    },
    cup: {
      title: '水杯位于惯用手一侧',
      reason: '水杯距离右手约 31 cm，当前仍在舒适可达区。除非你希望保留右侧手写区域，否则无需主动调整。'
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
    toast(copy[1], 3200);
  });

  $('#evidenceBtn')?.addEventListener('click', () => {
    const hasLiveEvidence = Boolean(state.visionMode);
    const source = state.visionMode === 'camera' ? '实时摄像头' : state.visionMode === 'file' ? '本地视频' : '未连接';
    openModal(`
      <span class="modal-kicker">REAL VISUAL EVIDENCE</span>
      <h2 id="modalTitle">当前判断使用了什么真实证据？</h2>
      <div class="evidence-modal">
        <div class="evidence-frame"><span>${hasLiveEvidence ? 'LIVE' : 'NO INPUT'}</span><i class="evidence-line"></i><b>${escapeHtml(source)}</b></div>
        <ol>
          <li><b>输入来源</b><span>${hasLiveEvidence ? `${escapeHtml(source)}，原始画面未上传` : '尚未启用摄像头或导入视频'}</span></li>
          <li><b>姿态检测</b><span>${escapeHtml($('#poseMetric')?.textContent || '无检测结果')}</span></li>
          <li><b>头肩线索</b><span>${escapeHtml([$('#neckMetric')?.textContent, $('#shoulderMetric')?.textContent].filter(Boolean).join(' · ') || '无检测结果')}</span></li>
          <li class="uncertain"><b>仍不确定</b><span>${hasLiveEvidence ? '二维单视角不能确认真实距离、屏幕高度或长期健康影响' : '没有真实视觉输入时，系统不会声称已经观察你的姿态'}</span></li>
        </ol>
      </div>
      <p class="modal-note">MediaPipe 本地姿态估计 · 可暂停、纠正或立即停止，不是医疗诊断。</p>
    `);
  });

  $('#previewBtn')?.addEventListener('click', () => {
    toast('已根据你的任务与空间限制生成 2 个可撤销方案。');
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
            task: '深度学习与论文写作，已持续 42 分钟',
            visualSource: state.visionMode === 'camera' ? '用户授权的实时摄像头' : state.visionMode === 'file' ? '用户导入的本地视频' : '尚无真实视觉输入',
            observations: state.visionMode ? [
              $('#poseMetric')?.textContent || '姿态检测状态未知',
              $('#neckMetric')?.textContent || '头颈偏移未知',
              $('#shoulderMetric')?.textContent || '肩线角度未知'
            ] : ['尚未启用摄像头或导入视频，不能声称已观察真实姿态'],
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
    current?.classList.remove('active');
    current?.classList.add('done');
    const marker = $('i', current);
    if (marker) marker.textContent = '✓';
    const next = steps[Math.min(activeIndex + 1, steps.length - 1)];
    if (activeIndex < steps.length - 1) {
      next.classList.add('active');
      toast('动作已采集，继续完成下一项。');
    } else {
      event.currentTarget.textContent = '校准已完成';
      event.currentTarget.disabled = true;
      toast('个人活动范围已更新；保存前仍需你的确认。');
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
    $('#heightValue').textContent = `+${amount} cm`;
    $('#angleValue').textContent = `${angle}°`;
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
      $('#experimentBtn').textContent = '开始体验方案 A';
    }
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

  function finishExperiment() {
    stopTimer();
    state.experimentPhase = 'confirm';
    $('#experimentState').textContent = '等待用户确认';
    $('#experimentBtn').textContent = '确认方案 A 并更新记忆';
    $('#experimentBtn').classList.add('confirm');
    toast('比较已完成：请确认是否把结果写入个人记忆。', 3400);
  }

  $('#experimentBtn')?.addEventListener('click', (event) => {
    if (state.experimentPhase === 'ready') {
      state.experimentPhase = 'running';
      $('#experimentState').textContent = '正在体验方案 A';
      event.currentTarget.textContent = '结束体验并查看结果';
      state.timerSeconds = 720;
      renderTimer();
      state.timerHandle = window.setInterval(() => {
        state.timerSeconds = Math.max(0, state.timerSeconds - 15);
        renderTimer();
        if (state.timerSeconds === 0) finishExperiment();
      }, 1000);
      toast('实验已开始；你可以随时提前结束。');
    } else if (state.experimentPhase === 'running') {
      finishExperiment();
    } else {
      state.experimentPhase = 'saved';
      event.currentTarget.textContent = '结果已保存';
      event.currentTarget.disabled = true;
      toast('已保存“方案 A 更舒适”；你可以在记忆页面撤销。');
      window.setTimeout(() => showView('memory'), 420);
    }
  });

  $('#skipExperiment')?.addEventListener('click', () => {
    stopTimer();
    state.experimentPhase = 'ready';
    toast('已跳过实验，空间和个人记忆均未改变。');
    window.setTimeout(() => showView('sense'), 360);
  });

  $$('.toggle').forEach((button) => button.addEventListener('click', () => {
    button.classList.toggle('on');
    const active = button.classList.contains('on');
    button.setAttribute('aria-pressed', String(active));
    const title = $('b', button.closest('.memory-item'))?.textContent || '该记忆';
    toast(`${title}已${active ? '启用' : '停用'}。`);
  }));

  $('.delete-memory')?.addEventListener('click', (event) => {
    const item = event.currentTarget.closest('.memory-item');
    item?.classList.add('removing');
    window.setTimeout(() => item?.remove(), 240);
    toast('这条待确认推断已删除。');
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
      product: 'HealthVerse concept prototype',
      exportedAt: new Date().toISOString(),
      confirmedPreferences: ['桌面右侧保留手写区域', '方案 A 在短时体验中更舒适'],
      note: 'Demo data only. Not medical advice.'
    };
    const file = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'healthverse-demo-data.json';
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

  $('#downloadArch')?.addEventListener('click', () => {
    const svg = $('#architectureSvg');
    if (!svg) return;
    const source = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${source}`], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'healthverse-agent-architecture.svg';
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('架构图 SVG 已生成，可继续在 Figma 或 Illustrator 中编辑。');
  });

  modalClose?.addEventListener('click', closeModal);
  modalBackdrop?.addEventListener('click', (event) => {
    if (event.target === modalBackdrop) closeModal();
  });

  modalBody?.addEventListener('click', (event) => {
    const action = event.target.closest('[data-modal-action]')?.dataset.modalAction;
    if (!action) return;
    if (action === 'save-privacy') toast('隐私设置已保存。');
    if (action === 'stop-camera') {
      stopVisionInput();
    }
    if (action === 'delete-session') {
      stopVisionInput({ announce: false });
      state.appliedPlan = false;
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
    if (action === 'disable-memory') {
      $$('.toggle').forEach((toggle) => toggle.classList.remove('on'));
      toast('全部记忆已停用，记录仍可恢复。');
    }
    if (action === 'delete-memory') {
      $$('.memory-item').forEach((item) => item.remove());
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
    stopTimer();
    window.clearInterval(state.storyboardHandle);
  });

  selectPlan('a');
  showView('sense');
})();
