/* ============================================================
   Transkriptör — sohbet arayüzü mantığı
   Akış: SS/link at → bot videoları bulur → kartlı balonla döner
   Backend API'leri değişmedi: /api/ocr, /api/search,
   /api/transcribe, /api/detailed_summary
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();

    const state = {
        videos: {}, // video_id -> API yanıtı (video, transcript)
        processingVideoIds: new Set(),
        timer: {
            startAt: null,
            intervalId: null,
            total: 0,
            completed: 0,
            active: false
        }
    };

    const body = document.body;
    const messages = document.getElementById("messages");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const attachBtn = document.getElementById("attach-btn");
    const fileInput = document.getElementById("file-input");
    const dragOverlay = document.getElementById("drag-overlay");
    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    const toastContainer = document.getElementById("toast-container");
    const processTimer = document.getElementById("process-timer");
    const timerLabel = document.getElementById("timer-label");
    const timerElapsed = document.getElementById("timer-elapsed");

    /* ---------- Tema ---------- */
    function initTheme() {
        const saved = localStorage.getItem("theme");
        const preferLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
        const light = saved ? saved === "light" : preferLight;
        body.classList.toggle("light-theme", light);
        body.classList.toggle("dark-theme", !light);
    }
    themeToggleBtn.addEventListener("click", () => {
        const light = body.classList.contains("light-theme");
        body.classList.toggle("light-theme", !light);
        body.classList.toggle("dark-theme", light);
        localStorage.setItem("theme", light ? "dark" : "light");
    });
    initTheme();

    /* ---------- Yardımcılar ---------- */
    function escapeHTML(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function formatTime(seconds) {
        const sec = Math.floor(seconds || 0);
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = sec % 60;
        if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
        return `${m}:${String(s).padStart(2, "0")}`;
    }

    function updateTimerLabel(label) {
        if (timerLabel) timerLabel.textContent = label;
    }

    function startProcessTimer(total = 1) {
        state.timer.startAt = Date.now();
        state.timer.total = Math.max(1, total);
        state.timer.completed = 0;
        state.timer.active = true;
        processTimer.classList.add("active");
        updateTimerLabel(`0/${state.timer.total} işleniyor`);
        timerElapsed.textContent = "0:00";

        if (state.timer.intervalId) clearInterval(state.timer.intervalId);
        state.timer.intervalId = setInterval(() => {
            timerElapsed.textContent = formatTime((Date.now() - state.timer.startAt) / 1000);
        }, 1000);
    }

    function completeTimedItem() {
        if (!state.timer.active) return;
        state.timer.completed = Math.min(state.timer.completed + 1, state.timer.total);
        timerElapsed.textContent = formatTime((Date.now() - state.timer.startAt) / 1000);

        if (state.timer.completed >= state.timer.total) {
            state.timer.active = false;
            if (state.timer.intervalId) {
                clearInterval(state.timer.intervalId);
                state.timer.intervalId = null;
            }
            updateTimerLabel(`Bitti: ${state.timer.completed}/${state.timer.total}`);
            processTimer.classList.remove("active");
        } else {
            updateTimerLabel(`${state.timer.completed}/${state.timer.total} tamamlandı`);
        }
    }

    function extractVideoTargets(text) {
        const targets = [];
        const seen = new Set();
        const urlRegex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?[^ \n\r\t]*?v=|shorts\/|embed\/)|youtu\.be\/)[^\s,;]+/gi;
        const idRegex = /^[a-zA-Z0-9_-]{11}$/;

        for (const match of text.matchAll(urlRegex)) {
            const target = match[0].trim();
            if (!seen.has(target)) {
                targets.push(target);
                seen.add(target);
            }
        }

        for (const part of text.split(/[\s,;]+/)) {
            const target = part.trim();
            if (idRegex.test(target) && !seen.has(target)) {
                targets.push(target);
                seen.add(target);
            }
        }

        return targets;
    }

    function copyToClipboard(text, msg = "Panoya kopyalandı.") {
        navigator.clipboard.writeText(text)
            .then(() => showToast("Başarılı", msg, "success"))
            .catch(() => showToast("Hata", "Panoya kopyalanamadı.", "error"));
    }

    function downloadAsTxt(filename, text) {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    function showToast(title, message, type = "success") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        let icon = "check-circle";
        if (type === "warning") icon = "alert-triangle";
        if (type === "error") icon = "alert-circle";
        toast.innerHTML = `
            <div class="toast-icon"><i data-lucide="${icon}"></i></div>
            <div>
                <div class="toast-title">${escapeHTML(title)}</div>
                <div class="toast-message">${escapeHTML(message)}</div>
            </div>`;
        toastContainer.appendChild(toast);
        lucide.createIcons();
        setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    /* ---------- Mesaj balonları ---------- */
    function addMessage(role) {
        const msg = document.createElement("div");
        msg.className = `msg ${role}`;
        const avatarIcon = role === "bot" ? "sparkles" : "user";
        msg.innerHTML = `
            <div class="msg-avatar"><i data-lucide="${avatarIcon}"></i></div>
            <div class="bubble"></div>`;
        messages.appendChild(msg);
        lucide.createIcons();
        return msg.querySelector(".bubble");
    }

    function addUserText(text) {
        addMessage("user").innerHTML = `<p>${escapeHTML(text)}</p>`;
    }

    function addUserImage(base64) {
        const bubble = addMessage("user");
        const img = document.createElement("img");
        img.className = "pasted-image";
        img.src = base64;
        img.alt = "Ekran görüntüsü";
        bubble.appendChild(img);
    }

    function addBotText(html) {
        const bubble = addMessage("bot");
        bubble.innerHTML = `<p>${html}</p>`;
        return bubble;
    }

    function addTyping(text = "Yazıyor") {
        const bubble = addMessage("bot");
        bubble.innerHTML = `
            <div class="typing">
                <span class="typing-text">${escapeHTML(text)}</span>
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>`;
        return {
            update(newText) {
                const el = bubble.querySelector(".typing-text");
                if (el) el.textContent = newText;
            },
            bubble,
            remove() { bubble.closest(".msg").remove(); }
        };
    }

    /* ---------- Markdown yardımcıları ---------- */
    function parseMarkdownToHTML(md) {
        if (!md) return "";
        let html = md.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        html = html.replace(/^(🎯|📚|💡|✅)\s*(.*$)/gim, "<h4>$1 $2</h4>");
        html = html.replace(/^#{1,4}\s+(.*$)/gim, "<h4>$1</h4>");
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        const lines = html.split("\n");
        let inList = false;
        const out = [];
        for (const line of lines) {
            const t = line.trim();
            if (t.startsWith("- ") || t.startsWith("* ")) {
                if (!inList) { out.push("<ul>"); inList = true; }
                out.push("<li>" + t.substring(2) + "</li>");
            } else {
                if (inList) { out.push("</ul>"); inList = false; }
                out.push(line);
            }
        }
        if (inList) out.push("</ul>");
        html = out.join("\n").replace(/\n\n/g, "</p><p>");
        return `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, "");
    }

    /* ---------- Görsel yükleme: paste / drop / dosya ---------- */
    attachBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleImageFile(e.target.files[0]);
        fileInput.value = "";
    });

    document.addEventListener("paste", (e) => {
        const items = (e.clipboardData || {}).items || [];
        for (const item of items) {
            if (item.type && item.type.startsWith("image/")) {
                e.preventDefault();
                handleImageFile(item.getAsFile());
                return;
            }
        }
    });

    let dragCounter = 0;
    document.addEventListener("dragenter", (e) => {
        e.preventDefault();
        dragCounter++;
        dragOverlay.classList.add("active");
    });
    document.addEventListener("dragover", (e) => e.preventDefault());
    document.addEventListener("dragleave", (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) { dragCounter = 0; dragOverlay.classList.remove("active"); }
    });
    document.addEventListener("drop", (e) => {
        e.preventDefault();
        dragCounter = 0;
        dragOverlay.classList.remove("active");
        const file = e.dataTransfer.files && e.dataTransfer.files[0];
        if (file && file.type.startsWith("image/")) handleImageFile(file);
    });

    function handleImageFile(file) {
        if (!file || !file.type.startsWith("image/")) {
            showToast("Hata", "Lütfen sadece görsel dosyası yükleyin.", "error");
            return;
        }
        const reader = new FileReader();
        reader.onloadend = () => {
            addUserImage(reader.result);
            runOcrFlow(reader.result);
        };
        reader.readAsDataURL(file);
    }

    /* ---------- SS akışı: OCR → arama → tam transkript ---------- */
    async function runOcrFlow(base64Image) {
        const typing = addTyping("Görüntüdeki videolar tespit ediliyor");
        let candidates;
        try {
            const res = await fetch("/api/ocr", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: base64Image })
            });
            const data = await res.json();
            if (!data.success) throw new Error(data.error);
            candidates = data.videos || [];
        } catch (err) {
            typing.remove();
            addBotText(`Görseli analiz edemedim 😕 ${escapeHTML(err.message || "Sunucu hatası oluştu.")}`);
            return;
        }
        typing.remove();

        if (candidates.length === 0) {
            addBotText("Bu görüntüde YouTube videosu bulamadım. Video başlıklarının net göründüğü bir ekran görüntüsü dener misin?");
            return;
        }

        // OCR can return the same card more than once when a title wraps or
        // the thumbnail text is read as a second row. Remove exact OCR
        // duplicates before starting the timer and network work.
        const uniqueCandidates = [];
        const candidateKeys = new Set();
        for (const candidate of candidates) {
            const key = String(candidate.title || "")
                .toLocaleLowerCase("tr-TR")
                .replace(/[^a-z0-9ğüşöçıİĞÜŞÖÇ]+/gi, "");
            if (!key || candidateKeys.has(key)) continue;
            candidateKeys.add(key);
            uniqueCandidates.push(candidate);
        }

        const selected = uniqueCandidates.slice(0, 6);
        const extraCount = uniqueCandidates.length - selected.length;
        addBotText(`Görüntüde <strong>${selected.length} aday video</strong> tespit edildi ✨ Hepsini aynı anda kontrol edip transkriptlerini alıyorum.${extraCount > 0 ? ` Kalan ${extraCount} aday şimdilik bekletildi.` : ""}`);

        startProcessTimer(selected.length);
        // All selected videos start together. Promise.all preserves the
        // screenshot order in the returned array even when one finishes first.
        const batchResults = (await Promise.all(
            selected.map((candidate, index) => processCandidate(
                candidate,
                index + 1,
                selected.length,
                { batchIndex: index + 1, batchTotal: selected.length }
            ))
        )).filter(Boolean);
        renderCopyAllButton(batchResults);

        addBotText(`Bitti! ✅ <strong>${batchResults.length}/${selected.length} video</strong> bulundu ve transkripti alındı. Başka ekran görüntüsü ya da link atabilirsin.`);
    }

    async function processCandidate(cand, index, total, options = {}) {
        const label = cand.title || "Video";
        const typing = addTyping(`(${index}/${total}) "${label}" YouTube'da aranıyor`);
        try {
            // 1. YouTube'da bul
            let searchRes = await fetch("/api/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: cand.title || "", channel: cand.channel || "" })
            });
            let searchData = await searchRes.json();
            // OCR may slightly corrupt the channel name. Retry by title only
            // before giving up on an otherwise readable video.
            if (!searchData.success && cand.channel) {
                searchRes = await fetch("/api/search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title: cand.title || "", channel: "" })
                });
                searchData = await searchRes.json();
            }
            if (!searchData.success) {
                typing.remove();
                addBotText(`⚠️ "<strong>${escapeHTML(label)}</strong>" YouTube'da bulunamadı, bu videoyu atlıyorum.`);
                return null;
            }

            const videoId = searchData.video.video_id;
            // Different OCR readings can still resolve to the same YouTube
            // video. Do not process the same video twice.
            if (state.processingVideoIds.has(videoId) || state.videos[videoId]) {
                typing.remove();
                return state.videos[videoId] || null;
            }
            state.processingVideoIds.add(videoId);

            // 2. Only fetch and display the original YouTube transcript.
            typing.update(`(${index}/${total}) "${label}" için tam transkript alınıyor`);
            return await transcribeIntoChat(videoId, typing, {
                trackTimer: false,
                batchIndex: index,
                batchTotal: total,
            });
        } catch (err) {
            typing.remove();
            addBotText(`⚠️ "<strong>${escapeHTML(label)}</strong>" işlenirken hata oluştu, atlıyorum.`);
        } finally {
            completeTimedItem();
        }
    }

    /* ---------- Link ve Komut Akışı ---------- */
    function sendCurrentInput() {
        const text = chatInput.value.trim();
        if (!text) return;
        chatInput.value = "";
        addUserText(text);

        // Check for discovery commands
        if (text.startsWith("/ara ") || text.startsWith("/discover ")) {
            const query = text.replace(/^\/(ara|discover)\s+/, "");
            runDiscoverFlow(query, false);
        } else if (text.startsWith("/kanal ")) {
            const channelUrl = text.replace(/^\/kanal\s+/, "");
            runDiscoverFlow(channelUrl, true);
        } else {
            const targets = extractVideoTargets(text);
            if (targets.length > 1) {
                runBatchTranscription(targets);
            } else {
                const typing = addTyping("Video transkripti alınıyor");
                transcribeIntoChat(targets[0] || text, typing);
            }
        }
    }
    sendBtn.addEventListener("click", sendCurrentInput);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendCurrentInput();
    });

    async function runBatchTranscription(targets) {
        const selected = targets.slice(0, 6);
        const extraCount = targets.length - selected.length;
        addBotText(`<strong>${selected.length} video</strong> aynı anda işleniyor.${extraCount > 0 ? ` İlk 6 video alındı, kalan ${extraCount} link bekletildi.` : ""}`);
        startProcessTimer(selected.length);

        const batchResults = (await Promise.all(
            selected.map((target, index) => {
                const typing = addTyping(`(${index + 1}/${selected.length}) Video transkripti alınıyor`);
                return transcribeIntoChat(target, typing, {
                    trackTimer: false,
                    batchIndex: index + 1,
                    batchTotal: selected.length,
                }).finally(() => completeTimedItem());
            })
        )).filter(Boolean);

        renderCopyAllButton(batchResults);
        addBotText(`Toplu işlem tamamlandı ✅ <strong>${batchResults.length}/${selected.length} video</strong> bulundu ve transkripti alındı. Toplam süre: <strong>${escapeHTML(timerElapsed.textContent)}</strong>`);
    }

    /* ---------- Arama / Kanal Keşif Akışı ---------- */
    async function runDiscoverFlow(inputVal, isChannel) {
        const titleText = isChannel ? "Kanal videoları çekiliyor..." : `"${inputVal}" araması yapılıyor...`;
        const typing = addTyping(titleText);
        try {
            const bodyObj = isChannel ? { channel_url: inputVal, max_results: 10 } : { query: inputVal, max_results: 10 };
            const res = await fetch("/api/discover", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(bodyObj)
            });
            const data = await res.json();
            typing.remove();
            
            if (data.success && data.videos && data.videos.length > 0) {
                renderDiscoveryBubble(inputVal, data.videos);
            } else {
                addBotText(`⚠️ Arama sonucunda hiç video bulunamadı veya bir hata oluştu.`);
            }
        } catch (err) {
            typing.remove();
            addBotText("⚠️ Sunucuya bağlanırken bir hata oluştu.");
        }
    }

    function renderDiscoveryBubble(query, videos) {
        const bubble = addMessage("bot");
        const batchableVideos = videos.slice(0, 6);
        
        const container = document.createElement("div");
        container.className = "discovery-container";
        container.innerHTML = `
            <p class="discovery-title">🔍 <strong>"${escapeHTML(query)}"</strong> için bulunan videolar:</p>
            <div class="discovery-toolbar">
                <button class="chip-btn primary batch-discovery-btn"><i data-lucide="list-video"></i> İlk ${batchableVideos.length} videoyu toplu işle</button>
            </div>
            <div class="discovery-list">
                ${videos.map(video => `
                    <div class="discovery-card" data-id="${escapeHTML(video.video_id)}">
                        <div class="dc-thumb">
                            <img src="${escapeHTML(video.thumbnail_url)}" alt="">
                            <span class="dc-duration">${escapeHTML(video.duration || "")}</span>
                        </div>
                        <div class="dc-info">
                            <div class="dc-title" title="${escapeHTML(video.title)}">${escapeHTML(video.title)}</div>
                            <div class="dc-channel"><i data-lucide="user"></i> ${escapeHTML(video.channel)}</div>
                            <div class="dc-actions">
                                <button class="chip-btn primary analyze-btn"><i data-lucide="file-text"></i> Transkripti Al</button>
                                <button class="chip-btn export-btn"><i data-lucide="file-down"></i> Dosyaya Aktar</button>
                            </div>
                        </div>
                    </div>
                `).join("")}
            </div>
        `;

        const batchDiscoveryBtn = container.querySelector(".batch-discovery-btn");
        batchDiscoveryBtn.addEventListener("click", () => {
            batchDiscoveryBtn.disabled = true;
            runBatchTranscription(batchableVideos.map(video => video.video_id));
        });
        
        // Add click events to buttons
        container.querySelectorAll(".discovery-card").forEach(card => {
            const videoId = card.getAttribute("data-id");
            const videoTitle = card.querySelector(".dc-title").textContent;
            
            // Portable JSON/TXT export button
            const exportBtn = card.querySelector(".export-btn");
            exportBtn.addEventListener("click", async () => {
                exportBtn.disabled = true;
                exportBtn.innerHTML = `<i data-lucide="loader" class="spin"></i> Aktarılıyor...`;
                lucide.createIcons();
                
                try {
                    const res = await fetch("/api/export", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ video_id: videoId })
                    });
                    const data = await res.json();
                    
                    if (data.success) {
                        exportBtn.className = "chip-btn success-btn";
                        exportBtn.innerHTML = `<i data-lucide="check"></i> Aktarıldı`;
                        showToast("Başarılı", `"${videoTitle}" JSON ve TXT olarak kaydedildi.`, "success");
                    } else {
                        exportBtn.disabled = false;
                        exportBtn.innerHTML = `<i data-lucide="send"></i> Yeniden Dene`;
                        showToast("Hata", data.error || "İhraç edilemedi.", "error");
                    }
                } catch (err) {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = `<i data-lucide="send"></i> Yeniden Dene`;
                    showToast("Hata", "Sunucu hatası oluştu.", "error");
                }
                lucide.createIcons();
            });
            
            // Sohbetle Özetle (Transcribe into Chat) Button
            const analyzeBtn = card.querySelector(".analyze-btn");
            analyzeBtn.addEventListener("click", () => {
                analyzeBtn.disabled = true;
                const typing = addTyping(`"${videoTitle}" için tam transkript alınıyor`);
                transcribeIntoChat(videoId, typing);
            });
        });
        
        bubble.appendChild(container);
        lucide.createIcons();
    }

    /* ---------- Transkript isteği → kartlı bot balonu ---------- */
    async function transcribeIntoChat(urlOrId, typing, options = {}) {
        const trackTimer = options.trackTimer !== false;
        if (trackTimer) startProcessTimer(1);

        try {
            const res = await fetch("/api/transcribe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: urlOrId })
            });
            const data = await res.json();
            typing.remove();

            if (data.success) {
                state.videos[data.video.video_id] = data;
                renderVideoBubble(data, options);
            } else if (data.error_type === "transcript_unavailable") {
                addBotText(`⚠️ ${escapeHTML(data.error || "Altyazı 3 denemede alınamadı. Video atlandı.")}`);
            } else {
                addBotText(`⚠️ ${escapeHTML(data.error || "Video analiz edilemedi.")}`);
            }
            return data.success ? data : null;
        } catch (err) {
            typing.remove();
            addBotText("⚠️ Sunucuya ulaşamadım, video analiz edilemedi. Tekrar dener misin?");
            return false;
        } finally {
            if (trackTimer) completeTimedItem();
        }
    }

    /* ---------- Video kartı balonu ---------- */
    function renderVideoBubble(videoData, options = {}) {
        const video = videoData.video;
        const transcript = videoData.transcript || [];
        const bubble = addMessage("bot");

        const orderLabel = options.batchIndex ? `${options.batchIndex}. Video Transkripti` : "Video Transkripti";

        const card = document.createElement("div");
        card.className = "video-card";
        card.innerHTML = `
            <div class="transcript-order">${orderLabel}</div>
            <div class="vc-head">
                <div class="vc-thumb">
                    <img src="${escapeHTML(video.thumbnail_url)}" alt="">
                    <span class="vc-duration">${escapeHTML(video.duration || "")}</span>
                </div>
                <div class="vc-info">
                    <div class="vc-title">${escapeHTML(video.title)}</div>
                    <div class="vc-channel"><i data-lucide="user"></i> ${escapeHTML(video.channel)}</div>
                </div>
            </div>
            <div class="vc-actions">
                <button class="chip-btn copy-btn"><i data-lucide="copy"></i> Kopyala</button>
                <button class="chip-btn download-btn"><i data-lucide="download"></i> TXT</button>
            </div>
            <div class="transcript-section active">
                <div class="transcript-container">
                    ${transcript.map(line => `
                        <div class="transcript-line">
                            <a class="line-time" target="_blank"
                               href="https://www.youtube.com/watch?v=${encodeURIComponent(video.video_id)}&t=${Math.floor(line.start || 0)}s">
                               ${escapeHTML(formatTime(line.start))}</a>
                            <span class="line-text">${escapeHTML(line.text)}</span>
                        </div>`).join("")}
                </div>
            </div>`;

        card.querySelector(".copy-btn").addEventListener("click", () => {
            const raw = formatTranscriptForCopy(video, transcript);
            copyToClipboard(raw, "Transkript panoya kopyalandı.");
        });
        card.querySelector(".download-btn").addEventListener("click", () => {
            const txt = formatTranscriptForCopy(video, transcript);
            downloadAsTxt(`transkript_${video.video_id}.txt`, txt);
        });

        bubble.appendChild(card);
        lucide.createIcons();
    }

    function formatTranscriptForCopy(video, transcript) {
        const link = `https://www.youtube.com/watch?v=${video.video_id}`;
        const lines = transcript.map(line => `[${formatTime(line.start)}] ${line.text}`).join("\n");
        return `VİDEO: ${video.title}\nKANAL: ${video.channel}\nSÜRE: ${video.duration || ""}\nLİNK: ${link}\n\n${lines}`;
    }

    function renderCopyAllButton(results) {
        if (!results.length) return;
        const separator = `\n\n${"=".repeat(70)}\n\n`;
        const text = results.map((data, index) => {
            return `${index + 1}. VİDEO TRANSKRİPTİ\n${formatTranscriptForCopy(data.video, data.transcript || [])}`;
        }).join(separator);
        const bubble = addMessage("bot");
        bubble.innerHTML = `
            <div class="batch-copy-box">
                <strong>${results.length} videonun tam transkripti hazır.</strong>
                <button class="chip-btn primary batch-copy-btn"><i data-lucide="copy"></i> Tümünü Kopyala</button>
            </div>`;
        bubble.querySelector(".batch-copy-btn").addEventListener("click", () => {
            copyToClipboard(text, `${results.length} videonun transkripti panoya kopyalandı.`);
        });
        lucide.createIcons();
    }

    /* ---------- Detaylı özet: bot balonu olarak ---------- */
    async function showDetailedSummary(videoId) {
        const videoData = state.videos[videoId];
        const title = videoData ? videoData.video.title : "Video";

        // Önbellekte varsa direkt göster
        if (videoData && videoData._detailed) {
            renderDetailedBubble(title, videoId, videoData._detailed);
            return;
        }

        const typing = addTyping(`"${title}" için detaylı ders notu hazırlanıyor`);
        try {
            const res = await fetch("/api/detailed_summary", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ video_id: videoId })
            });
            const data = await res.json();
            typing.remove();
            if (data.success) {
                if (videoData) videoData._detailed = data.detailed_summary;
                renderDetailedBubble(title, videoId, data.detailed_summary);
            } else {
                addBotText(`⚠️ ${escapeHTML(data.error || "Detaylı özet üretilemedi.")}`);
            }
        } catch (err) {
            typing.remove();
            addBotText("⚠️ Detaylı özet sunucudan alınamadı.");
        }
    }

    function renderDetailedBubble(title, videoId, markdownText) {
        const bubble = addMessage("bot");
        bubble.innerHTML = `
            <p><strong>📖 Detaylı Ders Notu — ${escapeHTML(title)}</strong></p>
            <div class="detailed-content">${parseMarkdownToHTML(markdownText)}</div>
            <div class="detailed-actions">
                <button class="chip-btn copy-detailed-btn"><i data-lucide="copy"></i> Kopyala</button>
                <button class="chip-btn download-detailed-btn"><i data-lucide="download"></i> TXT İndir</button>
            </div>`;
        bubble.querySelector(".copy-detailed-btn").addEventListener("click", () => {
            copyToClipboard(markdownText, "Ders notu panoya kopyalandı.");
        });
        bubble.querySelector(".download-detailed-btn").addEventListener("click", () => {
            downloadAsTxt(`ders_notu_${videoId}.txt`, `DERS NOTU — ${title}\n\n${markdownText}`);
        });
        lucide.createIcons();
    }

});
