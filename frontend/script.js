document.addEventListener('DOMContentLoaded', () => {
    const uploadBtn = document.getElementById('upload-btn');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    const refreshDocsBtn = document.getElementById('refresh-docs-btn');
    const documentList = document.getElementById('document-list');
    const chatHistory = document.getElementById('chat-history');
    const questionInput = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    
    let currentDocFilter = null;
    let isStreaming = false;

    // Empty when FastAPI serves this page; set in config.js when the
    // frontend is hosted separately (see frontend/config.js).
    const API_BASE = (window.API_BASE || '').replace(/\/+$/, '');
    const apiUrl = (path) => `${API_BASE}${path}`;

    // Load initial documents and analytics
    fetchDocuments();
    fetchAnalytics();
    
    // Load dynamic FAQs based on documents
    fetchDynamicFAQs();

    // Event Listeners
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);
    refreshDocsBtn.addEventListener('click', fetchDocuments);
    
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });
    
    sendBtn.addEventListener('click', sendQuestion);
    
    questionInput.addEventListener('input', () => {
        sendBtn.disabled = questionInput.value.trim().length === 0 || isStreaming;
    });

    const faqContainer = document.getElementById('faq-container');

    async function fetchDocuments() {
        try {
            const res = await fetch(apiUrl('/documents'));
            if (!res.ok) throw new Error('Failed to fetch documents');
            const data = await res.json();
            renderDocuments(data.documents);
        } catch (err) {
            console.error(err);
        }
    }

    async function fetchDynamicFAQs(docFilter = null) {
        const faqSpinner = document.getElementById('faq-spinner');
        const faqGrid = document.getElementById('faq-grid');
        const emptyState = document.getElementById('empty-state');
        const faqContainer = document.getElementById('faq-container');
        
        if (!docFilter) {
            if (emptyState) emptyState.classList.remove('hidden');
            if (faqContainer) faqContainer.classList.add('hidden');
            return;
        } else {
            if (emptyState) emptyState.classList.add('hidden');
            if (faqContainer) faqContainer.classList.remove('hidden');
        }
        
        if (!faqSpinner || !faqGrid) return;
        
        faqGrid.innerHTML = '';
        faqSpinner.classList.remove('hidden');
        
        const url = docFilter ? apiUrl('/faq/dynamic?doc_filter=' + encodeURIComponent(docFilter)) : apiUrl('/faq/dynamic');
        
        try {
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (data.questions && data.questions.length > 0) {
                    faqGrid.innerHTML = data.questions.map(q => `<button class="faq-btn">${q}</button>`).join('');
                    
                    const newBtns = faqGrid.querySelectorAll('.faq-btn');
                    newBtns.forEach(btn => {
                        btn.addEventListener('click', () => {
                            questionInput.value = btn.textContent.trim();
                            sendQuestion();
                        });
                    });
                }
            }
        } catch (err) {
            console.error('Failed to fetch dynamic FAQs', err);
        } finally {
            faqSpinner.classList.add('hidden');
        }
    }

    // --- Analytics -------------------------------------------------------

    const analyticsModal = document.getElementById('analytics-modal');
    const analyticsBody = document.getElementById('analytics-body');
    const analyticsMoreBtn = document.getElementById('analytics-more');
    const analyticsCloseBtn = document.getElementById('analytics-close');

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }

    function fmtNum(n) {
        if (n === null || n === undefined) return '—';
        if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e4) return (n / 1e3).toFixed(1) + 'k';
        return String(n);
    }

    function fmtBytes(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let value = bytes;
        while (value >= 1024 && i < units.length - 1) { value /= 1024; i++; }
        return `${value < 10 && i > 0 ? value.toFixed(1) : Math.round(value)} ${units[i]}`;
    }

    function fmtMs(ms) {
        if (!ms) return '—';
        return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
    }

    function fmtDate(iso) {
        if (!iso) return '—';
        const d = new Date(iso);
        if (isNaN(d)) return '—';
        return d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    async function fetchAnalytics() {
        try {
            const res = await fetch(apiUrl('/analytics'));
            if (res.ok) {
                const data = await res.json();
                renderAnalyticsSummary(data);
                if (analyticsModal && !analyticsModal.classList.contains('hidden')) {
                    renderDiagnostics(data);
                }
            }
        } catch (err) {
            console.error('Failed to fetch analytics', err);
        }
    }

    function renderAnalyticsSummary(data) {
        const totals = data.totals || {};
        const queries = data.queries || {};
        const set = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };
        set('stat-docs', fmtNum(totals.documents ?? data.total_documents ?? 0));
        set('stat-pages', fmtNum(totals.pages ?? data.total_pages ?? 0));
        set('stat-chunks', fmtNum(totals.chunks ?? 0));
        set('stat-tokens', fmtNum(totals.tokens_est ?? 0));
        set('stat-index', fmtBytes(totals.index_size_bytes ?? 0));
        set('stat-queries', fmtNum(queries.total_queries ?? 0));
    }

    function row(key, value) {
        return `<div class="diag-row"><span class="diag-key">${escapeHtml(key)}</span>` +
               `<span class="diag-val">${escapeHtml(value)}</span></div>`;
    }

    function renderHistogram(histogram) {
        if (!histogram || !histogram.length) return '';
        const max = Math.max(...histogram.map(b => b.count), 1);
        const bars = histogram.map(b => {
            const pct = (b.count / max) * 100;
            return `<div class="hist-col" title="${b.start}–${b.end} chars: ${b.count} chunk(s)">
                        <span class="hist-count">${b.count || ''}</span>
                        <div class="hist-bar ${b.count ? '' : 'empty'}" style="height:${b.count ? Math.max(pct, 3) : 2}%"></div>
                    </div>`;
        }).join('');
        const ticks = histogram.map(b => `<span class="hist-tick">${b.start}</span>`).join('');
        return `<div class="diag-hist">${bars}</div><div class="hist-axis">${ticks}</div>
                <p class="diag-note">Chunk length in characters — buckets span 0 to the configured chunk size.</p>`;
    }

    function renderDiagnostics(data) {
        if (!analyticsBody) return;

        const totals = data.totals || {};
        const pipe = data.pipeline || {};
        const chunking = data.chunking || {};
        const dist = chunking.distribution;
        const queries = data.queries || {};
        const docs = data.documents || [];

        const sections = [];

        // Corpus totals
        sections.push(`
            <div class="diag-section">
                <div class="diag-heading">Corpus</div>
                <div class="diag-kv">
                    ${row('Documents', totals.documents ?? 0)}
                    ${row('Pages', totals.pages ?? 0)}
                    ${row('Chunks / vectors', totals.chunks ?? 0)}
                    ${row('Avg chunks / doc', totals.avg_chunks_per_doc ?? 0)}
                    ${row('Characters indexed', (totals.characters ?? 0).toLocaleString())}
                    ${row('Tokens (est. chars/4)', (totals.tokens_est ?? 0).toLocaleString())}
                    ${row('Source files on disk', fmtBytes(totals.source_bytes))}
                    ${row('Vector index on disk', fmtBytes(totals.index_size_bytes))}
                </div>
            </div>`);

        // Pipeline configuration
        sections.push(`
            <div class="diag-section">
                <div class="diag-heading">Pipeline</div>
                <div class="diag-kv">
                    ${row('Chunk size', `${pipe.chunk_size} chars`)}
                    ${row('Chunk overlap', `${pipe.chunk_overlap} (${pipe.overlap_pct}%)`)}
                    ${row('Splitter', pipe.splitter)}
                    ${row('Separators', (pipe.separators || []).map(s => `"${s}"`).join(' → '))}
                    ${row('Top-K retrieved', pipe.top_k)}
                    ${row('Distance metric', pipe.distance_metric)}
                    ${row('Embedding model', pipe.embedding_model)}
                    ${row('Embedding dims', pipe.embedding_dimensions ?? '—')}
                    ${row('LLM backend', pipe.llm_backend)}
                    ${row('LLM model', pipe.llm_model)}
                    ${row('Temperature', pipe.temperature ?? '—')}
                    ${row('Collection', pipe.collection)}
                </div>
                <div class="diag-row" style="margin-top:6px">
                    <span class="diag-key">Persist dir</span>
                    <span class="diag-val">${escapeHtml(pipe.persist_dir || '—')}</span>
                </div>
            </div>`);

        // Chunk size distribution
        sections.push(`
            <div class="diag-section">
                <div class="diag-heading">Chunk size distribution</div>
                ${dist ? `
                    <div class="diag-kv" style="margin-bottom:14px">
                        ${row('Min', `${dist.min} chars`)}
                        ${row('Median (p50)', `${dist.p50} chars`)}
                        ${row('Mean', `${dist.mean} chars`)}
                        ${row('p95', `${dist.p95} chars`)}
                        ${row('Max', `${dist.max} chars`)}
                        ${row('Fill ratio', `${Math.round((dist.mean / (pipe.chunk_size || 1)) * 100)}% of chunk size`)}
                    </div>
                    ${renderHistogram(chunking.histogram)}
                ` : '<p class="diag-empty">No chunks indexed yet.</p>'}
            </div>`);

        // Per-document breakdown
        const docRows = docs.map(d => `
            <tr>
                <td class="diag-name">${escapeHtml(d.filename)}</td>
                <td>${escapeHtml(d.file_type)}</td>
                <td>${d.pages || '—'}</td>
                <td>${d.chunks}</td>
                <td>${(d.characters || 0).toLocaleString()}</td>
                <td>${d.avg_chunk_chars}</td>
                <td>${fmtBytes(d.size_bytes)}</td>
                <td>${escapeHtml(fmtDate(d.indexed_at))}</td>
            </tr>`).join('');

        sections.push(`
            <div class="diag-section">
                <div class="diag-heading">Documents (${docs.length})</div>
                ${docs.length ? `
                    <table class="diag-table">
                        <thead><tr>
                            <th>File</th><th>Type</th><th>Pages</th><th>Chunks</th>
                            <th>Chars</th><th>Avg</th><th>Size</th><th>Indexed</th>
                        </tr></thead>
                        <tbody>${docRows}</tbody>
                    </table>
                    <p class="diag-note">Pages are reported by the PDF reader; TXT and DOCX files have no page count.</p>
                ` : '<p class="diag-empty">No documents indexed yet.</p>'}
            </div>`);

        // Retrieval / query telemetry
        const topRows = (queries.top_questions || []).map(q => `
            <tr><td class="diag-name">${escapeHtml(q.question)}</td><td>${q.count}</td></tr>`).join('');
        const recentRows = (queries.recent || []).slice(0, 5).map(q => `
            <tr>
                <td class="diag-name">${escapeHtml(q.question)}</td>
                <td>${escapeHtml(fmtMs(q.latency_ms))}</td>
                <td>${q.chunks_retrieved}</td>
                <td>${escapeHtml(fmtDate(q.at))}</td>
            </tr>`).join('');

        sections.push(`
            <div class="diag-section">
                <div class="diag-heading">Retrieval &amp; latency</div>
                <div class="diag-kv" style="margin-bottom:14px">
                    ${row('Queries answered', queries.total_queries ?? 0)}
                    ${row('Logged (rolling)', queries.logged_queries ?? 0)}
                    ${row('Mean latency', fmtMs(queries.avg_latency_ms))}
                    ${row('Median (p50)', fmtMs(queries.p50_latency_ms))}
                    ${row('p95 latency', fmtMs(queries.p95_latency_ms))}
                    ${row('Slowest', fmtMs(queries.max_latency_ms))}
                    ${row('Avg chunks used', queries.avg_chunks_retrieved ?? 0)}
                </div>
                ${topRows ? `
                    <table class="diag-table" style="margin-bottom:16px">
                        <thead><tr><th>Most asked</th><th>Count</th></tr></thead>
                        <tbody>${topRows}</tbody>
                    </table>` : ''}
                ${recentRows ? `
                    <table class="diag-table">
                        <thead><tr><th>Recent query</th><th>Latency</th><th>Chunks</th><th>When</th></tr></thead>
                        <tbody>${recentRows}</tbody>
                    </table>` : '<p class="diag-empty">No questions asked yet.</p>'}
            </div>`);

        analyticsBody.innerHTML = sections.join('');
    }

    async function openDiagnostics() {
        analyticsBody.innerHTML = '<p class="diag-empty">Loading…</p>';
        analyticsModal.classList.remove('hidden');
        try {
            const res = await fetch(apiUrl('/analytics'));
            if (!res.ok) throw new Error('Failed to load analytics');
            const data = await res.json();
            renderAnalyticsSummary(data);
            renderDiagnostics(data);
        } catch (err) {
            console.error(err);
            analyticsBody.innerHTML = '<p class="diag-empty">Could not load diagnostics.</p>';
        }
    }

    function closeDiagnostics() {
        analyticsModal.classList.add('hidden');
    }

    if (analyticsMoreBtn) analyticsMoreBtn.addEventListener('click', openDiagnostics);
    if (analyticsCloseBtn) analyticsCloseBtn.addEventListener('click', closeDiagnostics);
    if (analyticsModal) {
        analyticsModal.addEventListener('click', (e) => {
            if (e.target === analyticsModal) closeDiagnostics();
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && analyticsModal && !analyticsModal.classList.contains('hidden')) {
            closeDiagnostics();
        }
    });

    function renderDocuments(docs) {
        documentList.innerHTML = '';
        if (docs.length === 0) {
            documentList.innerHTML = '<li class="doc-item" style="cursor:default">No documents found</li>';
            return;
        }
        
        docs.forEach(doc => {
            const li = document.createElement('li');
            li.className = 'doc-item-container';
            
            const docBtn = document.createElement('div');
            docBtn.className = 'doc-item';
            if (currentDocFilter === doc) {
                docBtn.classList.add('selected');
            }
            
            docBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <span>${doc}</span>
            `;
            
            docBtn.addEventListener('click', () => {
                if (currentDocFilter === doc) {
                    currentDocFilter = null;
                    docBtn.classList.remove('selected');
                } else {
                    document.querySelectorAll('.doc-item').forEach(el => el.classList.remove('selected'));
                    currentDocFilter = doc;
                    docBtn.classList.add('selected');
                }
                fetchDynamicFAQs(currentDocFilter);
            });
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-doc-btn';
            deleteBtn.title = "Delete document";
            deleteBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            `;
            
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Are you sure you want to delete ${doc}?`)) {
                    await deleteDocument(doc);
                }
            });
            
            li.appendChild(docBtn);
            li.appendChild(deleteBtn);
            documentList.appendChild(li);
        });
    }

    async function deleteDocument(filename) {
        try {
            const res = await fetch(apiUrl(`/documents/${encodeURIComponent(filename)}`), {
                method: 'DELETE'
            });
            if (!res.ok) {
                const data = await res.json();
                alert(`Error deleting document: ${data.detail || 'Unknown error'}`);
                return;
            }
            if (currentDocFilter === filename) {
                currentDocFilter = null;
            }
            clearChat();
            fetchDocuments();
            fetchAnalytics();
            fetchDynamicFAQs(currentDocFilter);
        } catch (err) {
            console.error(err);
            alert('Failed to delete document');
        }
    }

    function clearChat() {
        // Remove only the message nodes: #empty-state and #faq-container are
        // children of #chat-history and must survive so they can be re-shown.
        chatHistory.querySelectorAll('.message').forEach(el => el.remove());
        chatHistory.scrollTop = 0;
    }

    async function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        uploadStatus.innerHTML = '<span class="spinner"></span> Uploading...';
        uploadStatus.classList.remove('hidden');
        uploadStatus.style.color = 'var(--text-muted)';
        
        try {
            const res = await fetch(apiUrl('/upload'), {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (res.ok) {
                uploadStatus.textContent = 'File indexed successfully.';
                uploadStatus.style.color = 'var(--success-color)';
                fetchDocuments();
                fetchAnalytics();
                fetchDynamicFAQs(currentDocFilter);
            } else {
                uploadStatus.textContent = data.detail || 'Upload failed';
                uploadStatus.style.color = 'red';
            }
        } catch (err) {
            uploadStatus.textContent = 'Upload error';
            uploadStatus.style.color = 'red';
        }
        
        fileInput.value = '';
    }

    async function sendQuestion() {
        const text = questionInput.value.trim();
        if (!text || isStreaming) return;
        
        if (faqContainer) {
            faqContainer.classList.add('hidden');
        }
        const emptyState = document.getElementById('empty-state');
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
        
        questionInput.value = '';
        sendBtn.disabled = true;
        
        appendUserMessage(text);
        
        const loadingOverlay = document.getElementById('loading-overlay');
        const loadingQuestion = document.getElementById('loading-question');
        loadingQuestion.textContent = `"${text}"`;
        loadingOverlay.classList.remove('hidden');
        
        let botMessageElements = null;
        let isOverlayHidden = false;
        
        isStreaming = true;
        
        try {
            const res = await fetch(apiUrl('/ask/stream'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text, doc_filter: currentDocFilter })
            });
            
            if (!res.ok) {
                loadingOverlay.classList.add('hidden');
                isOverlayHidden = true;
                botMessageElements = appendBotMessagePlaceholder();
                const data = await res.json();
                botMessageElements.botContent.innerHTML = `<p style="color:red">Error: ${data.detail || 'Failed to ask question'}</p>`;
                isStreaming = false;
                return;
            }
            
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            
            let accumulatedHTML = '';
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (!dataStr) continue;
                        
                        const data = JSON.parse(dataStr);
                        
                        if (!isOverlayHidden && (data.token || data.done)) {
                            loadingOverlay.classList.add('hidden');
                            botMessageElements = appendBotMessagePlaceholder();
                            isOverlayHidden = true;
                        }
                        
                        if (data.token) {
                            accumulatedHTML += data.token;
                            botMessageElements.botContent.innerHTML = typeof marked !== 'undefined' ? marked.parse(accumulatedHTML) : accumulatedHTML;
                            chatHistory.scrollTop = chatHistory.scrollHeight;
                        } else if (data.done) {
                            if (data.answer) {
                                botMessageElements.botContent.innerHTML = typeof marked !== 'undefined' ? marked.parse(data.answer) : data.answer;
                            }
                            if (data.sources && data.sources.length > 0) {
                                botMessageElements.sourceSection.classList.remove('hidden');
                                botMessageElements.sourceList.innerHTML = data.sources.map(s => `<div>${s}</div>`).join('');
                            }
                        }
                    }
                }
            }
        } catch (err) {
            console.error(err);
            if (!isOverlayHidden) {
                loadingOverlay.classList.add('hidden');
                botMessageElements = appendBotMessagePlaceholder();
            }
            botMessageElements.botContent.innerHTML = `<p style="color:red">Connection error.</p>`;
        } finally {
            isStreaming = false;
            sendBtn.disabled = questionInput.value.trim().length === 0;
            if (!isOverlayHidden) {
                loadingOverlay.classList.add('hidden');
            }
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    function appendUserMessage(text) {
        const template = document.getElementById('user-msg-template');
        const clone = template.content.cloneNode(true);
        clone.querySelector('.message-bubble').textContent = text;
        chatHistory.appendChild(clone);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function appendBotMessagePlaceholder() {
        const template = document.getElementById('bot-msg-template');
        const clone = template.content.cloneNode(true);
        const botContent = clone.querySelector('.bot-content');
        const sourceSection = clone.querySelector('.source-section');
        const sourceList = clone.querySelector('.source-list');
        
        botContent.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
        
        chatHistory.appendChild(clone);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        return { botContent, sourceSection, sourceList };
    }
});
