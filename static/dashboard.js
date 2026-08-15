/**
 * Stanomer Acente CRM - Frontend Dashboard Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentFilterCity = '';
    let currentFilterStatus = '';
    let currentFilterSource = '';
    let currentFilterSegment = '';
    let currentFilterHasPhone = '';
    let currentFilterHasEmail = '';
    let currentFilterActivityCode = '';
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
        if (targetId === 'view-campaigns') loadCampaigns();
        if (targetId === 'view-unsubscribes') loadUnsubscribes();
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

            const unsubCountEl = document.getElementById('unsubscribes-menu-count');
            if (unsubCountEl) {
                unsubCountEl.textContent = `${data.total_unsubscribes || 0} Adres`;
            }

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
            if (currentFilterSegment) params.append('segment', currentFilterSegment);
            if (currentFilterHasPhone) params.append('has_phone', currentFilterHasPhone);
            if (currentFilterHasEmail) params.append('has_email', currentFilterHasEmail);
            if (currentFilterActivityCode) params.append('activity_code', currentFilterActivityCode);
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
                if (agency.status === 'TEST') statusClass = 'tag-test';

                let sourceBadges = '';
                const sourcesList = agency.sources || [agency.source];
                const srcStr = (Array.isArray(sourcesList) ? sourcesList.join(' ') : String(sourcesList || '')).toLowerCase();

                if (srcStr.includes('companywall')) {
                    sourceBadges += `<span class="badge-source source-companywall"><i class="fa-solid fa-building"></i> CompanyWall</span>`;
                }
                if (srcStr.includes('indomio')) {
                    sourceBadges += `<span class="badge-source source-indomio"><i class="fa-solid fa-gem"></i> Indomio</span>`;
                }
                if (srcStr.includes('nekretnine')) {
                    sourceBadges += `<span class="badge-source source-nekretnine"><i class="fa-solid fa-house"></i> Nekretnine</span>`;
                }

                if (!sourceBadges) {
                    const rawSrc = agency.source || '-';
                    sourceBadges = `<span class="badge-source source-default">${escapeHtml(rawSrc)}</span>`;
                }

                const pibMbInfo = (agency.pib || agency.mb) 
                    ? `<div style="font-size: 0.72rem; color: var(--text-muted); font-weight: normal; margin-top: 2px;">
                         ${agency.pib ? 'PIB: ' + agency.pib : ''} ${agency.mb ? ' | MB: ' + agency.mb : ''}
                       </div>` 
                    : '';

                let segBadge = '';
                const seg = agency.segment || '';
                if (seg.startsWith('A-')) segBadge = `<span class="status-tag" style="background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); font-weight: 600;">${escapeHtml(seg)}</span>`;
                else if (seg.startsWith('B-')) segBadge = `<span class="status-tag" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600;">${escapeHtml(seg)}</span>`;
                else if (seg.startsWith('C-')) segBadge = `<span class="status-tag" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-weight: 600;">${escapeHtml(seg)}</span>`;
                else if (seg.startsWith('D-')) segBadge = `<span class="status-tag" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3);">${escapeHtml(seg)}</span>`;
                else if (seg.startsWith('E-')) segBadge = `<span class="status-tag" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);">${escapeHtml(seg)}</span>`;
                else segBadge = `<span style="color: var(--text-muted); font-size: 0.8rem;">-</span>`;

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
                            <strong>${escapeHtml(agency.name)}</strong>
                            ${pibMbInfo}
                        </div>
                    </td>
                    <td>${segBadge}</td>
                    <td>${escapeHtml(agency.city || '-')}</td>
                    <td><span class="status-tag ${statusClass}">${agency.status}</span></td>
                    <td class="agency-phone-cell">${phonesStr}</td>
                    <td class="agency-email-cell">${emailsStr}</td>
                    <td>${sourceBadges}</td>
                    <td>
                        <button class="btn btn-sm btn-secondary btn-view-detail" data-id="${agency.id}" title="Acente Detayı" style="padding: 0.4rem 0.65rem;">
                            <i class="fa-solid fa-eye"></i>
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
        const modalLongName = document.getElementById('modal-agency-longname');
        const modalEstSize = document.getElementById('modal-agency-est-size');
        const modalFinancials = document.getElementById('modal-agency-financials');
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
            
            if (modalLongName) modalLongName.textContent = agency.long_name || agency.name;
            if (modalEstSize) {
                let estText = agency.establishment_date ? agency.establishment_date : 'Belirtilmedi';
                if (agency.enterprise_size) estText += ` (${agency.enterprise_size})`;
                if (agency.activity_code) estText += ` • Kod: ${agency.activity_code}`;
                modalEstSize.textContent = estText;
            }

            let empObj = {}, incObj = {};
            try { empObj = JSON.parse(agency.employees_json || '{}'); } catch(e) {}
            try { incObj = JSON.parse(agency.income_json || '{}'); } catch(e) {}

            let finHtml = '';
            const years = Array.from(new Set([...Object.keys(empObj), ...Object.keys(incObj)])).sort();
            if (years.length > 0) {
                finHtml = `<table class="data-table" style="width: 100%; border-collapse: collapse; font-size: 0.83rem; background: var(--bg-secondary); border-radius: var(--radius-sm); overflow: hidden; margin-top: 6px; border: 1px solid var(--border-color);">
                    <thead>
                        <tr style="background: var(--bg-primary); color: var(--text-muted); font-size: 0.78rem;">
                            <th style="padding: 6px 12px; text-align: left; font-weight: 600;">Metrik</th>
                            ${years.map(y => `<th style="padding: 6px 12px; text-align: right; font-weight: 600;">${y}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-top: 1px solid var(--border-color);">
                            <td style="padding: 7px 12px; font-weight: 600; color: var(--text-primary);">👥 Çalışan Sayısı</td>
                            ${years.map(y => `<td style="padding: 7px 12px; text-align: right; color: #10b981; font-weight: 700; font-family: monospace;">${empObj[y] || '-'}</td>`).join('')}
                        </tr>
                        <tr style="border-top: 1px solid var(--border-color);">
                            <td style="padding: 7px 12px; font-weight: 600; color: var(--text-primary);">💰 Toplam Gelir (RSD)</td>
                            ${years.map(y => `<td style="padding: 7px 12px; text-align: right; color: var(--accent-indigo); font-weight: 700; font-family: monospace;">${incObj[y] || '-'}</td>`).join('')}
                        </tr>
                    </tbody>
                </table>`;
            } else {
                finHtml = '<span style="color: var(--text-muted); font-style: italic;">Henüz 3 yıllık finansal tablo verisi işlenmedi.</span>';
            }
            if (modalFinancials) modalFinancials.innerHTML = finHtml;

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
                modalWebsites.innerHTML = agency.websites.map(w => {
                    const u = typeof w === 'object' && w.url ? w.url : w;
                    return `<a href="${u}" target="_blank" style="color: var(--accent-indigo); word-break: break-all;">${u}</a>`;
                }).join('<br>');
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

    const filterSegmentSelect = document.getElementById('filter-segment');
    if (filterSegmentSelect) {
        filterSegmentSelect.addEventListener('change', (e) => {
            currentFilterSegment = e.target.value;
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

    // Faaliyet Kodu filtresini yükle ve event listener ekle
    const filterActivityCodeSelect = document.getElementById('filter-activity-code');
    async function populateActivityCodeDropdowns() {
        try {
            const res = await fetch('/api/agencies/activity-codes');
            const codes = await res.json();
            const options = codes.map(c => `<option value="${c}">${c}</option>`).join('');
            if (filterActivityCodeSelect) {
                filterActivityCodeSelect.innerHTML = '<option value="">Tüm Kodlar</option>' + options;
            }
            const campSelect = document.getElementById('camp-filter-activity-code');
            if (campSelect) {
                campSelect.innerHTML = '<option value="">Tüm Kodlar</option>' + options;
            }
        } catch (err) {
            console.warn('Faaliyet kodları yüklenemedi:', err);
        }
    }
    populateActivityCodeDropdowns();

    if (filterActivityCodeSelect) {
        filterActivityCodeSelect.addEventListener('change', (e) => {
            currentFilterActivityCode = e.target.value;
            loadAgencies();
        });
    }

    if (globalSearchInput) {
        let searchDebounceTimer;
        const triggerSearch = (val) => {
            currentSearchQuery = val.trim();
            const activeTab = document.querySelector('.tab-view.active')?.id;
            if (activeTab !== 'view-agencies') {
                switchToTab('view-agencies');
            } else {
                loadAgencies();
            }
        };

        globalSearchInput.addEventListener('input', (e) => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => triggerSearch(e.target.value), 300);
        });

        globalSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchDebounceTimer);
                triggerSearch(e.target.value);
            }
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

    // ─── E-POSTA KAMPANYA MÖDÜLÜ SCRIPT'LERİ ──────────────────────────────────
    let sendProgressTimer = null;

    async function loadCampaigns() {
        const tbody = document.getElementById('campaigns-table-body');
        if (!tbody) return;

        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
                    <i class="fa-solid fa-spinner fa-spin"></i> Kampanyalar yükleniyor...
                </td>
            </tr>
        `;

        try {
            const res = await fetch('/api/campaigns');
            const data = await res.json();

            if (!Array.isArray(data) || data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
                            <i class="fa-solid fa-folder-open" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                            Henüz oluşturulmuş bir e-posta kampanyası yok. "Yeni Kampanya Oluştur" butonunu kullanarak hemen tanımlayabilirsiniz.
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = '';
            data.forEach(camp => {
                const tr = document.createElement('tr');

                let statusBadge = '<span class="status-badge" style="background: rgba(156, 163, 175, 0.15); color: #6b7280;">Taslak (DRAFT)</span>';
                if (camp.status === 'RUNNING') {
                    statusBadge = '<span class="status-badge" style="background: rgba(59, 130, 246, 0.15); color: #3b82f6;"><i class="fa-solid fa-spinner fa-spin"></i> Gönderiliyor</span>';
                } else if (camp.status === 'COMPLETED') {
                    statusBadge = `<span class="status-badge status-sent"><i class="fa-solid fa-check"></i> Tamamlandı (${camp.sent_count || 0} Gönderildi)</span>`;
                } else if (camp.status === 'FAILED') {
                    statusBadge = '<span class="status-badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444;">Hata Oluştu</span>';
                }

                const dateStr = camp.created_at ? new Date(camp.created_at).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';
                const langBadge = `<code style="background: rgba(99, 102, 241, 0.1); color: var(--accent-indigo); padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 0.78rem;">${escapeHtml(camp.lang || 'SR_LAT')}</code>`;

                tr.innerHTML = `
                    <td>
                        <strong style="color: var(--text-primary); font-size: 0.95rem;">${escapeHtml(camp.name)}</strong>
                    </td>
                    <td>${langBadge}</td>
                    <td>
                        <span style="color: var(--text-secondary); font-size: 0.88rem;">${escapeHtml(camp.subject)}</span>
                    </td>
                    <td>
                        <span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(camp.sender_name)} &lt;${escapeHtml(camp.sender_email)}&gt;</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td style="font-size: 0.82rem; color: var(--text-muted);">${dateStr}</td>
                    <td style="text-align: right;">
                        <div style="display: flex; gap: 0.4rem; justify-content: flex-end;">
                            <button class="btn btn-sm btn-secondary btn-preview-camp" data-id="${camp.id}" title="Şablon Önizle" style="padding: 0.4rem 0.65rem;">
                                <i class="fa-solid fa-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary btn-logs-camp" data-id="${camp.id}" title="Gönderim Geçmişi & Mail Zinciri" style="padding: 0.4rem 0.65rem; color: #10b981;">
                                <i class="fa-solid fa-list-check"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary btn-copy-camp" data-id="${camp.id}" title="Kampanyayı Kopyala" style="padding: 0.4rem 0.65rem; color: var(--accent-indigo);">
                                <i class="fa-solid fa-copy"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary btn-edit-camp" data-id="${camp.id}" title="Kampanyayı Düzenle" style="padding: 0.4rem 0.65rem;">
                                <i class="fa-solid fa-pen-to-square"></i>
                            </button>
                            <button class="btn btn-sm btn-primary btn-send-camp" data-id="${camp.id}" title="Gönderim Paneli" style="background: var(--accent-indigo); padding: 0.4rem 0.65rem;">
                                <i class="fa-solid fa-paper-plane"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary btn-delete-camp" data-id="${camp.id}" title="Kampanyayı Sil" style="color: #ef4444; padding: 0.4rem 0.65rem;">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                    </td>
                `;

                tbody.appendChild(tr);
            });

            tbody.querySelectorAll('.btn-preview-camp').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const campId = btn.getAttribute('data-id');
                    try {
                        const res = await fetch(`/api/campaigns/${campId}`);
                        const camp = await res.json();
                        if (camp && !camp.error) {
                            openEmailPreviewModal(camp.subject, camp.body_html, 0, camp.lang || 'SR_LAT');
                        }
                    } catch (e) {
                        alert('Kampanya detayları alınamadı: ' + e.message);
                    }
                });
            });
            tbody.querySelectorAll('.btn-logs-camp').forEach(btn => {
                btn.addEventListener('click', () => openCampaignLogsModal(btn.getAttribute('data-id')));
            });
            tbody.querySelectorAll('.btn-copy-camp').forEach(btn => {
                btn.addEventListener('click', () => openCampaignModal(btn.getAttribute('data-id'), true));
            });
            tbody.querySelectorAll('.btn-edit-camp').forEach(btn => {
                btn.addEventListener('click', () => openCampaignModal(btn.getAttribute('data-id'), false));
            });
            tbody.querySelectorAll('.btn-send-camp').forEach(btn => {
                btn.addEventListener('click', () => openSendModal(btn.getAttribute('data-id')));
            });
            tbody.querySelectorAll('.btn-delete-camp').forEach(btn => {
                btn.addEventListener('click', () => deleteCampaign(btn.getAttribute('data-id')));
            });

        } catch (err) {
            console.error('Kampanya listesi yüklenemedi:', err);
            tbody.innerHTML = `<tr><td colspan="6" style="color: red; text-align: center;">Hata: ${err.message}</td></tr>`;
        }
    }

    const modalCampaign = document.getElementById('modal-campaign');
    const modalCampaignTitle = document.getElementById('modal-campaign-title');
    const modalCampaignClose = document.getElementById('modal-campaign-close');
    const modalCampaignCancel = document.getElementById('modal-campaign-cancel');
    const formCampaign = document.getElementById('form-campaign');
    const btnNewCampaign = document.getElementById('btn-new-campaign');
    const btnCalcAudience = document.getElementById('btn-calc-audience');

    if (btnNewCampaign) {
        btnNewCampaign.addEventListener('click', () => openCampaignModal(null));
    }

    if (modalCampaignClose) modalCampaignClose.addEventListener('click', () => modalCampaign.classList.remove('active'));
    if (modalCampaignCancel) modalCampaignCancel.addEventListener('click', () => modalCampaign.classList.remove('active'));

    async function openCampaignModal(campId = null, isCopy = false) {
        document.getElementById('campaign-id').value = (campId && !isCopy) ? campId : '';
        document.getElementById('audience-preview-container').style.display = 'none';
        document.getElementById('target-audience-count-badge').textContent = 'Hedef kitle hesaplanmadı';

        if (!campId) {
            modalCampaignTitle.textContent = 'Yeni E-posta Kampanyası Oluştur';
            document.getElementById('campaign-name').value = '';
            document.getElementById('campaign-sender-name').value = 'Stanomer Ekibi';
            document.getElementById('campaign-subject').value = 'Unapređenje procesa nakon iznajmljivanja za vaše klijente (Besplatno rešenje)';
            document.getElementById('campaign-body').value = getDefaultCampaignTemplate();
            if (document.getElementById('campaign-lang')) document.getElementById('campaign-lang').value = 'SR_LAT';
            document.getElementById('camp-filter-city').value = '';
            document.getElementById('camp-filter-status').value = 'NEW';
            document.getElementById('camp-filter-source').value = '';
            if (document.getElementById('camp-filter-segment')) document.getElementById('camp-filter-segment').value = '';
            if (document.getElementById('camp-filter-activity-code')) document.getElementById('camp-filter-activity-code').value = '';
            modalCampaign.classList.add('active');
            updateUsedVariablesDetector();
        } else {
            modalCampaignTitle.textContent = isCopy ? 'Kampanyayı Kopyala & Yeni Oluştur' : 'Kampanyayı Düzenle';
            try {
                const res = await fetch(`/api/campaigns/${campId}`);
                const camp = await res.json();
                if (camp.error) {
                    alert(camp.error);
                    return;
                }

                document.getElementById('campaign-name').value = isCopy ? `${camp.name || ''} (Kopya)` : (camp.name || '');
                document.getElementById('campaign-sender-name').value = camp.sender_name || 'Stanomer Ekibi';
                document.getElementById('campaign-subject').value = camp.subject || '';
                document.getElementById('campaign-body').value = camp.body_html || '';
                if (document.getElementById('campaign-lang')) document.getElementById('campaign-lang').value = camp.lang || 'SR_LAT';

                let filterObj = {};
                try { filterObj = JSON.parse(camp.target_filter_json || '{}'); } catch(e) {}

                document.getElementById('camp-filter-city').value = filterObj.city || '';
                document.getElementById('camp-filter-status').value = filterObj.status || '';
                document.getElementById('camp-filter-source').value = filterObj.source || '';
                if (document.getElementById('camp-filter-segment')) {
                    document.getElementById('camp-filter-segment').value = filterObj.segment || '';
                }
                if (document.getElementById('camp-filter-activity-code')) {
                    document.getElementById('camp-filter-activity-code').value = filterObj.activity_code || '';
                }
                if (document.getElementById('camp-filter-exclude-today')) {
                    document.getElementById('camp-filter-exclude-today').checked = filterObj.exclude_today !== undefined ? Boolean(filterObj.exclude_today) : true;
                }

                modalCampaign.classList.add('active');
                calculateTargetAudience();
                updateUsedVariablesDetector();
            } catch (err) {
                alert('Kampanya detayları alınamadı: ' + err.message);
            }
        }
    }

    function updateUsedVariablesDetector() {
        const subject = document.getElementById('campaign-subject') ? document.getElementById('campaign-subject').value : '';
        const body = document.getElementById('campaign-body') ? document.getElementById('campaign-body').value : '';
        const fullContent = subject + '\n' + body;

        const varDefinitions = [
            { regex: /\{\{\s*(agency_name|name)\s*\}\}|AGENCY_NAME_PLACEHOLDER/i, desc: 'Acente Unvanı' },
            { regex: /\{\{\s*city\s*\}\}/i, desc: 'Bulunduğu Şehir' },
            { regex: /\{\{\s*ref_code\s*\}\}/i, desc: 'Referans Kodu' },
            { regex: /\{\{\s*address\s*\}\}/i, desc: 'Açık Adres' },
            { regex: /\{\{\s*unsubscribe_url\s*\}\}/i, desc: 'Abonelikten Çıkma Linki' }
        ];

        const detected = [];
        varDefinitions.forEach(def => {
            const match = fullContent.match(def.regex);
            if (match) {
                detected.push({ key: match[0], desc: def.desc });
            }
        });

        const countEl = document.getElementById('used-vars-count');
        const listEl = document.getElementById('used-vars-list');

        if (countEl) countEl.textContent = `(${detected.length})`;

        if (listEl) {
            if (detected.length === 0) {
                listEl.innerHTML = '<div style="color: #94a3b8; font-style: italic; padding: 4px 0;">Şablonda veya konuda henüz hiçbir değişken kullanılmadı.</div>';
            } else {
                listEl.innerHTML = detected.map(v => {
                    const safeKey = v.key.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                    return `
                    <div style="margin-bottom: 5px; display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.03); padding: 3px 6px; border-radius: 4px;">
                        <span style="display: inline-flex; align-items: center; gap: 0.4rem;">
                            <i class="fa-solid fa-circle-check" style="color: #34d399;"></i>
                            <code class="tooltip-code-tag" data-copy="${safeKey}">${safeKey}</code>
                        </span>
                        <span style="color: #94a3b8; font-size: 0.72rem;">${v.desc}</span>
                    </div>
                `;
                }).join('');
            }
        }
    }

    const inputCampSubject = document.getElementById('campaign-subject');
    const inputCampBody = document.getElementById('campaign-body');
    ['input', 'keyup', 'change', 'paste'].forEach(evtType => {
        if (inputCampSubject) inputCampSubject.addEventListener(evtType, () => setTimeout(updateUsedVariablesDetector, 50));
        if (inputCampBody) inputCampBody.addEventListener(evtType, () => setTimeout(updateUsedVariablesDetector, 50));
    });

    if (btnCalcAudience) {
        btnCalcAudience.addEventListener('click', calculateTargetAudience);
    }

    ['camp-filter-city', 'camp-filter-status', 'camp-filter-segment', 'camp-filter-source', 'camp-filter-activity-code', 'camp-filter-exclude-today'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', calculateTargetAudience);
    });

    async function calculateTargetAudience() {
        const city = document.getElementById('camp-filter-city').value.trim();
        const status = document.getElementById('camp-filter-status').value.trim();
        const source = document.getElementById('camp-filter-source').value.trim();
        const segment = document.getElementById('camp-filter-segment') ? document.getElementById('camp-filter-segment').value.trim() : '';
        const activity_code = document.getElementById('camp-filter-activity-code') ? document.getElementById('camp-filter-activity-code').value.trim() : '';
        const exclude_today = document.getElementById('camp-filter-exclude-today') ? document.getElementById('camp-filter-exclude-today').checked : true;

        const badge = document.getElementById('target-audience-count-badge');
        const container = document.getElementById('audience-preview-container');
        const list = document.getElementById('audience-preview-list');

        badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Hesaplamalar yapılıyor...';

        try {
            const res = await fetch('/api/campaigns/preview-audience', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_filter: { city, status, source, segment, activity_code, exclude_today } })
            });

            const data = await res.json();
            badge.textContent = `🎯 Bulunan Hedef Acente: ${data.total} adet (E-postası olanlar)`;

            if (data.agencies && data.agencies.length > 0) {
                list.innerHTML = '';
                data.agencies.slice(0, 30).forEach(ag => {
                    const li = document.createElement('li');
                    li.style.color = 'var(--text-secondary)';
                    li.innerHTML = `<strong>${escapeHtml(ag.name)}</strong> (${escapeHtml(ag.city || 'Şehir Yok')}) — <span style="color: var(--accent-indigo);">${escapeHtml(ag.emails.join(', '))}</span>`;
                    list.appendChild(li);
                });
                if (data.total > 30) {
                    const liMore = document.createElement('li');
                    liMore.style.color = 'var(--text-muted)';
                    liMore.style.fontStyle = 'italic';
                    liMore.textContent = `... ve ${data.total - 30} diğer acente.`;
                    list.appendChild(liMore);
                }
                container.style.display = 'block';
            } else {
                container.style.display = 'none';
            }
        } catch (err) {
            badge.textContent = 'Hesaplama hatası';
            console.error('Audience calc error:', err);
        }
    }

    if (formCampaign) {
        formCampaign.addEventListener('submit', async (e) => {
            e.preventDefault();
            const campId = document.getElementById('campaign-id').value;
            const name = document.getElementById('campaign-name').value.trim();
            const sender_name = document.getElementById('campaign-sender-name').value.trim();
            const subject = document.getElementById('campaign-subject').value.trim();
            const body_html = document.getElementById('campaign-body').value.trim();
            const lang = document.getElementById('campaign-lang') ? document.getElementById('campaign-lang').value : 'SR_LAT';

            const city = document.getElementById('camp-filter-city').value.trim();
            const status = document.getElementById('camp-filter-status').value.trim();
            const source = document.getElementById('camp-filter-source').value.trim();
            const segment = document.getElementById('camp-filter-segment') ? document.getElementById('camp-filter-segment').value.trim() : '';
            const activity_code = document.getElementById('camp-filter-activity-code') ? document.getElementById('camp-filter-activity-code').value.trim() : '';
            const exclude_today = document.getElementById('camp-filter-exclude-today') ? document.getElementById('camp-filter-exclude-today').checked : true;

            const payload = {
                name,
                sender_name,
                subject,
                body_html,
                lang,
                target_filter: { city, status, source, segment, activity_code, exclude_today }
            };

            try {
                const url = campId ? `/api/campaigns/${campId}` : '/api/campaigns';
                const method = campId ? 'PUT' : 'POST';

                const res = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (data.success || data.id) {
                    modalCampaign.classList.remove('active');
                    loadCampaigns();
                } else {
                    alert('Hata: ' + (data.error || 'Kaydedilemedi.'));
                }
            } catch (err) {
                alert('Kaydetme sırasında bir hata oluştu: ' + err.message);
            }
        });
    }

    async function deleteCampaign(campId) {
        if (!confirm('Bu kampanyayı silmek istediğinize emin misiniz?')) return;
        try {
            const res = await fetch(`/api/campaigns/${campId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                loadCampaigns();
            } else {
                alert(data.error || 'Kampanya silinemedi.');
            }
        } catch (err) {
            alert('Silme sırasında hata: ' + err.message);
        }
    }

    const modalSendCampaign = document.getElementById('modal-send-campaign');
    const modalSendClose = document.getElementById('modal-send-close');
    const modalSendCancel = document.getElementById('modal-send-cancel');
    const btnSendTestEmail = document.getElementById('btn-send-test-email');
    const btnStartRealSend = document.getElementById('btn-start-real-send');

    if (modalSendClose) modalSendClose.addEventListener('click', () => {
        modalSendCampaign.classList.remove('active');
        if (sendProgressTimer) clearInterval(sendProgressTimer);
    });

    if (modalSendCancel) modalSendCancel.addEventListener('click', () => {
        modalSendCampaign.classList.remove('active');
        if (sendProgressTimer) clearInterval(sendProgressTimer);
    });

    async function openSendModal(campId) {
        document.getElementById('send-campaign-id').value = campId;
        document.getElementById('send-progress-container').style.display = 'none';

        if (btnStartRealSend) {
            btnStartRealSend.disabled = false;
            btnStartRealSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Toplu Gönderimi Başlat (Gerçek)';
        }
        if (btnSendTestEmail) {
            btnSendTestEmail.disabled = false;
            btnSendTestEmail.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Test Gönder';
        }
        if (document.getElementById('btn-stop-send')) {
            document.getElementById('btn-stop-send').style.display = 'none';
        }

        try {
            const res = await fetch(`/api/campaigns/${campId}`);
            const camp = await res.json();
            if (camp.error) {
                alert(camp.error);
                return;
            }

            document.getElementById('send-camp-name').textContent = camp.name;
            document.getElementById('send-camp-subject').textContent = 'Konu: ' + camp.subject;

            let filterObj = {};
            try { filterObj = JSON.parse(camp.target_filter_json || '{}'); } catch(e) {}

            let filterParts = [];
            if (filterObj.status) filterParts.push(`Statü = <span style="color:var(--accent-indigo); font-weight:700;">${filterObj.status}</span>`);
            else filterParts.push(`Statü = <i>Tüm Statüler</i>`);
            if (filterObj.segment) filterParts.push(`Segment = <span style="color:var(--accent-indigo); font-weight:700;">${filterObj.segment}</span>`);
            if (filterObj.city) filterParts.push(`Şehir = <strong>${filterObj.city}</strong>`);
            if (filterObj.source) filterParts.push(`Kaynak = <strong>${filterObj.source}</strong>`);
            
            const isExcludeToday = filterObj.exclude_today !== undefined ? Boolean(filterObj.exclude_today) : true;
            filterParts.push(`Bugün Gönderilenler = <strong>${isExcludeToday ? 'Hariç Tutuluyor ✅' : 'Dahil ⚠️'}</strong>`);

            const filtersEl = document.getElementById('send-camp-filters');
            if (filtersEl) {
                filtersEl.innerHTML = `🎯 <strong>Hedef Kriterleri:</strong> ${filterParts.join(' • ')}`;
            }

            const resAudience = await fetch('/api/campaigns/preview-audience', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_filter: filterObj })
            });
            const dataAudience = await resAudience.json();
            document.getElementById('send-total-recipients').textContent = dataAudience.total || 0;

            modalSendCampaign.classList.add('active');
        } catch (err) {
            alert('Gönderim paneli açılamadı: ' + err.message);
        }
    }

    if (btnSendTestEmail) {
        btnSendTestEmail.addEventListener('click', async () => {
            const campId = document.getElementById('send-campaign-id').value;
            const testEmail = document.getElementById('test-email-input').value.trim();

            if (!testEmail) {
                alert('Lütfen bir test e-posta adresi yazın.');
                return;
            }

            btnSendTestEmail.disabled = true;
            btnSendTestEmail.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Gönderiliyor...';

            try {
                const res = await fetch(`/api/campaigns/${campId}/send`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ test_email: testEmail })
                });

                const data = await res.json();
                if (data.success) {
                    document.getElementById('send-progress-container').style.display = 'block';
                    pollSendingProgress(campId, true);
                } else {
                    alert('Hata: ' + (data.error || 'Test maili başlatılamadı.'));
                }
            } catch (err) {
                alert('Test maili hatası: ' + err.message);
            } finally {
                btnSendTestEmail.disabled = false;
                btnSendTestEmail.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Test Gönder';
            }
        });
    }

    if (btnStartRealSend) {
        btnStartRealSend.addEventListener('click', async () => {
            const campId = document.getElementById('send-campaign-id').value;
            const count = document.getElementById('send-total-recipients').textContent;

            if (count === '0') {
                alert('Bu kampanyanın hedef kitlesinde e-postaya sahip acente bulunmuyor.');
                return;
            }

            if (!confirm(`Filtrelenen ${count} acenteye gerçekten toplu e-posta gönderimini başlatmak istiyor musunuz?`)) {
                return;
            }

            btnStartRealSend.disabled = true;
            btnStartRealSend.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Başlatıldı';

            try {
                const res = await fetch(`/api/campaigns/${campId}/send`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });

                const data = await res.json();
                if (data.success) {
                    document.getElementById('send-progress-container').style.display = 'block';
                    if (document.getElementById('btn-stop-send')) document.getElementById('btn-stop-send').style.display = 'inline-block';
                    pollSendingProgress(campId, false);
                } else {
                    alert('Hata: ' + (data.error || 'Gönderim başlatılamadı.'));
                    btnStartRealSend.disabled = false;
                    btnStartRealSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Toplu Gönderimi Başlat (Gerçek)';
                }
            } catch (err) {
                alert('Gönderim başlatılırken hata: ' + err.message);
                btnStartRealSend.disabled = false;
                btnStartRealSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Toplu Gönderimi Başlat (Gerçek)';
            }
        });
    }

    const btnStopSend = document.getElementById('btn-stop-send');
    if (btnStopSend) {
        btnStopSend.addEventListener('click', async () => {
            const campId = document.getElementById('send-campaign-id').value;
            if (!campId) return;
            btnStopSend.disabled = true;
            btnStopSend.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Durduruluyor...';
            try {
                const res = await fetch(`/api/campaigns/${campId}/stop`, { method: 'POST' });
                const data = await res.json();
                alert(data.message || 'Gönderim işlemi durduruldu.');
            } catch (e) {
                alert('Durdurma hatası: ' + e.message);
            } finally {
                btnStopSend.disabled = false;
                btnStopSend.innerHTML = '<i class="fa-solid fa-hand"></i> Gönderimi Durdur';
            }
        });
    }

    function pollSendingProgress(campId, isTest = false) {
        if (sendProgressTimer) clearInterval(sendProgressTimer);

        const logsBox = document.getElementById('send-logs-box');
        const progressBar = document.getElementById('send-progress-bar');
        const progressPct = document.getElementById('send-progress-pct');
        const statusText = document.getElementById('send-status-text');

        sendProgressTimer = setInterval(async () => {
            try {
                const res = await fetch(`/api/campaigns/${campId}/progress${isTest ? '?test=1' : ''}`);
                const data = await res.json();

                const total = data.total || 1;
                const sent = data.sent || 0;
                const failed = data.failed || 0;
                const current = sent + failed;
                const pct = Math.round((current / total) * 100);

                progressBar.style.width = pct + '%';
                progressPct.textContent = pct + '%';

                if (data.status === 'RUNNING') {
                    statusText.textContent = `Gönderiliyor (${current}/${total}) - Şu An: ${data.current_agency || 'Acente...'}`;
                } else if (data.status === 'COMPLETED') {
                    statusText.textContent = `✅ Gönderim Tamamlandı! (${sent} Başarılı, ${failed} Hata)`;
                    clearInterval(sendProgressTimer);
                    if (btnStartRealSend) {
                        btnStartRealSend.disabled = false;
                        btnStartRealSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Toplu Gönderimi Başlat (Gerçek)';
                    }
                    if (document.getElementById('btn-stop-send')) {
                        document.getElementById('btn-stop-send').style.display = 'none';
                    }
                    loadCampaigns();
                } else if (data.status === 'STOPPED' || data.status === 'FAILED') {
                    statusText.textContent = `🛑 Gönderim Durduruldu / Bitti (${sent} Başarılı, ${failed} Hata)`;
                    clearInterval(sendProgressTimer);
                    if (btnStartRealSend) {
                        btnStartRealSend.disabled = false;
                        btnStartRealSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Toplu Gönderimi Başlat (Gerçek)';
                    }
                    if (document.getElementById('btn-stop-send')) {
                        document.getElementById('btn-stop-send').style.display = 'none';
                    }
                    loadCampaigns();
                }

                if (Array.isArray(data.logs) && data.logs.length > 0) {
                    logsBox.innerHTML = data.logs.map(l => `<div>${escapeHtml(l)}</div>`).join('');
                    logsBox.scrollTop = logsBox.scrollHeight;
                }
            } catch (err) {
                console.error('Progress poll error:', err);
            }
        }, 1500);
    }

    const modalCampaignLogs = document.getElementById('modal-campaign-logs');
    const modalCampLogsClose = document.getElementById('modal-camp-logs-close');
    const modalCampLogsCancel = document.getElementById('modal-camp-logs-cancel');
    const campLogsSearch = document.getElementById('camp-logs-search');
    let currentCampLogs = [];

    if (modalCampLogsClose) modalCampLogsClose.addEventListener('click', () => modalCampaignLogs.classList.remove('active'));
    if (modalCampLogsCancel) modalCampLogsCancel.addEventListener('click', () => modalCampaignLogs.classList.remove('active'));

    if (campLogsSearch) {
        campLogsSearch.addEventListener('input', () => renderCampLogsTable(campLogsSearch.value.trim().toLowerCase()));
    }

    async function openCampaignLogsModal(campId) {
        if (!modalCampaignLogs) return;

        document.getElementById('camp-logs-tbody').innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> İletişim geçmişi yükleniyor...</td></tr>';
        modalCampaignLogs.classList.add('active');

        try {
            const [resCamp, resLogs] = await Promise.all([
                fetch(`/api/campaigns/${campId}`),
                fetch(`/api/campaigns/${campId}/communications`)
            ]);

            const camp = await resCamp.json();
            const dataLogs = await resLogs.json();

            document.getElementById('modal-camp-logs-subtitle').textContent = `Kampanya: ${camp.name || 'İsimsiz'} • Konu: ${camp.subject || '-'}`;
            currentCampLogs = dataLogs.logs || [];

            const totalSent = currentCampLogs.length;
            const uniqueAgencies = new Set(currentCampLogs.map(l => l.agency_id).filter(Boolean)).size;

            document.getElementById('camp-logs-total-sent').textContent = totalSent;
            document.getElementById('camp-logs-total-agencies').textContent = uniqueAgencies;

            if (campLogsSearch) campLogsSearch.value = '';
            renderCampLogsTable('');
        } catch (err) {
            document.getElementById('camp-logs-tbody').innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">Yükleme hatası: ${escapeHtml(err.message)}</td></tr>`;
        }
    }

    function renderCampLogsTable(query = '') {
        const tbody = document.getElementById('camp-logs-tbody');
        if (!tbody) return;

        let filtered = currentCampLogs;
        if (query) {
            filtered = currentCampLogs.filter(l => 
                (l.agency_name || '').toLowerCase().includes(query) ||
                (l.recipient || '').toLowerCase().includes(query) ||
                (l.agency_city || '').toLowerCase().includes(query)
            );
        }

        const countInfo = document.getElementById('camp-logs-count-info');
        if (countInfo) countInfo.textContent = `${filtered.length} / ${currentCampLogs.length} iletişim kaydı gösteriliyor`;

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">Hiçbir gönderim kaydı bulunamadı.</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(l => {
            const dateStr = l.date ? l.date.replace('T', ' ').split('.')[0] : '-';
            const statusTag = l.status === 'SENT' 
                ? '<span class="status-tag tag-sent">Gönderildi</span>'
                : `<span class="status-tag tag-failed">${escapeHtml(l.status || 'Bilinmiyor')}</span>`;

            return `
                <tr style="border-bottom: 1px solid var(--border-color);">
                    <td style="padding: 0.6rem 0.8rem; font-family: monospace; font-size: 0.78rem; color: var(--text-secondary);">${escapeHtml(dateStr)}</td>
                    <td style="padding: 0.6rem 0.8rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(l.agency_name || 'Test Acentesi')}</td>
                    <td style="padding: 0.6rem 0.8rem; color: var(--text-muted);">${escapeHtml(l.agency_city || '-')}</td>
                    <td style="padding: 0.6rem 0.8rem; font-family: monospace; font-size: 0.78rem; color: var(--accent-indigo);">${escapeHtml(l.recipient || '-')}</td>
                    <td style="padding: 0.6rem 0.8rem;">${statusTag}</td>
                    <td style="padding: 0.6rem 0.8rem; text-align: right;">
                        <button class="btn btn-xs btn-secondary btn-view-log-msg" data-msg="${escapeHtml(l.message || '')}" data-subj="${escapeHtml(l.agency_name || '')}" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">
                            <i class="fa-solid fa-eye"></i> Mesaj
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('.btn-view-log-msg').forEach(btn => {
            btn.addEventListener('click', () => {
                const msg = btn.getAttribute('data-msg');
                const title = btn.getAttribute('data-subj');
                openEmailPreviewModal(`Gönderilen Mesaj: ${title}`, msg, 0, 'SR_LAT');
            });
        });
    }

    function getDefaultCampaignTemplate() {
        return `<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <title>Stanomer - {{agency_name}}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #eef2f6; font-family: 'Plus Jakarta Sans', Arial, sans-serif; color: #4b5563;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr><td align="center" style="padding: 40px 10px;">
            <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); overflow: hidden; max-width: 600px; width: 100%;">
                <tr><td align="center" style="padding: 40px 40px 0 40px;">
                    <img src="https://www.stanomer.online/assets/logo.png" alt="Stanomer Logo" width="150" style="display: block; max-width: 150px; height: auto;">
                </td></tr>
                <tr><td style="padding: 40px;">
                    <p style="font-size: 16px; line-height: 1.6; margin-top: 0; margin-bottom: 20px; font-weight: 600; color: #111827;">
                        Poštovani tim {{agency_name}},
                    </p>
                    <p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 20px;">
                        Nakon što se ugovor o zakupu potpiše, praćenje mesečne kirije i arhiviranje računa između stanodavca i zakupca često ostaje neformalizovano — što ponekad dovodi do nesporazuma ili kašnjenja.
                    </p>
                    <p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 20px;">
                        Naš digitalni asistent, <a href="https://www.stanomer.online" style="color: #3b82f6; text-decoration: none; font-weight: 800;">Stanomer</a>, rešava upravo taj problem: automatizuje naplatu kirije i arhiviranje računa između stanodavaca i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz vašeg portfolija i njihove zakupce.
                    </p>
                    <p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 25px;">
                        Za više informacija posetite <a href="https://stanomer.online" style="color: #3b82f6; text-decoration: none; font-weight: 800;">stanomer.online</a>.
                    </p>
                    <p style="margin-top: 25px; margin-bottom: 30px; text-align: center;">
                        <a href="https://www.stanomer.online" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none !important; padding: 12px 24px; border-radius: 6px; font-size: 15px; font-weight: 600; text-align: center;"><span style="color: #ffffff !important; text-decoration: none !important;">Zakažite Demo / Zatražite Sandbox</span></a>
                    </p>
                    <p style="margin: 0; color: #6b7280;">Srdačan pozdrav,<br><strong>Stanomer Ekibi</strong></p>
                    <div style="margin-top: 35px; text-align: center; font-size: 12px; color: #9ca3af; border-top: 1px solid #f3f4f6; padding-top: 20px;">
                        Ako ne želite da primate više obaveštenja od nas, možete se <a href="{{unsubscribe_url}}" style="color: #6b7280; text-decoration: underline;">odjaviti ovde</a>.
                    </div>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ─── E-POSTA CANLI ÖNİZLEME MODALI ──────────────────────────────────────
    const modalEmailPreview = document.getElementById('modal-email-preview');
    const modalPreviewClose = document.getElementById('modal-preview-close');
    const modalPreviewCancel = document.getElementById('modal-preview-cancel');
    const previewAgencySelect = document.getElementById('preview-agency-select');
    const previewSubjectDisplay = document.getElementById('preview-subject-display');
    const previewRecipientDisplay = document.getElementById('preview-recipient-display');
    const emailPreviewIframe = document.getElementById('email-preview-iframe');
    const btnPreviewCampaignHtml = document.getElementById('btn-preview-campaign-html');

    const btnViewDesktop = document.getElementById('btn-preview-view-desktop');
    const btnViewMobile = document.getElementById('btn-preview-view-mobile');
    const btnViewFull = document.getElementById('btn-preview-view-full');

    let currentPreviewSubject = '';
    let currentPreviewBodyHtml = '';
    let previewAgenciesList = [];

    if (modalPreviewClose) modalPreviewClose.addEventListener('click', () => modalEmailPreview.classList.remove('active'));
    if (modalPreviewCancel) modalPreviewCancel.addEventListener('click', () => modalEmailPreview.classList.remove('active'));

    // Device View Mode Switcher
    if (btnViewDesktop) {
        btnViewDesktop.addEventListener('click', () => {
            emailPreviewIframe.style.width = '600px';
            btnViewDesktop.classList.add('active');
            if (btnViewMobile) btnViewMobile.classList.remove('active');
            if (btnViewFull) btnViewFull.classList.remove('active');
        });
    }
    if (btnViewMobile) {
        btnViewMobile.addEventListener('click', () => {
            emailPreviewIframe.style.width = '375px';
            btnViewMobile.classList.add('active');
            if (btnViewDesktop) btnViewDesktop.classList.remove('active');
            if (btnViewFull) btnViewFull.classList.remove('active');
        });
    }
    if (btnViewFull) {
        btnViewFull.addEventListener('click', () => {
            emailPreviewIframe.style.width = '100%';
            btnViewFull.classList.add('active');
            if (btnViewDesktop) btnViewDesktop.classList.remove('active');
            if (btnViewMobile) btnViewMobile.classList.remove('active');
        });
    }

    // Populate Test Agencies Select box
    async function loadPreviewAgencies() {
        if (previewAgenciesList.length > 0) return;
        try {
            const res = await fetch('/api/agencies');
            const data = await res.json();
            if (Array.isArray(data)) {
                previewAgenciesList = data;
                previewAgencySelect.innerHTML = '<option value="0">⚡ Varsayılan Örnek Acente (Beoexpert)</option>';
                data.slice(0, 100).forEach(ag => {
                    const opt = document.createElement('option');
                    opt.value = ag.id;
                    opt.textContent = `${ag.name} (${ag.city || 'Şehir Yok'})`;
                    previewAgencySelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Önizleme acente listesi alınamadı:', e);
        }
    }

    let currentPreviewLang = 'SR_LAT';

    async function updateEmailPreview(agencyId = 0) {
        try {
            const res = await fetch('/api/campaigns/preview-html', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subject: currentPreviewSubject,
                    body_html: currentPreviewBodyHtml,
                    lang: currentPreviewLang,
                    agency_id: parseInt(agencyId) || 0
                })
            });
            const data = await res.json();
            if (data.error) {
                alert('Önizleme hatası: ' + data.error);
                return;
            }

            previewSubjectDisplay.textContent = data.subject || '(Konu yok)';
            const emails = (data.agency && data.agency.emails && data.agency.emails.length > 0) ? data.agency.emails.join(', ') : 'info@beoexpert.rs';
            previewRecipientDisplay.textContent = `${data.agency.name} <${emails}>`;
            
            // Inject into iframe safely using srcdoc
            emailPreviewIframe.srcdoc = data.body_html || '<p style="padding: 2rem; color: #666;">Şablon içeriği boş.</p>';
        } catch (err) {
            console.error('Email preview fetch error:', err);
        }
    }

    window.openEmailPreviewModal = async function(subject, bodyHtml, agencyId = 0, lang = 'SR_LAT') {
        currentPreviewSubject = subject || '';
        currentPreviewBodyHtml = bodyHtml || '';
        currentPreviewLang = lang || 'SR_LAT';
        
        modalEmailPreview.classList.add('active');
        await loadPreviewAgencies();
        
        previewAgencySelect.value = agencyId || 0;
        await updateEmailPreview(agencyId || 0);
    };

    if (previewAgencySelect) {
        previewAgencySelect.addEventListener('change', (e) => {
            updateEmailPreview(e.target.value);
        });
    }

    if (btnPreviewCampaignHtml) {
        btnPreviewCampaignHtml.addEventListener('click', () => {
            const subject = document.getElementById('campaign-subject').value;
            const bodyHtml = document.getElementById('campaign-body').value;
            const lang = document.getElementById('campaign-lang') ? document.getElementById('campaign-lang').value : 'SR_LAT';
            openEmailPreviewModal(subject, bodyHtml, 0, lang);
        });
    }

    // ─── UNSUBSCRIBES MANAGEMENT ──────────────────────────────────────────
    async function loadUnsubscribes() {
        const tbody = document.getElementById('unsubscribes-table-body');
        const countBadge = document.getElementById('unsubscribes-menu-count');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Yükleniyor...</td></tr>';

        try {
            const res = await fetch('/api/unsubscribes');
            const data = await res.json();
            if (Array.isArray(data)) {
                if (countBadge) countBadge.textContent = `${data.length} Adres`;

                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem; color: var(--text-muted);">Henüz abonelikten çıkan e-posta adresi bulunmuyor.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.forEach(item => {
                    const tr = document.createElement('tr');
                    const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';
                    const agencyName = item.agency_name ? escapeHtml(item.agency_name) : (item.agency_id ? `Acente #${item.agency_id}` : '-');

                    tr.innerHTML = `
                        <td>
                            <code style="font-size: 0.88rem; color: #ef4444; background: rgba(239, 68, 68, 0.08); padding: 3px 8px; border-radius: 4px; font-weight: 600;">${escapeHtml(item.email)}</code>
                        </td>
                        <td>
                            <strong style="color: var(--text-primary); font-size: 0.88rem;">${agencyName}</strong>
                        </td>
                        <td>
                            <span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(item.reason || 'Web sayfasından odjava')}</span>
                        </td>
                        <td>
                            <span style="font-size: 0.82rem; color: var(--text-muted);">${dateStr}</span>
                        </td>
                        <td style="text-align: right;">
                            <button class="btn btn-sm btn-secondary btn-resubscribe-email" data-email="${escapeHtml(item.email)}" title="Yeniden Abone Yap (Listeden Çıkar)">
                                <i class="fa-solid fa-rotate-left"></i> Yeniden Abone Yap
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });

                tbody.querySelectorAll('.btn-resubscribe-email').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const email = btn.getAttribute('data-email');
                        if (confirm(`"${email}" adresini yeniden bülten listesine eklemek istediğinizden emin misiniz?`)) {
                            try {
                                const delRes = await fetch(`/api/unsubscribes/${encodeURIComponent(email)}`, { method: 'DELETE' });
                                const delData = await delRes.json();
                                if (delData.success) {
                                    loadUnsubscribes();
                                    loadStats();
                                } else {
                                    alert('Hata: ' + (delData.error || 'İşlem başarısız'));
                                }
                            } catch (err) {
                                alert('Hata: ' + err.message);
                            }
                        }
                    });
                });
            }
        } catch (err) {
            console.error('Unsubscribes yükleme hatası:', err);
            tbody.innerHTML = `<tr><td colspan="5" style="color: red; text-align: center;">Hata: ${err.message}</td></tr>`;
        }
    }

    const btnRefreshUnsubscribes = document.getElementById('btn-refresh-unsubscribes');
    if (btnRefreshUnsubscribes) {
        btnRefreshUnsubscribes.addEventListener('click', loadUnsubscribes);
    }

    const btnSyncSupabaseUnsubscribes = document.getElementById('btn-sync-supabase-unsubscribes');
    if (btnSyncSupabaseUnsubscribes) {
        btnSyncSupabaseUnsubscribes.addEventListener('click', async () => {
            let key = localStorage.getItem('supabase_service_role_key') || '';
            if (!key) {
                key = prompt("Lütfen Supabase SERVICE_ROLE_KEY değerini giriniz:");
                if (!key || !key.trim()) return;
                key = key.strip ? key.strip() : key.trim();
                if (confirm("Bu anahtarı sonraki senkronizasyonlar için tarayıcınızda hatırlayalım mı?")) {
                    localStorage.setItem('supabase_service_role_key', key);
                }
            }

            btnSyncSupabaseUnsubscribes.disabled = true;
            btnSyncSupabaseUnsubscribes.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Eşitleniyor...';

            try {
                const res = await fetch('/api/unsubscribes/sync-supabase', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service_role_key: key })
                });
                const result = await res.json();
                if (result.success) {
                    alert(`✅ Supabase Sync Başarılı!\n\n• Toplam Çekilen: ${result.fetched}\n• Yeni Eklenen: ${result.inserted}\n• Zaten Mevcut: ${result.skipped}\n• Hatalı: ${result.errors}`);
                    loadUnsubscribes();
                    loadStats();
                } else {
                    if (result.error && (result.error.includes("Key") || result.error.includes("401"))) {
                        localStorage.removeItem('supabase_service_role_key');
                    }
                    alert('⚠️ Sync Hatası: ' + (result.error || 'Bilinmeyen hata'));
                }
            } catch (err) {
                alert('⚠️ Bağlantı Hatası: ' + err.message);
            } finally {
                btnSyncSupabaseUnsubscribes.disabled = false;
                btnSyncSupabaseUnsubscribes.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Supabase\'den Sync Et';
            }
        });
    }

    // Click-to-copy for tooltip code tags
    document.addEventListener('click', (e) => {
        const codeTag = e.target.closest('.tooltip-code-tag');
        if (codeTag) {
            const textToCopy = codeTag.getAttribute('data-copy') || codeTag.textContent.trim();
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(textToCopy);
            } else {
                const tempInput = document.createElement('textarea');
                tempInput.value = textToCopy;
                document.body.appendChild(tempInput);
                tempInput.select();
                document.execCommand('copy');
                document.body.removeChild(tempInput);
            }
            // Visual feedback: green glow without altering variable text
            codeTag.style.transition = 'all 0.2s ease';
            codeTag.style.background = '#059669';
            codeTag.style.color = '#ffffff';
            codeTag.style.borderColor = '#10b981';
            codeTag.style.boxShadow = '0 0 8px rgba(16, 185, 129, 0.6)';

            let feedback = document.getElementById('copy-feedback-toast');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.id = 'copy-feedback-toast';
                feedback.style.position = 'fixed';
                feedback.style.zIndex = '100000';
                feedback.style.background = '#059669';
                feedback.style.color = '#ffffff';
                feedback.style.fontSize = '0.75rem';
                feedback.style.fontWeight = '700';
                feedback.style.padding = '4px 10px';
                feedback.style.borderRadius = '12px';
                feedback.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
                feedback.style.pointerEvents = 'none';
                feedback.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
                document.body.appendChild(feedback);
            }

            const rect = codeTag.getBoundingClientRect();
            feedback.textContent = '✓ Kopyalandı!';
            feedback.style.top = (rect.top - 28) + 'px';
            feedback.style.left = (rect.left + rect.width / 2) + 'px';
            feedback.style.transform = 'translateX(-50%)';
            feedback.style.opacity = '1';

            setTimeout(() => {
                codeTag.style.background = '';
                codeTag.style.color = '';
                codeTag.style.borderColor = '';
                codeTag.style.boxShadow = '';
                if (feedback) feedback.style.opacity = '0';
            }, 1200);
        }
    });

    // Initial Load
    loadStats();
    loadAgencies();
});


