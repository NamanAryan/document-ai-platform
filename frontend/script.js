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
            const res = await fetch('/documents');
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
        
        const url = docFilter ? '/faq/dynamic?doc_filter=' + encodeURIComponent(docFilter) : '/faq/dynamic';
        
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

    async function fetchAnalytics() {
        try {
            const res = await fetch('/analytics');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('stat-docs').textContent = data.total_documents;
                document.getElementById('stat-pages').textContent = data.total_pages;
            }
        } catch (err) {
            console.error('Failed to fetch analytics', err);
        }
    }

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
            const res = await fetch(`/documents/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });
            if (!res.ok) {
                const data = await res.json();
                alert(`Error deleting document: ${data.detail || 'Unknown error'}`);
                return;
            }
            if (currentDocFilter === filename) {
                currentDocFilter = null;
                fetchDynamicFAQs(null);
            }
            fetchDocuments();
            fetchAnalytics();
        } catch (err) {
            console.error(err);
            alert('Failed to delete document');
        }
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
            const res = await fetch('/upload', {
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
            const res = await fetch('/ask/stream', {
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
