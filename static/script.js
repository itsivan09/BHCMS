document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Notification Dropdown Logic
    const notifBtn = document.getElementById('notificationBtn');
    const notifDrop = document.getElementById('notificationDropdown');
    
    if (notifBtn && notifDrop) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifDrop.classList.toggle('show');
        });
        document.addEventListener('click', (e) => {
            if (!notifDrop.contains(e.target) && !notifBtn.contains(e.target)) {
                notifDrop.classList.remove('show');
            }
        });
    }

    // 2. Global Search Logic (Works for Inventory & Patients)
    const searchInput = document.getElementById('searchInput') || document.getElementById('inventory-search');
    
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const value = this.value.toLowerCase();
            const rows = document.querySelectorAll("table tbody tr");
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(value) ? "" : "none";
            });
        });
    }

    // 3. Make all magnifier/search icons clickable
    function findRelatedSearchInput(triggerEl) {
        const wrappers = [
            triggerEl.closest('.input-group'),
            triggerEl.closest('.patient-search-wrap'),
            triggerEl.closest('.g-patient-search-wrap'),
            triggerEl.closest('.inv-search-wrap'),
            triggerEl.parentElement
        ].filter(Boolean);

        for (const wrapper of wrappers) {
            const candidate = wrapper.querySelector('input[type="search"], input[type="text"], input:not([type])');
            if (candidate && !candidate.disabled) {
                return candidate;
            }
        }
        return null;
    }

    function activateSearchTrigger(triggerEl, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        const input = findRelatedSearchInput(triggerEl);
        if (!input) return;

        input.dataset.openAllOnIcon = '1';
        input.focus();
        input.dispatchEvent(new Event('focus', { bubbles: true }));
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
        setTimeout(() => {
            if (input && input.dataset) delete input.dataset.openAllOnIcon;
        }, 0);
    }

    function bindSearchTrigger(triggerEl) {
        if (!triggerEl || triggerEl.dataset.searchTriggerBound === '1') return;
        triggerEl.dataset.searchTriggerBound = '1';

        if (triggerEl.tagName !== 'BUTTON') {
            triggerEl.setAttribute('role', 'button');
            triggerEl.setAttribute('tabindex', '0');
        }
        triggerEl.style.cursor = 'pointer';

        triggerEl.addEventListener('click', function(e) {
            activateSearchTrigger(triggerEl, e);
        });

        triggerEl.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                activateSearchTrigger(triggerEl, e);
            }
        });
    }

    const searchTriggers = Array.from(document.querySelectorAll(
        '.patient-search-wrap .search-icon, .g-patient-search-wrap .g-search-icon, .inv-search-wrap .fa-search, .input-group .fa-search, .input-group .input-group-text'
    )).filter(el => {
        if (el.classList.contains('search-icon') || el.classList.contains('g-search-icon')) return true;
        if (el.classList.contains('fa-search') || el.classList.contains('fa-magnifying-glass')) return true;
        return !!el.querySelector('.fa-search, .fa-magnifying-glass');
    });

    searchTriggers.forEach(bindSearchTrigger);

});

window.BHCMSNameUtils = (function() {
    function titleCaseWords(value) {
        return (value || '')
            .toLowerCase()
            .split(' ')
            .filter(part => part.trim() !== '')
            .map(part => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' ');
    }

    function sanitizeNamePart(value) {
        const cleaned = (value || '').replace(/[^A-Za-zÑñ\s]/g, '');
        return titleCaseWords(cleaned);
    }

    function setNameValidity(inputEl) {
        if (!inputEl) return;
        if (!inputEl.value.trim() && inputEl.required) {
            inputEl.setCustomValidity('This field is required.');
        } else if (inputEl.value && !/^[A-Za-zÑñ]+( [A-Za-zÑñ]+)*$/.test(inputEl.value)) {
            inputEl.setCustomValidity('Use letters and spaces only.');
        } else {
            inputEl.setCustomValidity('');
        }
    }

    function normalizeMiddleInitial(value) {
        const raw = (value || '').toUpperCase().replace(/[^A-Z\/]/g, '');
        if (raw === 'N' || raw === 'N/' || raw === 'N/A') {
            return raw === 'N' ? 'N' : (raw === 'N/' ? 'N/' : 'N/A');
        }
        return raw.replace(/[^A-Z]/g, '').slice(0, 1);
    }

    function finalizeMiddleInitial(value) {
        const clean = (value || '').trim().toUpperCase();
        if (clean === 'NA' || clean === 'N/A') return 'N/A';
        return clean.replace(/[^A-Z]/g, '').slice(0, 1);
    }

    function bindNameTextInput(inputEl, onChange) {
        if (!inputEl || inputEl.dataset.nameBound === '1') return;
        inputEl.dataset.nameBound = '1';

        inputEl.addEventListener('input', function() {
            this.value = sanitizeNamePart(this.value);
            setNameValidity(this);
            if (typeof onChange === 'function') onChange(this);
        });

        inputEl.addEventListener('blur', function() {
            this.value = sanitizeNamePart(this.value);
            setNameValidity(this);
            if (typeof onChange === 'function') onChange(this);
        });

        inputEl.addEventListener('invalid', function() {
            setNameValidity(this);
        });
    }

    function bindMiddleInitialInput(inputEl, onChange) {
        if (!inputEl || inputEl.dataset.middleBound === '1') return;
        inputEl.dataset.middleBound = '1';

        inputEl.addEventListener('input', function() {
            this.value = normalizeMiddleInitial(this.value);
            if (typeof onChange === 'function') onChange(this);
        });

        inputEl.addEventListener('blur', function() {
            this.value = finalizeMiddleInitial(this.value);
            if (typeof onChange === 'function') onChange(this);
        });
    }

    return {
        titleCaseWords,
        sanitizeNamePart,
        normalizeMiddleInitial,
        finalizeMiddleInitial,
        setNameValidity,
        bindNameTextInput,
        bindMiddleInitialInput
    };
})();

/* --- NEW: MEDICAL HISTORY MODAL LOGIC --- */
function viewMedicalHistory(patientId, patientName) {
    const nameSpan = document.getElementById('historyPatientName');
    if (nameSpan) nameSpan.textContent = patientName;

    const tbody = document.getElementById('historyTableBody');
    const loading = document.getElementById('historyLoading');
    const empty = document.getElementById('historyEmpty');

    if (tbody) tbody.innerHTML = '';
    if (loading) loading.style.display = 'block';
    if (empty) empty.style.display = 'none';

    const modal = new bootstrap.Modal(document.getElementById('historyModal'));
    modal.show();

    fetch(`/api/patient/${patientId}/history`)
        .then(response => response.json())
        .then(data => {
            if (loading) loading.style.display = 'none';

            if (data.length === 0) {
                if (empty) empty.style.display = 'block';
            } else {
                data.forEach(record => {
                    const row = `
                        <tr>
                            <td>${record.date}</td>
                            <td><span class="badge bg-info text-dark">${record.type}</span></td>
                            <td>
                                <div class="fw-bold">${record.diagnosis}</div>
                                <small class="text-muted">${record.complaint}</small>
                            </td>
                            <td>${record.bp}</td>
                        </tr>
                    `;
                    if (tbody) tbody.innerHTML += row;
                });
            }
        })
        .catch(error => {
            console.error('Error:', error);
            if (loading) loading.innerHTML = '<p class="text-danger">Error loading data</p>';
        });
}