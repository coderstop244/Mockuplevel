/**
 * Mockuplevel - Multimodal Study Companion Frontend Application
 */

const App = {
  state: {
    activeTab: 'study', // study, library, flashcards, quiz, mock-papers, mastery, settings
    activeSubTab: 'transcript', // transcript, keyframes, document
    sources: [],
    selectedSource: null,
    studyTopic: null,
    tenantId: null,
    courseId: null,
    streamUrl: null,
    transcript: [],
    keyframes: [],
    chatMessages: [
      {
        role: 'assistant',
        content: `### 👋 Welcome to Mockuplevel!
I am your Multimodal Study Companion. I have analyzed your lecture materials, transcripts, and visual slides.

**What I can do for you:**
- 🎯 Answer any question with **clickable video timestamp citations**.
- 📝 Break down complex concepts into step-by-step notes.
- ⚡ Test your recall with interactive flashcards and quizzes.
- 🎬 Sync transcripts and keyframes with your video lecture.

Try asking: *"What is PostgreSQL and what are its key features?"* or pick a prompt below!`,
        citations: []
      }
    ],
    isChatLoading: false,
    flashcards: [],
    currentCardIndex: 0,
    isCardFlipped: false,
    quizQuestions: [],
    currentQuizIndex: 0,
    quizScore: 0,
    quizSelectedOption: null,
    quizAnswered: false,
    quizCompleted: false,
    mockPapers: [],
    mockPaperSourceId: null,
    activeMockPaper: null,
    mockPaperTimeLeft: 3600,
    mockPaperTimer: null,
    mockPaperReports: [],
    masteryData: null,
    storageFiles: [],
    healthStatus: null,
    activeTaskId: null,
    taskInterval: null
  },

  init() {
    this.restoreMockPapers();
    this.setupEventListeners();
    this.fetchHealth();
    this.fetchSources();
    this.fetchStorageFiles();
    this.renderTabs();
    this.renderChatMessages();
  },

  restoreMockPapers() {
    try {
      const saved = JSON.parse(localStorage.getItem('studypulse_mock_papers_v3') || 'null');
      if (
        saved &&
        Array.isArray(saved.papers) &&
        saved.papers.length === 10 &&
        saved.papers.every(paper =>
          Number.isInteger(paper.question_count) &&
          paper.questions?.length === paper.question_count &&
          paper.questions.every(question =>
            Array.isArray(question.options) &&
            question.options.length === 4 &&
            Number.isInteger(question.correct_index)
          )
        )
      ) {
        this.state.mockPapers = saved.papers;
        this.state.mockPaperSourceId = saved.sourceId || null;
      }
      const reports = JSON.parse(localStorage.getItem('studypulse_mock_reports_v1') || '[]');
      this.state.mockPaperReports = Array.isArray(reports) ? reports : [];
    } catch (err) {
      console.warn('Saved mock papers could not be restored:', err);
      localStorage.removeItem('studypulse_mock_papers_v3');
      localStorage.removeItem('studypulse_mock_reports_v1');
    }
  },

  setupEventListeners() {
    // Navigation tabs
    document.querySelectorAll('[data-tab]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tab = e.currentTarget.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // Sub-tabs (Transcript / Keyframes / Document)
    document.querySelectorAll('[data-subtab]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const subtab = e.currentTarget.getAttribute('data-subtab');
        this.switchSubTab(subtab);
      });
    });

    // Chat form submit
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
      chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.sendChatMessage();
      });
    }

    // Chat textarea Enter key
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendChatMessage();
        }
      });
    }

    // Video Player synchronization
    const video = document.getElementById('study-video');
    if (video) {
      video.addEventListener('timeupdate', () => {
        this.onVideoTimeUpdate(video.currentTime);
      });
    }

    // File Upload dropzone
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-upload-input');
    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
          this.uploadFile(e.target.files[0]);
        }
      });
      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-indigo-500', 'bg-indigo-500/10');
      });
      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
      });
      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
        if (e.dataTransfer.files.length) {
          this.uploadFile(e.dataTransfer.files[0]);
        }
      });
    }

    // Source selector change
    const sourceSelect = document.getElementById('source-selector');
    if (sourceSelect) {
      sourceSelect.addEventListener('change', (e) => {
        this.selectSource(e.target.value);
      });
    }

    // Flashcard flip on card click
    const flashcardEl = document.getElementById('flashcard-card');
    if (flashcardEl) {
      flashcardEl.addEventListener('click', () => {
        this.toggleFlashcardFlip();
      });
    }
  },

  // -----------------------------
  // Navigation & Tabs
  // -----------------------------
  switchTab(tab) {
    this.state.activeTab = tab;
    document.querySelectorAll('.view-panel').forEach(panel => {
      panel.classList.add('hidden');
    });
    const activePanel = document.getElementById(`panel-${tab}`);
    if (activePanel) activePanel.classList.remove('hidden');

    document.querySelectorAll('[data-tab]').forEach(btn => {
      const isTarget = btn.getAttribute('data-tab') === tab;
      btn.classList.toggle('active', isTarget);
      if (isTarget) {
        btn.classList.add('text-white', 'bg-indigo-600/20', 'border-indigo-500/50');
        btn.classList.remove('text-slate-400');
      } else {
        btn.classList.remove('text-white', 'bg-indigo-600/20', 'border-indigo-500/50');
        btn.classList.add('text-slate-400');
      }
    });

    if (tab === 'flashcards' && !this.state.flashcards.length) {
      this.loadFlashcards();
    } else if (tab === 'quiz' && !this.state.quizQuestions.length) {
      this.loadQuiz();
    } else if (tab === 'mastery') {
      this.fetchMastery();
    } else if (tab === 'library') {
      this.fetchStorageFiles();
    } else if (tab === 'mock-papers' && !this.state.mockPapers.length) {
      this.loadMockPapers();
    }
  },

  switchSubTab(subtab) {
    this.state.activeSubTab = subtab;
    document.querySelectorAll('.subtab-panel').forEach(p => p.classList.add('hidden'));
    const target = document.getElementById(`subpanel-${subtab}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('[data-subtab]').forEach(btn => {
      const isTarget = btn.getAttribute('data-subtab') === subtab;
      btn.classList.toggle('text-indigo-400', isTarget);
      btn.classList.toggle('border-b-2', isTarget);
      btn.classList.toggle('border-indigo-500', isTarget);
      btn.classList.toggle('text-slate-400', !isTarget);
    });
  },

  renderTabs() {
    this.switchTab(this.state.activeTab);
    this.switchSubTab(this.state.activeSubTab);
  },

  // -----------------------------
  // API Fetchers
  // -----------------------------
  async fetchHealth() {
    try {
      const res = await fetch('/api/v1/health');
      const data = await res.json();
      this.state.healthStatus = data;
      this.renderHealthBadge(data);
    } catch (err) {
      console.warn('Health check failed:', err);
    }
  },

  renderHealthBadge(health) {
    const badge = document.getElementById('system-health-pill');
    if (!badge) return;
    const isHealthy = health?.status === 'healthy';
    badge.innerHTML = `
      <span class="w-2 h-2 rounded-full ${isHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}"></span>
      <span class="text-xs font-medium text-slate-300">
        ${isHealthy ? 'System Active' : 'Offline / Standalone'}
      </span>
    `;
  },

  async fetchSources() {
    try {
      const res = await fetch('/api/v1/sources');
      const data = await res.json();
      this.state.sources = data.sources || [];
      this.state.tenantId = data.tenant_id || null;
      this.state.courseId = data.course_id || null;
      this.renderSourceSelector();
      this.renderLibraryGrid();

      if (this.state.sources.length > 0 && !this.state.selectedSource) {
        this.selectSource(this.state.sources[0].source_id);
      }
    } catch (err) {
      console.error('Error fetching sources:', err);
    }
  },

  renderSourceSelector() {
    const selector = document.getElementById('source-selector');
    if (!selector) return;
    selector.innerHTML = '';
    this.state.sources.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.source_id;
      opt.textContent = `${s.media_type === 'video' ? '🎬' : '📄'} ${s.title} (${s.chunks_count} chunks)`;
      if (s.source_id === this.state.selectedSource) {
        opt.selected = true;
      }
      selector.appendChild(opt);
    });
  },

  async selectSource(sourceId) {
    this.state.selectedSource = sourceId;
    const sourceObj = this.state.sources.find(s => s.source_id === sourceId);
    this.state.studyTopic = sourceObj || null;
    this.state.chatMessages = [{
      role: 'assistant',
      content: `### 📚 ${sourceObj?.title || sourceId}\n\nAsk a question about this topic. Answers are generated from this topic's indexed study material.`,
      citations: []
    }];
    this.renderChatMessages();

    // Update active source title banner
    const titleEl = document.getElementById('active-source-title');
    if (titleEl && sourceObj) {
      titleEl.textContent = sourceObj.title;
    }
    const chatInput = document.getElementById('chat-input');
    if (chatInput && sourceObj) {
      chatInput.placeholder = `Ask a question about ${sourceObj.title}...`;
    }

    // 1. Fetch streaming URL
    try {
      const res = await fetch(`/api/v1/sources/${encodeURIComponent(sourceId)}/stream`);
      const data = await res.json();
      this.state.streamUrl = data.url;
      const video = document.getElementById('study-video');
      if (video && data.url) {
        video.src = data.url;
        video.load();
      }
    } catch (err) {
      console.error('Error loading stream URL:', err);
    }

    // 2. Fetch transcript
    try {
      const res = await fetch(`/api/v1/sources/${encodeURIComponent(sourceId)}/transcript`);
      const data = await res.json();
      this.state.transcript = data.segments || [];
      this.renderTranscript();
    } catch (err) {
      console.error('Error loading transcript:', err);
    }

    // 3. Fetch keyframes
    try {
      const res = await fetch(`/api/v1/sources/${encodeURIComponent(sourceId)}/keyframes`);
      const data = await res.json();
      this.state.keyframes = data.keyframes || [];
      this.renderKeyframes();
    } catch (err) {
      console.error('Error loading keyframes:', err);
    }
  },

  // -----------------------------
  // Video Player & Transcript Sync
  // -----------------------------
  seekVideo(seconds) {
    const video = document.getElementById('study-video');
    if (video) {
      video.currentTime = parseFloat(seconds);
      video.play().catch(() => {});
      this.onVideoTimeUpdate(seconds);
    }
  },

  onVideoTimeUpdate(currentTime) {
    // Format timer
    const timeDisplay = document.getElementById('video-time-display');
    const video = document.getElementById('study-video');
    if (timeDisplay && video) {
      const cur = this.formatTime(currentTime);
      const dur = this.formatTime(video.duration || 0);
      timeDisplay.textContent = `${cur} / ${dur}`;
    }

    // Highlight transcript segment
    const segments = document.querySelectorAll('.transcript-segment');
    let activeFound = false;

    segments.forEach(el => {
      const tStart = parseFloat(el.getAttribute('data-start') || '0');
      const tEnd = parseFloat(el.getAttribute('data-end') || '999999');

      if (!activeFound && currentTime >= tStart && currentTime <= tEnd) {
        if (!el.classList.contains('active')) {
          segments.forEach(s => s.classList.remove('active'));
          el.classList.add('active');
          // Smooth autoscroll into view
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        activeFound = true;
      }
    });
  },

  renderTranscript() {
    const container = document.getElementById('transcript-container');
    if (!container) return;
    if (!this.state.transcript.length) {
      container.innerHTML = `
        <div class="text-center py-12 text-slate-500">
          <i data-lucide="file-text" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
          <p>No transcript segments available for this source.</p>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    container.innerHTML = this.state.transcript.map(s => {
      const timeTag = this.formatTime(s.t_start);
      return `
        <div class="transcript-segment p-3 rounded-lg hover:bg-slate-800/60 cursor-pointer flex gap-3 items-start"
             data-start="${s.t_start}" data-end="${s.t_end}"
             onclick="App.seekVideo(${s.t_start})">
          <span class="citation-pill shrink-0">${timeTag}</span>
          <p class="text-sm text-slate-200 leading-relaxed">${this.escapeHtml(s.text)}</p>
        </div>
      `;
    }).join('');
    lucide.createIcons();
  },

  renderKeyframes() {
    const container = document.getElementById('keyframes-grid');
    if (!container) return;
    if (!this.state.keyframes.length) {
      container.innerHTML = `
        <div class="col-span-full text-center py-12 text-slate-500">
          <i data-lucide="image" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
          <p>No keyframes extracted yet for this video.</p>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    container.innerHTML = this.state.keyframes.map(k => `
      <div class="glass-card group overflow-hidden rounded-xl border border-white/5 cursor-pointer relative"
           onclick="App.seekVideo(${k.timestamp})">
        <div class="aspect-video bg-slate-900 overflow-hidden relative">
          <img src="${k.url}" alt="Keyframe ${k.formatted_time}"
               class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
               loading="lazy" />
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <span class="p-2 rounded-full bg-indigo-600 text-white shadow-lg">
              <i data-lucide="play" class="w-4 h-4 fill-white"></i>
            </span>
          </div>
          <span class="absolute bottom-2 left-2 bg-slate-950/80 backdrop-blur text-xs font-mono px-2 py-0.5 rounded text-indigo-300 border border-white/10">
            ${k.formatted_time}
          </span>
        </div>
      </div>
    `).join('');
    lucide.createIcons();
  },

  // -----------------------------
  // AI Study Chat
  // -----------------------------
  async sendChatMessage(prefilledText = null) {
    const input = document.getElementById('chat-input');
    const text = prefilledText || (input ? input.value.trim() : '');
    if (!text || this.state.isChatLoading) return;

    if (input && !prefilledText) input.value = '';

    // Add user message
    this.state.chatMessages.push({
      role: 'user',
      content: text
    });
    this.state.isChatLoading = true;
    this.renderChatMessages();

    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          source_id: this.state.selectedSource,
          tenant_id: this.state.tenantId,
          course_id: this.state.courseId
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Chat request failed (${res.status})`);
      }

      this.state.chatMessages.push({
        role: 'assistant',
        content: data.answer,
        citations: data.citations || [],
        suggested: data.suggested_questions || []
      });
    } catch (err) {
      console.error('Chat error:', err);
      this.state.chatMessages.push({
        role: 'assistant',
        content: `⚠️ **Error communicating with study companion:** ${err.message}. Please check that the server is running.`,
        citations: []
      });
    } finally {
      this.state.isChatLoading = false;
      this.renderChatMessages();
    }
  },

  renderChatMessages() {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;

    container.innerHTML = this.state.chatMessages.map(msg => {
      const isUser = msg.role === 'user';
      let htmlBody = isUser ? this.escapeHtml(msg.content) : marked.parse(msg.content);

      // Replace timestamp references in Markdown like [01:15] with interactive citation chips
      htmlBody = htmlBody.replace(/\[(\d{1,2}:\d{2})\]/g, (match, p1) => {
        const secs = this.parseTimeToSeconds(p1);
        return `<button class="citation-pill" onclick="App.seekVideo(${secs})">⏱️ ${p1}</button>`;
      });

      // Citations footer
      let citationsHtml = '';
      if (msg.citations && msg.citations.length > 0) {
        citationsHtml = `
          <div class="mt-3 pt-2.5 border-t border-white/10 flex flex-wrap gap-1.5 items-center">
            <span class="text-xs text-slate-400 font-semibold uppercase tracking-wider mr-1">Citations:</span>
            ${msg.citations.map(c => {
              if (c.timestamp !== null && c.timestamp !== undefined) {
                return `<button class="citation-pill" onclick="App.seekVideo(${c.timestamp})">🎬 ${c.formatted_time}</button>`;
              }
              return `<span class="citation-pill">📄 Page ${c.page_number}</span>`;
            }).join('')}
          </div>
        `;
      }

      // Suggested follow-up prompt pills
      let suggestedHtml = '';
      if (msg.suggested && msg.suggested.length > 0) {
        suggestedHtml = `
          <div class="mt-3 flex flex-wrap gap-2">
            ${msg.suggested.map(q => `
              <button class="text-xs px-2.5 py-1 rounded-full bg-indigo-950/60 hover:bg-indigo-900/80 border border-indigo-700/50 text-indigo-300 transition-all"
                      onclick="App.sendChatMessage('${this.escapeHtml(q)}')">
                💡 ${this.escapeHtml(q)}
              </button>
            `).join('')}
          </div>
        `;
      }

      return `
        <div class="flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}">
          ${!isUser ? `
            <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shrink-0 shadow-md">
              <i data-lucide="bot" class="w-4 h-4 text-white"></i>
            </div>
          ` : ''}

          <div class="max-w-[85%] rounded-2xl p-4 ${isUser ? 'bg-indigo-600 text-white rounded-tr-none' : 'glass-panel text-slate-100 rounded-tl-none border border-white/10'}">
            <div class="prose prose-invert prose-sm max-w-none leading-relaxed">
              ${htmlBody}
            </div>
            ${citationsHtml}
            ${suggestedHtml}
          </div>

          ${isUser ? `
            <div class="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center shrink-0">
              <i data-lucide="user" class="w-4 h-4 text-slate-300"></i>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    // If loading, append typing indicator
    if (this.state.isChatLoading) {
      container.innerHTML += `
        <div class="flex gap-3 items-center text-slate-400 text-xs py-2">
          <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shrink-0">
            <i data-lucide="bot" class="w-4 h-4 text-white"></i>
          </div>
          <div class="glass-panel px-4 py-3 rounded-2xl border border-white/10 flex items-center gap-1.5">
            <span class="wave-bar"></span>
            <span class="wave-bar"></span>
            <span class="wave-bar"></span>
            <span class="wave-bar"></span>
            <span class="wave-bar"></span>
            <span class="ml-2 font-medium text-slate-300">Synthesizing study answer...</span>
          </div>
        </div>
      `;
    }

    container.scrollTop = container.scrollHeight;
    lucide.createIcons();
  },

  // -----------------------------
  // Storage & Ingestion Pipeline
  // -----------------------------
  async fetchStorageFiles() {
    try {
      const res = await fetch('/api/v1/storage/files');
      const data = await res.json();
      this.state.storageFiles = data.files || [];
      this.renderStorageFiles();
    } catch (err) {
      console.error('Error fetching storage files:', err);
    }
  },

  renderStorageFiles() {
    const listEl = document.getElementById('storage-files-list');
    if (!listEl) return;
    if (!this.state.storageFiles.length) {
      listEl.innerHTML = `
        <div class="col-span-full text-center py-6 text-slate-500">
          <p>No storage objects found in Supabase.</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = this.state.storageFiles.map(f => `
      <div class="glass-card p-4 rounded-xl flex items-center justify-between border border-white/5">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg ${f.type === 'video' ? 'bg-indigo-500/10 text-indigo-400' : 'bg-cyan-500/10 text-cyan-400'} flex items-center justify-center">
            <i data-lucide="${f.type === 'video' ? 'video' : 'file-text'}" class="w-5 h-5"></i>
          </div>
          <div>
            <h4 class="font-semibold text-sm text-slate-200">${this.escapeHtml(f.name)}</h4>
            <div class="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
              <span>Bucket: <code>${f.bucket}</code></span>
              <span>•</span>
              <span>${this.formatBytes(f.size_bytes)}</span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2">
          ${f.is_ingested ? `
            <span class="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold flex items-center gap-1">
              <i data-lucide="check-circle" class="w-3.5 h-3.5"></i> Indexed
            </span>
          ` : `
            <button class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all flex items-center gap-1.5"
                    onclick="App.ingestStorageFile('${f.name}', '${f.type}')">
              <i data-lucide="cpu" class="w-3.5 h-3.5"></i> Run Ingestion
            </button>
          `}
        </div>
      </div>
    `).join('');
    lucide.createIcons();
  },

  async ingestStorageFile(filename, type) {
    this.openTaskModal('Initializing ingestion pipeline...');
    try {
      const endpoint = type === 'video' ? '/api/v1/ingest/video' : '/api/v1/ingest/document';
      const payload = {
        source_id: filename,
        storage_path: filename
      };
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.task_id) {
        this.trackTask(data.task_id);
      }
    } catch (err) {
      this.updateTaskModalError(err.message);
    }
  },

  async uploadFile(file) {
    this.openTaskModal(`Uploading ${file.name}...`);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('auto_ingest', 'true');

    try {
      const res = await fetch('/api/v1/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Upload failed (${res.status})`);
      }
      if (data.task_id) {
        this.trackTask(data.task_id);
      } else {
        this.closeTaskModal();
        this.fetchSources();
        this.fetchStorageFiles();
      }
    } catch (err) {
      this.updateTaskModalError(err.message);
    }
  },

  trackTask(taskId) {
    this.state.activeTaskId = taskId;
    if (this.state.taskInterval) clearInterval(this.state.taskInterval);

    this.state.taskInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/tasks/${taskId}`);
        const data = await res.json();
        this.updateTaskModalProgress(data);

        if (data.status === 'SUCCESS' || data.status === 'SUCCESSFUL') {
          clearInterval(this.state.taskInterval);
          setTimeout(() => {
            this.closeTaskModal();
            this.fetchSources();
            this.fetchStorageFiles();
          }, 1500);
        } else if (data.status === 'FAILED') {
          clearInterval(this.state.taskInterval);
          this.updateTaskModalError(data.error || 'Ingestion task encountered an error.');
        } else if (data.status === 'UNKNOWN') {
          clearInterval(this.state.taskInterval);
          this.updateTaskModalError('The ingestion task could not be found on the server.');
        }
      } catch (err) {
        console.error('Error tracking task:', err);
      }
    }, 2000);
  },

  openTaskModal(initialStage) {
    const modal = document.getElementById('task-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.getElementById('task-stage-text').textContent = initialStage;
    document.getElementById('task-progress-bar').style.width = '15%';
  },

  updateTaskModalProgress(data) {
    const stageEl = document.getElementById('task-stage-text');
    const barEl = document.getElementById('task-progress-bar');
    if (stageEl) stageEl.textContent = data.stage || data.status;
    if (barEl) barEl.style.width = `${data.progress || 50}%`;
  },

  updateTaskModalError(errMsg) {
    const stageEl = document.getElementById('task-stage-text');
    const barEl = document.getElementById('task-progress-bar');
    if (stageEl) stageEl.innerHTML = `<span class="text-rose-400">Failed: ${errMsg}</span>`;
    if (barEl) barEl.classList.add('bg-rose-500');
  },

  closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) modal.classList.add('hidden');
  },

  async startStudySession(sourceId) {
    sourceId = decodeURIComponent(sourceId);
    const source = this.state.sources.find(s => s.source_id === sourceId);
    if (!source) {
      console.error(`Cannot start study session; source not found: ${sourceId}`);
      return;
    }

    this.state.selectedSource = sourceId;
    this.state.studyTopic = source;
    this.state.chatMessages = [{
      role: 'assistant',
      content: `### 📚 ${source.title}\n\nYou are now studying **${source.title}**. Ask me anything about this material and I will answer using only this topic's indexed content.\n\nTry asking:\n- What are the main concepts?\n- Explain this topic simply.\n- Create a quiz about this material.`,
      citations: []
    }];
    this.state.flashcards = [];
    this.state.quizQuestions = [];
    this.state.quizCompleted = false;

    await this.selectSource(sourceId);
    this.switchTab('study');
    this.renderChatMessages();

    const input = document.getElementById('chat-input');
    if (input) {
      input.placeholder = `Ask a question about ${source.title}...`;
      input.focus();
    }
  },

  openMockPapers() {
    if (
      this.state.mockPaperSourceId &&
      this.state.selectedSource &&
      this.state.mockPaperSourceId !== this.state.selectedSource
    ) {
      this.state.mockPapers = [];
    }
    this.switchTab('mock-papers');
  },

  async loadMockPapers() {
    const container = document.getElementById('mock-papers-container');
    if (container) {
      container.innerHTML = `
        <div class="glass-panel rounded-2xl p-8 border border-white/10 text-center">
          <div class="w-10 h-10 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 class="text-lg font-bold text-white">Building your mock papers...</h2>
          <p class="text-sm text-slate-400 mt-2">Retrieving indexed material and arranging difficulty from easy to hard.</p>
        </div>
      `;
    }
    try {
      const res = await fetch('/api/v1/study/mock-papers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: this.state.selectedSource,
          tenant_id: this.state.tenantId,
          course_id: this.state.courseId
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to generate mock papers');
      this.state.mockPapers = data.papers || [];
      this.state.mockPaperSourceId = this.state.selectedSource;
      localStorage.setItem('studypulse_mock_papers_v3', JSON.stringify({
        sourceId: this.state.selectedSource,
        papers: this.state.mockPapers
      }));
      this.state.mockPaperReports = [];
      localStorage.removeItem('studypulse_mock_reports_v1');
      this.renderMockPapersList();
    } catch (err) {
      console.error('Error generating mock papers:', err);
      if (container) {
        container.innerHTML = `
          <div class="glass-panel rounded-2xl p-8 border border-rose-500/30 text-center">
            <i data-lucide="alert-circle" class="w-10 h-10 text-rose-400 mx-auto mb-3"></i>
            <h2 class="text-lg font-bold text-white">Could not generate mock papers</h2>
            <p class="text-sm text-rose-200 mt-2">${this.escapeHtml(err.message)}</p>
            <button onclick="App.loadMockPapers()" class="mt-5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-sm">Try again</button>
          </div>
        `;
        lucide.createIcons();
      }
    }
  },

  renderMockPapersList() {
    const container = document.getElementById('mock-papers-container');
    if (!container) return;
    container.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h2 class="text-xl font-bold text-white">Test Yourself</h2>
          <p class="text-sm text-slate-400 mt-1">Select a paper. Each attempt is limited to 1 hour.</p>
        </div>
        <button onclick="App.loadMockPapers()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">Regenerate</button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        ${this.state.mockPapers.map((paper, index) => `
          <button onclick="App.startMockPaper(${index})" class="text-left glass-panel rounded-2xl p-4 border border-white/10 hover:border-indigo-400/60 hover:bg-indigo-950/30 transition-all">
            <div class="flex items-center justify-between mb-4">
              <span class="w-9 h-9 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold">${index + 1}</span>
              <span class="text-[10px] uppercase tracking-wider font-bold ${index < 3 ? 'text-emerald-400' : index < 7 ? 'text-amber-400' : 'text-rose-400'}">${this.escapeHtml(paper.difficulty || `Level ${index + 1}`)}</span>
            </div>
            <h3 class="text-sm font-bold text-white">${this.escapeHtml(paper.title || `Mock Paper ${index + 1}`)}</h3>
            <p class="text-xs text-slate-400 mt-2">${paper.question_count || paper.questions?.length || 0} MCQs · 60 minutes</p>
          </button>
        `).join('')}
      </div>
      ${this.renderMockPaperReports()}
    `;
    lucide.createIcons();
  },

  startMockPaper(index) {
    const paper = this.state.mockPapers[index];
    if (!paper) return;
    if (this.state.mockPaperTimer) clearInterval(this.state.mockPaperTimer);
    this.state.activeMockPaper = index;
    this.state.mockPaperTimeLeft = 3600;
    this.renderMockPaper();
    this.state.mockPaperTimer = setInterval(() => {
      this.state.mockPaperTimeLeft--;
      this.updateMockPaperTimer();
      if (this.state.mockPaperTimeLeft <= 0) {
        clearInterval(this.state.mockPaperTimer);
        this.state.mockPaperTimer = null;
        this.submitMockPaper(true);
      }
    }, 1000);
  },

  updateMockPaperTimer() {
    const timer = document.getElementById('mock-paper-timer');
    if (!timer) return;
    const minutes = Math.floor(this.state.mockPaperTimeLeft / 60);
    const seconds = this.state.mockPaperTimeLeft % 60;
    timer.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    timer.classList.toggle('text-rose-400', this.state.mockPaperTimeLeft <= 300);
  },

  renderMockPaper() {
    const container = document.getElementById('mock-papers-container');
    const paper = this.state.mockPapers[this.state.activeMockPaper];
    if (!container || !paper) return;
    container.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
        <div>
          <button onclick="App.stopMockPaper()" class="text-xs text-indigo-400 hover:text-indigo-300 mb-2">← Back to all papers</button>
          <h2 class="text-xl font-bold text-white">${this.escapeHtml(paper.title || 'Mock Paper')}</h2>
          <p class="text-sm text-slate-400">${this.escapeHtml(paper.difficulty || '')} · ${paper.question_count || paper.questions?.length || 0} MCQs</p>
        </div>
        <div class="px-4 py-2 rounded-xl bg-slate-900 border border-white/10 font-mono text-xl font-bold text-emerald-400" id="mock-paper-timer">60:00</div>
      </div>
      <form id="mock-paper-form" class="space-y-4">
        ${paper.questions.map((question, index) => `
          <label class="block glass-panel rounded-2xl p-5 border border-white/10">
            <span class="text-xs font-bold text-indigo-400">Question ${index + 1} of ${paper.question_count || paper.questions.length}</span>
            <p class="text-sm font-semibold text-white mt-2">${this.escapeHtml(question.question)}</p>
            <div class="mt-3 space-y-2">
              ${question.options.map((option, optionIndex) => `
                <label class="flex items-start gap-2 p-2 rounded-lg hover:bg-slate-800/70 cursor-pointer">
                  <input type="radio" name="answer-${index}" value="${optionIndex}" class="mt-1 accent-indigo-500">
                  <span class="text-sm text-slate-300">${String.fromCharCode(65 + optionIndex)}. ${this.escapeHtml(option)}</span>
                </label>
              `).join('')}
            </div>
          </label>
        `).join('')}
        <button type="submit" class="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm">Submit Paper</button>
      </form>
    `;
    document.getElementById('mock-paper-form').addEventListener('submit', (event) => {
      event.preventDefault();
      this.submitMockPaper(false);
    });
    this.updateMockPaperTimer();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  submitMockPaper(timedOut = false) {
    const paper = this.state.mockPapers[this.state.activeMockPaper];
    const form = document.getElementById('mock-paper-form');
    if (!paper || !form) return;
    const formData = new FormData(form);
    let answered = 0;
    let correct = 0;
    paper.questions.forEach((question, index) => {
      const selected = formData.get(`answer-${index}`);
      if (selected !== null) {
        answered++;
        if (Number(selected) === question.correct_index) correct++;
      }
    });
    const total = paper.questions.length;
    const report = {
      paperNumber: paper.paper_number || this.state.activeMockPaper + 1,
      title: paper.title,
      score: correct,
      total,
      answered,
      percentage: total ? Math.round((correct / total) * 100) : 0,
      timedOut,
      completedAt: new Date().toLocaleString()
    };
    this.state.mockPaperReports.unshift(report);
    localStorage.setItem('studypulse_mock_reports_v1', JSON.stringify(this.state.mockPaperReports.slice(0, 20)));
    if (this.state.mockPaperTimer) clearInterval(this.state.mockPaperTimer);
    this.state.mockPaperTimer = null;
    this.state.activeMockPaper = null;
    alert(timedOut ? 'Time is up. Your paper was submitted.' : `Paper submitted. Score: ${correct}/${total}`);
    this.renderMockPapersList();
  },

  renderMockPaperReports() {
    if (!this.state.mockPaperReports.length) return '';
    return `
      <div class="mt-8 glass-panel rounded-2xl p-5 border border-white/10">
        <h3 class="text-lg font-bold text-white mb-4">Progress Report</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="text-xs uppercase text-slate-500 border-b border-white/10">
              <tr><th class="py-2">Paper</th><th>Score</th><th>Answered</th><th>Progress</th><th>Completed</th></tr>
            </thead>
            <tbody>
              ${this.state.mockPaperReports.map(report => `
                <tr class="border-b border-white/5 text-slate-300">
                  <td class="py-3">${this.escapeHtml(report.title || `Paper ${report.paperNumber}`)}</td>
                  <td>${report.score}/${report.total}</td>
                  <td>${report.answered}/${report.total}</td>
                  <td><span class="${report.percentage >= 70 ? 'text-emerald-400' : 'text-amber-400'} font-bold">${report.percentage}%</span></td>
                  <td class="text-xs text-slate-500">${this.escapeHtml(report.completedAt)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  stopMockPaper() {
    if (this.state.mockPaperTimer) clearInterval(this.state.mockPaperTimer);
    this.state.mockPaperTimer = null;
    this.state.activeMockPaper = null;
    this.renderMockPapersList();
  },

  renderLibraryGrid() {
    const grid = document.getElementById('library-cards-grid');
    if (!grid) return;
    if (!this.state.sources.length) {
      grid.innerHTML = `
        <div class="col-span-full text-center py-12 text-slate-500">
          <p>No ingested materials found. Ingest a video or document to begin.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = this.state.sources.map(s => `
      <div class="glass-card rounded-2xl overflow-hidden border border-white/10 p-5 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold ${s.media_type === 'video' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30' : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'}">
              ${s.media_type.toUpperCase()}
            </span>
            <span class="text-xs text-slate-400">${s.chunks_count} Chunks</span>
          </div>
          <h3 class="text-lg font-bold text-white mb-1.5">${this.escapeHtml(s.title)}</h3>
          <p class="text-xs text-slate-400 font-mono mb-4">ID: ${this.escapeHtml(s.source_id)}</p>
        </div>

        <div class="pt-4 border-t border-white/5 flex items-center justify-between">
          <span class="text-xs text-slate-400 flex items-center gap-1">
            <i data-lucide="image" class="w-3.5 h-3.5"></i> ${s.keyframes_count} Slides
          </span>
          <button class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-all shadow-md flex items-center gap-1.5"
                  onclick="App.startStudySession('${encodeURIComponent(s.source_id)}')">
            <span>Show Now</span>
            <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `).join('');
    lucide.createIcons();
  },

  // -----------------------------
  // Flashcards Arena
  // -----------------------------
  async loadFlashcards() {
    try {
      const res = await fetch('/api/v1/study/flashcards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: this.state.selectedSource })
      });
      const data = await res.json();
      this.state.flashcards = data.cards || [];
      this.state.currentCardIndex = 0;
      this.state.isCardFlipped = false;
      this.renderFlashcard();
    } catch (err) {
      console.error('Error loading flashcards:', err);
    }
  },

  toggleFlashcardFlip() {
    this.state.isCardFlipped = !this.state.isCardFlipped;
    const cardEl = document.getElementById('flashcard-flipper');
    if (cardEl) {
      cardEl.classList.toggle('card-flipped', this.state.isCardFlipped);
    }
  },

  nextFlashcard(mastered = false) {
    if (mastered) {
      // Record mastery event
      const current = this.state.flashcards[this.state.currentCardIndex];
      if (current) {
        fetch('/api/v1/mastery/event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic_id: current.topic,
            is_correct: true,
            event_type: 'flashcard_review'
          })
        }).catch(() => {});
      }
    }

    if (this.state.currentCardIndex < this.state.flashcards.length - 1) {
      this.state.currentCardIndex++;
      this.state.isCardFlipped = false;
      this.renderFlashcard();
    }
  },

  prevFlashcard() {
    if (this.state.currentCardIndex > 0) {
      this.state.currentCardIndex--;
      this.state.isCardFlipped = false;
      this.renderFlashcard();
    }
  },

  renderFlashcard() {
    const card = this.state.flashcards[this.state.currentCardIndex];
    if (!card) return;

    document.getElementById('flashcard-counter').textContent = `Card ${this.state.currentCardIndex + 1} of ${this.state.flashcards.length}`;
    document.getElementById('flashcard-topic').textContent = card.topic;
    document.getElementById('flashcard-question').textContent = card.question;
    document.getElementById('flashcard-answer').textContent = card.answer;
    document.getElementById('flashcard-citation').textContent = `⏱️ ${card.citation}`;

    const flipper = document.getElementById('flashcard-flipper');
    if (flipper) flipper.classList.toggle('card-flipped', this.state.isCardFlipped);
  },

  // -----------------------------
  // Knowledge Quiz Arena
  // -----------------------------
  async loadQuiz() {
    try {
      const res = await fetch('/api/v1/study/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: this.state.selectedSource })
      });
      const data = await res.json();
      this.state.quizQuestions = data.questions || [];
      this.state.currentQuizIndex = 0;
      this.state.quizScore = 0;
      this.state.quizSelectedOption = null;
      this.state.quizAnswered = false;
      this.state.quizCompleted = false;
      this.renderQuizQuestion();
    } catch (err) {
      console.error('Error loading quiz:', err);
    }
  },

  selectQuizOption(index) {
    if (this.state.quizAnswered) return;
    this.state.quizSelectedOption = index;
    this.state.quizAnswered = true;

    const q = this.state.quizQuestions[this.state.currentQuizIndex];
    const isCorrect = index === q.correct_index;
    if (isCorrect) this.state.quizScore++;

    // Record learning event
    fetch('/api/v1/mastery/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic_id: `Quiz Question ${q.id}`,
        is_correct: isCorrect,
        event_type: 'quiz_answer'
      })
    }).catch(() => {});

    this.renderQuizQuestion();
  },

  nextQuizQuestion() {
    if (this.state.currentQuizIndex < this.state.quizQuestions.length - 1) {
      this.state.currentQuizIndex++;
      this.state.quizAnswered = false;
      this.state.quizSelectedOption = null;
      this.renderQuizQuestion();
    } else {
      this.state.quizCompleted = true;
      this.renderQuizSummary();
    }
  },

  renderQuizQuestion() {
    const container = document.getElementById('quiz-container');
    if (!container) return;
    const q = this.state.quizQuestions[this.state.currentQuizIndex];
    if (!q) return;

    const total = this.state.quizQuestions.length;
    const current = this.state.currentQuizIndex + 1;

    container.innerHTML = `
      <div class="glass-panel rounded-2xl p-8 max-w-2xl mx-auto border border-white/10 shadow-2xl">
        <div class="flex items-center justify-between text-xs text-slate-400 mb-4 pb-3 border-b border-white/10">
          <span class="font-semibold text-indigo-400 uppercase tracking-wider">Question ${current} of ${total}</span>
          <span>Score: ${this.state.quizScore} / ${this.state.currentQuizIndex}</span>
        </div>

        <h3 class="text-xl font-bold text-white mb-6 leading-snug">${this.escapeHtml(q.question)}</h3>

        <div class="space-y-3 mb-6">
          ${q.options.map((opt, idx) => {
            let btnClass = 'bg-slate-800/80 hover:bg-slate-700/80 border-white/10 text-slate-200';
            if (this.state.quizAnswered) {
              if (idx === q.correct_index) {
                btnClass = 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold';
              } else if (idx === this.state.quizSelectedOption) {
                btnClass = 'bg-rose-500/20 border-rose-500 text-rose-300';
              } else {
                btnClass = 'bg-slate-900/40 opacity-40 border-white/5';
              }
            }
            return `
              <button class="w-full text-left p-4 rounded-xl border transition-all text-sm flex items-center justify-between ${btnClass}"
                      onclick="App.selectQuizOption(${idx})" ${this.state.quizAnswered ? 'disabled' : ''}>
                <span>${this.escapeHtml(opt)}</span>
                ${this.state.quizAnswered && idx === q.correct_index ? '<i data-lucide="check" class="w-4 h-4 text-emerald-400"></i>' : ''}
                ${this.state.quizAnswered && idx === this.state.quizSelectedOption && idx !== q.correct_index ? '<i data-lucide="x" class="w-4 h-4 text-rose-400"></i>' : ''}
              </button>
            `;
          }).join('')}
        </div>

        ${this.state.quizAnswered ? `
          <div class="p-4 rounded-xl bg-slate-900/80 border border-white/10 mb-6 text-sm">
            <h5 class="font-bold text-indigo-300 mb-1 flex items-center gap-1.5">
              <i data-lucide="info" class="w-4 h-4"></i> Explanation:
            </h5>
            <p class="text-slate-300 leading-relaxed">${this.escapeHtml(q.explanation)}</p>
            <div class="mt-2 text-xs text-slate-400">Citation: ⏱️ ${q.citation}</div>
          </div>

          <div class="flex justify-end">
            <button class="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-lg transition-all"
                    onclick="App.nextQuizQuestion()">
              ${current === total ? 'View Quiz Results' : 'Next Question →'}
            </button>
          </div>
        ` : ''}
      </div>
    `;
    lucide.createIcons();
  },

  renderQuizSummary() {
    const container = document.getElementById('quiz-container');
    if (!container) return;
    const total = this.state.quizQuestions.length;
    const pct = Math.round((this.state.quizScore / total) * 100);

    container.innerHTML = `
      <div class="glass-panel rounded-2xl p-8 max-w-lg mx-auto text-center border border-white/10 shadow-2xl">
        <div class="w-20 h-20 rounded-full mx-auto mb-4 bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center text-3xl font-extrabold text-white shadow-lg">
          ${pct}%
        </div>
        <h3 class="text-2xl font-bold text-white mb-2">Quiz Completed!</h3>
        <p class="text-slate-300 text-sm mb-6">
          You scored <strong class="text-indigo-400">${this.state.quizScore} out of ${total}</strong> questions correctly.
        </p>

        <div class="flex justify-center gap-3">
          <button class="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition-all"
                  onclick="App.loadQuiz()">
            Try Again
          </button>
          <button class="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-all shadow-lg"
                  onclick="App.switchTab('mastery')">
            Check Mastery Analytics
          </button>
        </div>
      </div>
    `;
    lucide.createIcons();
  },

  // -----------------------------
  // Mastery Analytics
  // -----------------------------
  async fetchMastery() {
    try {
      const res = await fetch('/api/v1/mastery');
      const data = await res.json();
      this.state.masteryData = data;
      this.renderMastery();
    } catch (err) {
      console.error('Error fetching mastery:', err);
    }
  },

  renderMastery() {
    const data = this.state.masteryData;
    if (!data) return;

    const scoreEl = document.getElementById('mastery-score-text');
    if (scoreEl) scoreEl.textContent = `${data.overall_mastery}%`;

    const topicsEl = document.getElementById('mastery-topics-list');
    if (topicsEl) {
      topicsEl.innerHTML = data.topics.map(t => `
        <div class="p-4 rounded-xl glass-card border border-white/5">
          <div class="flex items-center justify-between mb-2">
            <span class="font-semibold text-sm text-slate-200">${this.escapeHtml(t.topic)}</span>
            <span class="text-xs font-mono font-bold text-indigo-400">${t.mastery}%</span>
          </div>
          <div class="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div class="h-full bg-gradient-to-r from-indigo-500 to-cyan-400 rounded-full" style="width: ${t.mastery}%"></div>
          </div>
        </div>
      `).join('');
    }
  },

  // -----------------------------
  // Settings
  // -----------------------------
  async saveOpenAIKey() {
    const input = document.getElementById('settings-openai-key');
    const key = input ? input.value.trim() : '';
    if (!key) return alert('Please enter a key');

    try {
      const res = await fetch('/api/v1/settings/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ openai_api_key: key })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Key update failed (${res.status})`);
      }
      alert('OpenAI API Key successfully updated!');
      this.fetchHealth();
    } catch (err) {
      alert('Error updating key: ' + err.message);
    }
  },

  // -----------------------------
  // Utility Helpers
  // -----------------------------
  formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  },

  parseTimeToSeconds(timeStr) {
    const parts = timeStr.split(':').map(Number);
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    return 0;
  },

  formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  },

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m]));
  }
};

window.App = App;
document.addEventListener('DOMContentLoaded', () => App.init());
