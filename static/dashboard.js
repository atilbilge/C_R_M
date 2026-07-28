/**
 * Stanomer Acente CRM - Frontend Dashboard Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentFilterCity = '';
    let currentFilterStatus = '';
    let currentFilterSource = '';
    let currentFilterHasPhone = '';
    let currentFilterHasEmail = '';
    let currentSearchQuery = '';
    let selectedAgencyId = null;

    // DOM References
    const navItems = document.querySelectorAll('.nav-menu .nav-item');
    const tabViews = document.querySelectorAll('.tab-view');

    const statTotal = document.getElementById('stat-total-agencies');
    const statResponded = document.getElementById('stat-responded');
    const statSent = document.getElementById('stat-sent');
    const statPhones = document.getElementById('stat-phones');
    const badgeAgenciesCount = document.getElementById('agencies-count-badge');

    const filterCitySelect = document.getElementById('filter-city');
    const statusPills = document.querySelectorAll('.status-pills .pill');
    const globalSearchInput = document.getElementById('global-search');

    const tbodyAgencies = document.getElementById('agencies-tbody');
    const loadingSpinner = document.getElementById('table-loading');

    const agencyModal = document.getElementById('agency-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    const addCommModal = document.getElementById('add-comm-modal');
    const btnQuickAdd = document.getElementById('btn-quick-add');
    const btnAddCommModal = document.getElementById('btn-add-comm-modal');
    const addCommCloseBtn = document.getElementById('add-comm-close-btn');
    const addCommCancelBtn = document.getElementById('add-comm-cancel');
    const addCommForm = document.getElementById('add-comm-form');
    const commAgencySelect = document.getElementById('comm-agency-select');

    const commsFeedList = document.getElementById('comms-feed-list');
    const filterCommChannel = document.getElementById('filter-comm-channel');
    const referralsTbody = document.getElementById('referrals-tbody');

    const dashboardRecentAgencies = document.getElementById('dashboard-recent-agencies');
    const dashboardCitiesList = document.getElementById('dashboard-cities-list');

    // 0. Tab Navigation Toggle Function
    window.switchToTab = function(targetId) {
        navItems.forEach(item => {
            if (item.getAttribute('data-target') === targetId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        tabViews.forEach(view => {
            if (view.id === targetId) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        if (targetId === 'view-comms') loadCommunicationsFeed();
        if (targetId === 'view-referrals') loadReferralsOverview();
        if (targetId === 'view-agencies') loadAgencies();
    };

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-target');
            if (targetId) switchToTab(targetId);
        });
    });

    // NVIDIA AI Translation Helper
    async function handleTranslateClick(btn, messageText, containerEl) {
        let transBox = containerEl.querySelector('.translation-box');
        if (transBox) {
            if (transBox.style.display === 'none') {
                transBox.style.display = 'block';
                btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Çeviriyi Gizle';
            } else {
                transBox.style.display = 'none';
                btn.innerHTML = '<i class="fa-solid fa-language" style="color: var(--accent-indigo);"></i> Türkçe\'ye Çevir';
            }
            return;
        }

        const originalBtnHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Çevriliyor...';

        try {
            const res = await fetch('/api/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: messageText })
            });
            const data = await res.json();

            if (data.translated_text) {
                transBox = document.createElement('div');
                transBox.className = 'translation-box';
                transBox.style.cssText = 'margin-top: 10px; background: rgba(42, 161, 152, 0.08); border-left: 4px solid var(--accent-indigo); padding: 0.75rem 1rem; border-radius: var(--radius-sm); font-size: 0.9rem; color: var(--text-primary);';

                const isHtml = data.translated_text.includes('<!DOCTYPE') || data.translated_text.includes('<html') || data.translated_text.includes('<table');
                const contentHtml = isHtml
                    ? `<iframe srcdoc="${data.translated_text.replace(/"/g, '&quot;')}" style="width: 100%; height: 340px; border: 1px solid var(--border-color); border-radius: 6px; background: #ffffff; margin-top: 6px;" frameborder="0"></iframe>`
                    : `<div style="line-height: 1.5; white-space: pre-wrap;">${data.translated_text}</div>`;

                transBox.innerHTML = `
                    <div style="font-weight: 600; font-size: 0.75rem; color: var(--accent-indigo); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;">
                        <i class="fa-solid fa-robot"></i> NVIDIA AI Türkçe Çevirisi (Llama 3.3 70B):
                    </div>
                    ${contentHtml}
                `;
                containerEl.appendChild(transBox);
                btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Çeviriyi Gizle';
            } else {
                alert(data.error || 'Çeviri yapılırken bir hata oluştu.');
                btn.innerHTML = originalBtnHtml;
            }
        } catch (err) {
            console.error('Çeviri hatası:', err);
            alert('Çeviri servisine ulaşılamadı.');
            btn.innerHTML = originalBtnHtml;
        } finally {
            btn.disabled = false;
        }
    }

    // 1. Fetch & Render Overall Stats & Dashboard Overview Widgets
    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();

            statTotal.textContent = data.total_agencies || 0;
            statPhones.textContent = data.total_phones || 0;
            
            const agenciesMenuCount = document.getElementById('agencies-menu-count');
            if (agenciesMenuCount) {
                agenciesMenuCount.textContent = `${data.total_agencies || 0} Acente`;
            }

            const respondedCount = data.status_distribution?.RESPONDED || 0;
            const sentCount = data.status_distribution?.SENT || 0;

            statResponded.textContent = respondedCount;
            statSent.textContent = sentCount;

            const lastSyncEl = document.getElementById('last-sync-time');
            if (lastSyncEl && data.last_email_sync) {
                const syncDt = new Date(data.last_email_sync);
                lastSyncEl.textContent = syncDt.toLocaleString('tr-TR', {
                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                });
            }

            // Populate City Select Options & City List Widget
            filterCitySelect.innerHTML = '<option value="">Tüm Şehirler</option>';
            if (data.top_cities) {
                dashboardCitiesList.innerHTML = '';
                Object.entries(data.top_cities).forEach(([city, count]) => {
                    if (city) {
                        const opt = document.createElement('option');
                        opt.value = city;
                        opt.textContent = `${city} (${count})`;
                        filterCitySelect.appendChild(opt);

                        const row = document.createElement('div');
                        row.style.cssText = 'display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.85rem; cursor: pointer;';
                        row.className = 'city-widget-row';
                        row.innerHTML = `<span><i class="fa-solid fa-location-dot" style="color: var(--accent-indigo); margin-right: 6px;"></i>${city}</span> <strong style="color: var(--accent-indigo);">${count} Acente</strong>`;
                        row.addEventListener('click', () => {
                            filterAndShowAgencies({ city: city });
                        });
                        dashboardCitiesList.appendChild(row);
                    }
                });
            }

            // Load Recent Interactions Widget (Sondan başa doğru sıralı son 6 etkileşim)
            const commsRes = await fetch('/api/communications');
            const comms = await commsRes.json();

            dashboardRecentAgencies.innerHTML = '';
            if (comms && comms.length > 0) {
                const recentComms = comms.slice(0, 6);
                recentComms.forEach(c => {
                    const div = document.createElement('div');
                    div.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color); cursor: pointer; transition: background 0.2s;';
                    div.className = 'recent-interaction-row';

                    const formattedDate = new Date(c.date).toLocaleString('tr-TR', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                    });

                    div.addEventListener('click', () => {
                        if (c.agency_id) openAgencyModal(c.agency_id);
                    });

                    div.innerHTML = `
                        <div>
                            <strong style="color: var(--text-primary); font-size: 0.92rem;">${c.agency_name}</strong>
                            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">
                                <span><i class="fa-regular fa-clock" style="color: var(--accent-indigo);"></i> ${formattedDate}</span>
                                <span style="margin-left: 8px;">&bull; ${c.sender} &rarr; ${c.recipient}</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span class="status-tag tag-${c.status.toLowerCase()}">${c.status}</span>
                            <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); openAgencyModal(${c.agency_id});">
                                <i class="fa-solid fa-clock-rotate-left"></i> Zaman Çizelgesi
                            </button>
                        </div>
                    `;
                    dashboardRecentAgencies.appendChild(div);
                });
            } else {
                dashboardRecentAgencies.innerHTML = '<p style="color: var(--text-muted);">Henüz kaydedilmiş etkileşim bulunmuyor.</p>';
            }

        } catch (err) {
            console.error('Stats yükleme hatası:', err);
        }
    }

    // 2. Fetch & Render Agencies Table
    async function loadAgencies() {
        loadingSpinner.style.display = 'block';
        tbodyAgencies.innerHTML = '';

        try {
            const params = new URLSearchParams();
            if (currentFilterCity) params.append('city', currentFilterCity);
            if (currentFilterStatus) params.append('status', currentFilterStatus);
            if (currentFilterSource) params.append('source', currentFilterSource);
            if (currentFilterHasPhone) params.append('has_phone', currentFilterHasPhone);
            if (currentFilterHasEmail) params.append('has_email', currentFilterHasEmail);
            if (currentSearchQuery) params.append('q', currentSearchQuery);

            const res = await fetch(`/api/agencies?${params.toString()}`);
            const agencies = await res.json();

            loadingSpinner.style.display = 'none';

            const menuCount = document.getElementById('agencies-menu-count');
            if (menuCount) {
                const count = agencies ? agencies.length : 0;
                menuCount.textContent = `${count} Acente`;
            }

            if (!agencies || agencies.length === 0) {
                tbodyAgencies.innerHTML = `
                    <tr>
                        <td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-muted);">
                            <i class="fa-solid fa-folder-open"></i> Arama kriterlerine uygun acente bulunamadı.
                        </td>
                    </tr>
                `;
                return;
            }

            agencies.forEach(agency => {
                const tr = document.createElement('tr');
                
                let statusClass = 'tag-new';
                if (agency.status === 'SENT') statusClass = 'tag-sent';
                if (agency.status === 'RESPONDED') statusClass = 'tag-responded';
                if (agency.status === 'CONTACTED') statusClass = 'tag-contacted';
                if (agency.status === 'FAILED') statusClass = 'tag-failed';

                let sourceBadges = '';
                if (agency.sources && agency.sources.includes('companywall')) {
                    sourceBadges += `<span class="badge-source source-companywall"><i class="fa-solid fa-building-circle-check"></i> CompanyWall</span>`;
                }
                if (agency.sources && agency.sources.includes('indomio')) {
                    sourceBadges += `<span class="badge-source source-indomio"><i class="fa-solid fa-gem"></i> Indomio</span>`;
                }
                if (agency.sources && agency.sources.includes('nekretnine')) {
                    sourceBadges += `<span class="badge-source source-nekretnine"><i class="fa-solid fa-house"></i> Nekretnine</span>`;
                }

                const pibMbInfo = (agency.pib || agency.mb) 
                    ? `<div style="font-size: 0.72rem; color: var(--text-muted); font-weight: normal; margin-top: 2px;">
                         ${agency.pib ? 'PIB: ' + agency.pib : ''} ${agency.mb ? ' | MB: ' + agency.mb : ''}
                       </div>` 
                    : '';

                const phonesStr = agency.phones && agency.phones.length > 0 
                    ? agency.phones.join(', ') 
                    : '<span style="color: var(--text-muted);">-</span>';

                const emailsStr = agency.emails && agency.emails.length > 0 
                    ? agency.emails.join(', ') 
                    : '<span style="color: var(--text-muted);">-</span>';

                tr.innerHTML = `
                    <td><strong>#${agency.id}</strong></td>
                    <td class="agency-name-cell">
                        <div>
                            <div>${sourceBadges}<strong>${agency.name}</strong></div>
                            ${pibMbInfo}
                        </div>
                    </td>
                    <td>${agency.city || '-'}</td>
                    <td><span class="status-tag ${statusClass}">${agency.status}</span></td>
                    <td>${phonesStr}</td>
                    <td>${emailsStr}</td>
                    <td><span class="code-tag">${agency.ref_code}</span></td>
                    <td>
                        <button class="btn btn-sm btn-secondary btn-view-detail" data-id="${agency.id}">
                            <i class="fa-solid fa-clock-rotate-left"></i> Detay
                        </button>
                    </td>
                `;

                tbodyAgencies.appendChild(tr);
            });

            document.querySelectorAll('.btn-view-detail').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const id = e.currentTarget.getAttribute('data-id');
                    window.openAgencyModal(id);
                });
            });

        } catch (err) {
            loadingSpinner.style.display = 'none';
            console.error('Acente listesi yüklenirken hata:', err);
        }
    }

    // 3. Open Agency Detail Modal with Timeline
    window.openAgencyModal = async function(agencyId) {
        selectedAgencyId = agencyId;
        agencyModal.classList.add('active');

        const modalTitle = document.getElementById('modal-agency-name');
        const modalStatus = document.getElementById('modal-agency-status');
        const modalAddress = document.getElementById('modal-agency-address');
        const modalPhones = document.getElementById('modal-agency-phones');
        const modalEmails = document.getElementById('modal-agency-emails');
        const modalWebsites = document.getElementById('modal-agency-websites');
        const modalRefCode = document.getElementById('modal-agency-refcode');
        const modalTimeline = document.getElementById('modal-timeline');

        modalTimeline.innerHTML = '<p style="color: var(--text-muted); text-align: center;">Yükleniyor...</p>';

        try {
            const res = await fetch(`/api/agencies/${agencyId}`);
            const agency = await res.json();

            modalTitle.textContent = agency.name;
            modalStatus.textContent = agency.status;
            modalStatus.className = `status-tag tag-${agency.status.toLowerCase()}`;
            modalAddress.textContent = `${agency.city ? agency.city + ' / ' : ''}${agency.address || 'Adres bilgisi yok'}`;
            
            modalPhones.textContent = agency.phones && agency.phones.length > 0 ? agency.phones.join(', ') : 'Belirtilmedi';
            if (agency.emails && agency.emails.length > 0) {
                modalEmails.innerHTML = agency.emails.map(e => {
                    const addr = typeof e === 'object' ? e.email : e;
                    const isInactive = typeof e === 'object' && e.status === 'INACTIVE';
                    return isInactive 
                        ? `<span class="email-inactive" title="E-posta teslim edilemedi / Pasif"><i class="fa-solid fa-triangle-exclamation"></i> ${addr} (Geri Döndü)</span>`
                        : addr;
                }).join('<br>');
            } else {
                modalEmails.textContent = 'Belirtilmedi';
            }
            
            if (agency.websites && agency.websites.length > 0) {
                modalWebsites.innerHTML = agency.websites.map(w => `<a href="${w.url}" target="_blank" style="color: var(--accent-indigo);">${w.url}</a>`).join('<br>');
            } else {
                modalWebsites.textContent = 'Belirtilmedi';
            }

            modalRefCode.textContent = agency.ref_code;

            modalTimeline.innerHTML = '';
            if (!agency.communications || agency.communications.length === 0) {
                modalTimeline.innerHTML = '<p style="color: var(--text-muted); padding: 1rem 0;">Henüz kaydedilmiş iletişim yok.</p>';
            } else {
                agency.communications.forEach(comm => {
                    const item = document.createElement('div');
                    const isReceived = comm.status === 'RECEIVED' || comm.status === 'RESPONDED';
                    const isFailed = comm.status === 'FAILED';
                    
                    item.className = `timeline-item ${isReceived ? 'received' : ''} ${isFailed ? 'failed' : ''}`;

                    const formattedDate = new Date(comm.date).toLocaleString('tr-TR', {
                        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                    });

                    const statusBadge = isFailed 
                        ? `<span class="status-tag tag-failed" style="margin-left: 6px;"><i class="fa-solid fa-circle-exclamation"></i> TESLİMAT HATASI</span>`
                        : '';

                    const messageContent = (comm.message.includes('<!DOCTYPE') || comm.message.includes('<html') || comm.message.includes('<table'))
                        ? `<iframe srcdoc="${comm.message.replace(/"/g, '&quot;')}" style="width: 100%; height: 420px; border: 1px solid var(--border-color); border-radius: 12px; background: #ffffff; margin-top: 8px;" frameborder="0"></iframe>`
                        : `<div style="white-space: pre-wrap;">${comm.message}</div>`;

                    item.innerHTML = `
                        <div class="timeline-meta" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <span><i class="fa-solid fa-paper-plane"></i> ${comm.sender} &rarr; ${comm.recipient} ${statusBadge}</span>
                                <span style="margin-left: 10px;"><i class="fa-regular fa-clock"></i> ${formattedDate} (${comm.channel})</span>
                            </div>
                            <button class="btn btn-sm btn-secondary btn-translate-msg" title="NVIDIA AI ile Türkçe'ye Çevir">
                                <i class="fa-solid fa-language" style="color: var(--accent-indigo);"></i> Türkçe'ye Çevir
                            </button>
                        </div>
                        <div class="timeline-body">${messageContent}</div>
                    `;

                    const transBtn = item.querySelector('.btn-translate-msg');
                    const bodyEl = item.querySelector('.timeline-body');
                    if (transBtn) {
                        transBtn.addEventListener('click', () => {
                            handleTranslateClick(transBtn, comm.message, bodyEl);
                        });
                    }

                    modalTimeline.appendChild(item);
                });
            }

        } catch (err) {
            console.error('Modal acente detay yükleme hatası:', err);
        }
    };

    modalCloseBtn.addEventListener('click', () => agencyModal.classList.remove('active'));

    document.getElementById('btn-copy-ref').addEventListener('click', () => {
        const code = document.getElementById('modal-agency-refcode').textContent;
        navigator.clipboard.writeText(code);
        alert(`Referans Kodu Kopyalandı: ${code}`);
    });

    // 4. İletişim Akışı (Feed View)
    const filterCommPeriodSelect = document.getElementById('filter-comm-period');
    const customDateContainer = document.getElementById('custom-date-container');
    const filterCommStartDate = document.getElementById('filter-comm-start-date');
    const filterCommEndDate = document.getElementById('filter-comm-end-date');

    if (filterCommPeriodSelect) {
        filterCommPeriodSelect.addEventListener('change', () => {
            if (filterCommPeriodSelect.value === 'custom') {
                customDateContainer.style.display = 'flex';
            } else {
                customDateContainer.style.display = 'none';
            }
            loadCommunicationsFeed();
        });
    }

    if (filterCommStartDate) filterCommStartDate.addEventListener('change', loadCommunicationsFeed);
    if (filterCommEndDate) filterCommEndDate.addEventListener('change', loadCommunicationsFeed);

    async function loadCommunicationsFeed() {
        commsFeedList.innerHTML = '<p style="color: var(--text-muted); text-align: center;">Akış yükleniyor...</p>';
        const channel = filterCommChannel ? filterCommChannel.value : '';
        const period = filterCommPeriodSelect ? filterCommPeriodSelect.value : '';
        const startDate = filterCommStartDate ? filterCommStartDate.value : '';
        const endDate = filterCommEndDate ? filterCommEndDate.value : '';

        try {
            const params = new URLSearchParams();
            if (channel) params.append('channel', channel);
            if (period) params.append('period', period);
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

            const res = await fetch(`/api/communications?${params.toString()}`);
            const comms = await res.json();

            commsFeedList.innerHTML = '';
            if (!comms || comms.length === 0) {
                commsFeedList.innerHTML = '<p style="color: var(--text-muted); padding: 2rem; text-align: center;">Seçilen kriterlere uygun iletişim kaydı bulunamadı.</p>';
                return;
            }

            comms.forEach(comm => {
                const card = document.createElement('div');
                card.className = 'comm-feed-card collapsed';
                card.style.cssText = 'background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem; transition: all 0.25s ease;';

                const formattedDate = new Date(comm.date).toLocaleString('tr-TR', {
                    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                });

                const isHtmlEmail = comm.message.includes('<!DOCTYPE') || comm.message.includes('<html') || comm.message.includes('<table');
                const fullMessageHtml = isHtmlEmail
                    ? `<iframe srcdoc="${comm.message.replace(/"/g, '&quot;')}" style="width: 100%; height: 380px; border: 1px solid var(--border-color); border-radius: 8px; background: #ffffff; margin-top: 8px;" frameborder="0"></iframe>`
                    : `<div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5; white-space: pre-wrap; background: var(--bg-primary); border: 1px solid var(--border-color); padding: 0.75rem; border-radius: var(--radius-sm); margin-top: 8px;">${comm.message}</div>`;

                let snippet = comm.message.replace(/<[^>]*>?/gm, '').replace(/\s+/g, ' ').trim();
                if (snippet.length > 140) snippet = snippet.substring(0, 140) + '...';

                card.innerHTML = `
                    <div class="comm-card-header" style="display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <div>
                            <strong style="color: var(--text-primary); font-size: 1rem;">${comm.agency_name}</strong>
                            <span style="font-size: 0.8rem; color: var(--text-muted); margin-left: 0.5rem;">(${comm.agency_city || 'Şehir Yok'})</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span class="status-tag tag-${comm.status.toLowerCase()}">${comm.status}</span>
                            <button class="btn btn-sm btn-secondary btn-translate-msg" title="NVIDIA AI ile Türkçe'ye Çevir">
                                <i class="fa-solid fa-language" style="color: var(--accent-indigo);"></i> Türkçe'ye Çevir
                            </button>
                            <button class="btn btn-sm btn-secondary btn-toggle-expand" title="Detayı Aç/Kapat">
                                <i class="fa-solid fa-chevron-down icon-arrow"></i> <span class="expand-text">Detayı Göster</span>
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); openAgencyModal(${comm.agency_id});" title="Acente Zaman Çizelgesi">
                                <i class="fa-solid fa-clock-rotate-left"></i> Zaman Çizelgesi
                            </button>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.4rem; margin-bottom: 0.5rem;">
                        <span><i class="fa-solid fa-user"></i> ${comm.sender} &rarr; ${comm.recipient}</span>
                        <span style="margin-left: 1rem;"><i class="fa-regular fa-clock"></i> ${formattedDate} (${comm.channel})</span>
                    </div>
                    <div class="comm-card-snippet" style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.4; font-style: italic; background: rgba(42,161,152,0.06); padding: 0.5rem 0.75rem; border-radius: 6px; border-left: 3px solid var(--accent-indigo); cursor: pointer;">
                        ${snippet || 'Mesaj içeriği'}
                    </div>
                    <div class="comm-card-body" style="display: none; margin-top: 0.75rem;">
                        ${fullMessageHtml}
                    </div>
                `;

                const toggleBtn = card.querySelector('.btn-toggle-expand');
                const headerEl = card.querySelector('.comm-card-header');
                const snippetEl = card.querySelector('.comm-card-snippet');
                const bodyEl = card.querySelector('.comm-card-body');
                const arrowIcon = card.querySelector('.icon-arrow');
                const expandText = card.querySelector('.expand-text');

                const toggleCard = (e) => {
                    if (e) e.stopPropagation();
                    const isCollapsed = card.classList.contains('collapsed');
                    if (isCollapsed) {
                        card.classList.remove('collapsed');
                        card.classList.add('expanded');
                        bodyEl.style.display = 'block';
                        snippetEl.style.display = 'none';
                        arrowIcon.className = 'fa-solid fa-chevron-up icon-arrow';
                        expandText.textContent = 'Daralt';
                    } else {
                        card.classList.add('collapsed');
                        card.classList.remove('expanded');
                        bodyEl.style.display = 'none';
                        snippetEl.style.display = 'block';
                        arrowIcon.className = 'fa-solid fa-chevron-down icon-arrow';
                        expandText.textContent = 'Detayı Göster';
                    }
                };

                headerEl.addEventListener('click', toggleCard);
                snippetEl.addEventListener('click', toggleCard);
                toggleBtn.addEventListener('click', toggleCard);

                const transBtn = card.querySelector('.btn-translate-msg');
                if (transBtn) {
                    transBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (card.classList.contains('collapsed')) {
                            toggleCard(e);
                        }
                        handleTranslateClick(transBtn, comm.message, bodyEl);
                    });
                }

                commsFeedList.appendChild(card);
            });

        } catch (err) {
            console.error('İletişim akışı yükleme hatası:', err);
        }
    }

    if (filterCommChannel) {
        filterCommChannel.addEventListener('change', loadCommunicationsFeed);
    }

    // 5. Referans Sistemi Overview
    async function loadReferralsOverview() {
        referralsTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem;">Yükleniyor...</td></tr>';
        try {
            const res = await fetch('/api/referrals');
            const data = await res.json();

            referralsTbody.innerHTML = '';
            data.forEach(item => {
                const tr = document.createElement('tr');
                const refLink = `https://stanomer.com/ref/${item.ref_code}`;
                tr.innerHTML = `
                    <td><strong>#${item.id}</strong></td>
                    <td><strong>${item.name}</strong></td>
                    <td>${item.city || '-'}</td>
                    <td><span class="code-tag">${item.ref_code}</span></td>
                    <td><a href="${refLink}" target="_blank" style="color: var(--accent-indigo); font-size: 0.85rem;">${refLink}</a></td>
                    <td><span class="badge" style="background: var(--accent-emerald);">${item.referral_count} Davet</span></td>
                    <td>
                        <button class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText('${refLink}'); alert('Referans Linki Kopyalandı!');">
                            <i class="fa-regular fa-copy"></i> Linki Kopyala
                        </button>
                    </td>
                `;
                referralsTbody.appendChild(tr);
            });
        } catch (err) {
            console.error('Referans yükleme hatası:', err);
        }
    }

    // Filter & Search Listeners
    filterCitySelect.addEventListener('change', (e) => {
        currentFilterCity = e.target.value;
        loadAgencies();
    });

    const filterSourceSelect = document.getElementById('filter-source');
    if (filterSourceSelect) {
        filterSourceSelect.addEventListener('change', (e) => {
            currentFilterSource = e.target.value;
            loadAgencies();
        });
    }

    statusPills.forEach(pill => {
        pill.addEventListener('click', (e) => {
            statusPills.forEach(p => p.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentFilterStatus = e.currentTarget.getAttribute('data-status');
            loadAgencies();
        });
    });

    const filterHasPhoneSelect = document.getElementById('filter-has-phone');
    if (filterHasPhoneSelect) {
        filterHasPhoneSelect.addEventListener('change', (e) => {
            currentFilterHasPhone = e.target.value;
            loadAgencies();
        });
    }

    const filterHasEmailSelect = document.getElementById('filter-has-email');
    if (filterHasEmailSelect) {
        filterHasEmailSelect.addEventListener('change', (e) => {
            currentFilterHasEmail = e.target.value;
            loadAgencies();
        });
    }

    // Helper to filter agencies and navigate to Agencies tab
    window.filterAndShowAgencies = function({ status = '', city = '', hasPhone = '', hasEmail = '', search = '' } = {}) {
        currentFilterStatus = status;
        currentFilterCity = city;
        currentFilterHasPhone = hasPhone;
        currentFilterHasEmail = hasEmail;
        currentSearchQuery = search;

        if (filterCitySelect) filterCitySelect.value = city;
        if (filterHasPhoneSelect) filterHasPhoneSelect.value = hasPhone;
        if (filterHasEmailSelect) filterHasEmailSelect.value = hasEmail;
        if (globalSearchInput) globalSearchInput.value = search;

        statusPills.forEach(p => {
            if (p.getAttribute('data-status') === status) {
                p.classList.add('active');
            } else {
                p.classList.remove('active');
            }
        });

        switchToTab('view-agencies');
    };

    // Dashboard Stat Cards Click Handlers
    const cardTotalAgencies = document.getElementById('card-total-agencies');
    if (cardTotalAgencies) {
        cardTotalAgencies.addEventListener('click', () => {
            filterAndShowAgencies({ status: '', city: '', hasPhone: '', hasEmail: '', search: '' });
        });
    }

    const cardResponded = document.getElementById('card-responded');
    if (cardResponded) {
        cardResponded.addEventListener('click', () => {
            filterAndShowAgencies({ status: 'RESPONDED' });
        });
    }

    const cardSent = document.getElementById('card-sent');
    if (cardSent) {
        cardSent.addEventListener('click', () => {
            filterAndShowAgencies({ status: 'SENT' });
        });
    }

    const cardPhones = document.getElementById('card-phones');
    if (cardPhones) {
        cardPhones.addEventListener('click', () => {
            filterAndShowAgencies({ hasPhone: 'yes' });
        });
    }

    // Quick Add Modal Form Listener
    async function populateAgencyDropdown() {
        try {
            const res = await fetch('/api/agencies');
            const agencies = await res.json();
            commAgencySelect.innerHTML = '<option value="">Acente Seçiniz...</option>';
            agencies.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.id;
                opt.textContent = `${a.name} (${a.city || 'Şehir Yok'})`;
                commAgencySelect.appendChild(opt);
            });
        } catch (err) {
            console.error('Dropdown doldurma hatası:', err);
        }
    }

    btnQuickAdd.addEventListener('click', () => {
        populateAgencyDropdown();
        addCommModal.classList.add('active');
    });

    btnAddCommModal.addEventListener('click', () => {
        populateAgencyDropdown();
        if (selectedAgencyId) {
            commAgencySelect.value = selectedAgencyId;
        }
        addCommModal.classList.add('active');
    });

    addCommCloseBtn.addEventListener('click', () => addCommModal.classList.remove('active'));
    addCommCancelBtn.addEventListener('click', () => addCommModal.classList.remove('active'));

    addCommForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const agencyId = commAgencySelect.value;
        const channel = document.getElementById('comm-channel').value;
        const status = document.getElementById('comm-status').value;
        const sender = document.getElementById('comm-sender').value;
        const message = document.getElementById('comm-message').value;

        if (!agencyId || !message) return;

        try {
            const res = await fetch(`/api/agencies/${agencyId}/communications`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender, message, channel, status })
            });

            if (res.ok) {
                addCommModal.classList.remove('active');
                addCommForm.reset();
                loadStats();
                loadAgencies();
                if (agencyModal.classList.contains('active')) {
                    openAgencyModal(agencyId);
                }
            } else {
                alert('İletişim kaydı eklenirken hata oluştu.');
            }
        } catch (err) {
            console.error('İletişim ekleme hatası:', err);
        }
    });

    // Sync Status Badge Click Handler
    const syncBadge = document.getElementById('sync-status-badge');
    const syncIcon = document.getElementById('sync-icon');

    if (syncBadge) {
        syncBadge.addEventListener('click', async () => {
            if (syncIcon) syncIcon.classList.add('fa-spin');
            try {
                const res = await fetch('/api/sync-emails', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    await loadStats();
                    const activeTab = document.querySelector('.tab-view.active')?.id;
                    if (activeTab === 'view-agencies') loadAgencies();
                    if (activeTab === 'view-comms') loadCommunicationsFeed();
                }
            } catch (err) {
                console.error('E-posta senkronizasyon hatası:', err);
            } finally {
                if (syncIcon) syncIcon.classList.remove('fa-spin');
            }
        });
    }

    // Global Expand All / Collapse All Handlers
    const btnExpandAll = document.getElementById('btn-expand-all');
    const btnCollapseAll = document.getElementById('btn-collapse-all');

    if (btnExpandAll) {
        btnExpandAll.addEventListener('click', () => {
            document.querySelectorAll('.comm-feed-card.collapsed').forEach(card => {
                const toggleBtn = card.querySelector('.btn-toggle-expand');
                if (toggleBtn) toggleBtn.click();
            });
        });
    }

    if (btnCollapseAll) {
        btnCollapseAll.addEventListener('click', () => {
            document.querySelectorAll('.comm-feed-card.expanded').forEach(card => {
                const toggleBtn = card.querySelector('.btn-toggle-expand');
                if (toggleBtn) toggleBtn.click();
            });
        });
    }

    // Logout Button Click Handler
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            if (confirm('Oturumu kapatmak istediğinize emin misiniz?')) {
                try {
                    const res = await fetch('/api/logout', { method: 'POST' });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    }
                } catch (err) {
                    console.error('Çıkış yapma hatası:', err);
                }
            }
        });
    }

    // Initial Load
    loadStats();
    loadAgencies();
});
