<!-- Mississippi_Stud_Poker.php - 密西西比梭哈扑克统计页面 -->
<div class="msp-content">
    <!-- 对局总览 + 结果分布（1/3 与 2/3 比例） -->
    <div class="dashboard-grid">
        <!-- 对局总览卡片（占 1/3） -->
        <div class="card overview-card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>对局总览</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item">
                    <div class="stat-value" id="msp-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="msp-winrate">0%</div>
                    <div class="stat-label">胜率</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="msp-wins">0</div>
                    <div class="stat-label">赢局</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="msp-losses">0</div>
                    <div class="stat-label">输局</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#f0ad4e;" id="msp-pushes">0</div>
                    <div class="stat-label">平局</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#aaa;" id="msp-folds">0</div>
                    <div class="stat-label">弃牌局</div>
                </div>
            </div>
        </div>

        <!-- 结果分布卡片（占 2/3） -->
        <div class="card result-card">
            <div class="card-header">
                <i class="fas fa-flag-checkered"></i>
                <h2>牌型结果分布</h2>
            </div>
            <div class="stats-grid-result" id="msp-result-grid">
                <!-- 通过 JS 动态生成 -->
            </div>
        </div>
    </div>

    <!-- 对局记录 -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-list-ul"></i>
            <h2>对局记录</h2>
            <div style="margin-left:auto;display:flex;gap:10px;">
                <button class="page-btn active" data-page="latest" id="mspPageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="mspPageOldest">最旧25局</button>
            </div>
        </div>
        <div class="msp-table-wrap">
            <table class="msp-table" id="msp-history-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>时间</th>
                        <th>底牌</th>
                        <th>公共牌</th>
                        <th>结果</th>
                        <th>赢钱</th>
                    </tr>
                </thead>
                <tbody id="msp-history-body">
                    <tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 模态框 -->
    <div class="modal-overlay" id="mspDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> 对局详情</h2>
                <button class="modal-close" id="mspModalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">底牌</div>
                            <div class="hand-cards" id="msp-detail-player">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">公共牌</div>
                            <div class="hand-cards" id="msp-detail-comm">—</div>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">时间</span>
                            <span class="footer-value" id="msp-detail-time">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">结果</span>
                            <span class="footer-value" id="msp-detail-result">—</span>
                        </div>
                    </div>
                    <div class="detail-right">
                        <div class="detail-meta-row">
                            <div class="meta-item">
                                <span class="meta-label">局号</span>
                                <span class="meta-value" id="msp-detail-index">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">切牌位置</span>
                                <span class="meta-value" id="msp-detail-cut">—</span>
                            </div>
                        </div>
                        <div class="deck-section">
                            <div class="deck-label">牌堆顺序 (52张)</div>
                            <div class="deck-cards" id="msp-detail-deck"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .msp-content .dashboard-grid {
        display: grid;
        grid-template-columns: 1fr 2fr;   /* 1/3 与 2/3 比例 */
        gap: 25px;
        margin-bottom: 35px;
    }
    .msp-content .stats-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    .msp-content .stats-grid-result {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
    }
    .msp-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 14px 10px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .msp-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .msp-content .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .msp-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .msp-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
    }
    .msp-content .stat-label {
        font-size: 0.85rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .msp-content .stat-sub {
        font-size: 0.8rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .msp-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 22px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .msp-content .card:hover {
        transform: translateY(-3px);
    }
    .msp-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .msp-content .card-header i {
        font-size: 1.5rem;
        margin-right: 12px;
        color: #ffcc00;
    }
    .msp-content .card-header h2 {
        font-size: 1.3rem;
        color: #e0e0e0;
        font-weight: 600;
    }
    .page-btn {
        background: rgba(40,55,75,0.5);
        border: 1px solid rgba(255,255,255,0.1);
        color: #8da0b3;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        font-family: inherit;
    }
    .page-btn:hover {
        background: rgba(255,204,0,0.15);
        color: #ffcc00;
        border-color: #ffcc00;
    }
    .page-btn.active {
        background: #ffcc00;
        color: #0d1520;
        border-color: #ffcc00;
    }
    .msp-content .msp-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .msp-content .msp-table {
        table-layout: fixed;
        width: 100%;
    }
    .msp-content .msp-table th:nth-child(1),
    .msp-content .msp-table td:nth-child(1) { width: 6%; }
    .msp-content .msp-table th:nth-child(2),
    .msp-content .msp-table td:nth-child(2) { width: 18%; }
    .msp-content .msp-table th:nth-child(3),
    .msp-content .msp-table td:nth-child(3) { width: 20%; text-align: left; }
    .msp-content .msp-table th:nth-child(4),
    .msp-content .msp-table td:nth-child(4) { width: 24%; text-align: left; }
    .msp-content .msp-table th:nth-child(5),
    .msp-content .msp-table td:nth-child(5) { width: 16%; text-align: center; }
    .msp-content .msp-table th:nth-child(6),
    .msp-content .msp-table td:nth-child(6) { width: 16%; text-align: center; }

    .msp-content .msp-table th,
    .msp-content .msp-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .msp-content .msp-table th {
        background: rgba(40,55,75,0.6);
        color: #8da0b3;
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255,255,255,0.06);
    }
    .msp-content .msp-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .msp-content .msp-table tr:hover td {
        background: rgba(255,204,0,0.06);
    }
    .msp-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    .msp-content .winnings-positive {
        color: #4ecdc4;
        font-weight: 700;
    }
    .msp-content .winnings-negative {
        color: #aaaaaa;
        font-weight: 700;
    }
    .msp-content .winnings-zero {
        color: #8da0b3;
    }
    .msp-content .msp-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .msp-content .msp-result-badge.win {
        background: rgba(78,205,196,0.25);
        color: #4ecdc4;
    }
    .msp-content .msp-result-badge.lose {
        background: rgba(255,107,107,0.25);
        color: #ff6b6b;
    }
    .msp-content .msp-result-badge.push {
        background: rgba(240,173,78,0.25);
        color: #f0ad4e;
    }
    .msp-content .msp-result-badge.fold {
        background: rgba(170,170,170,0.25);
        color: #aaa;
    }

    /* 模态框样式 */
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.7);
        backdrop-filter: blur(6px);
        z-index: 1000;
        justify-content: center;
        align-items: center;
        padding: 20px;
    }
    .modal-overlay.active {
        display: flex;
    }
    .modal-content {
        background: rgba(20,30,45,0.98);
        border-radius: 24px;
        max-width: 900px;
        width: 100%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0,0,0,0.8);
        border: 1px solid rgba(255,255,255,0.08);
        animation: modalFade 0.3s ease;
    }
    @keyframes modalFade {
        from { opacity: 0; transform: scale(0.95) translateY(10px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
    }
    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 28px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .modal-header h2 {
        font-size: 1.6rem;
        color: #ffcc00;
        margin: 0;
    }
    .modal-header h2 i {
        margin-right: 12px;
    }
    .modal-close {
        background: none;
        border: none;
        color: #8da0b3;
        font-size: 2.2rem;
        cursor: pointer;
        transition: color 0.2s;
        line-height: 1;
    }
    .modal-close:hover {
        color: #ff6b6b;
    }
    .modal-body {
        padding: 28px;
    }
    .detail-layout {
        display: flex;
        gap: 30px;
        flex-wrap: wrap;
    }
    .detail-left {
        flex: 2;
        min-width: 240px;
    }
    .detail-right {
        flex: 1.5;
        min-width: 200px;
        background: rgba(0,0,0,0.2);
        border-radius: 16px;
        padding: 20px;
        align-self: flex-start;
    }
    .hand-section {
        margin-bottom: 18px;
    }
    .hand-section:last-child {
        margin-bottom: 0;
    }
    .hand-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8da0b3;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .hand-cards {
        font-size: 1.3rem;
        font-weight: 700;
        color: #e0e0e0;
        background: rgba(0,0,0,0.25);
        padding: 10px 16px;
        border-radius: 12px;
        min-height: 44px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        word-break: break-all;
    }
    .hand-cards .card-suit {
        display: inline-block;
    }
    .hand-cards .suit-heart, .hand-cards .suit-diamond {
        color: #ff6b6b;
    }
    .hand-cards .suit-spade, .hand-cards .suit-club {
        color: #ccc;
    }
    .detail-meta-row {
        display: flex;
        gap: 20px;
        margin-bottom: 18px;
        flex-wrap: wrap;
    }
    .detail-meta-row .meta-item {
        flex: 1;
        min-width: 80px;
    }
    .meta-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .meta-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
    }
    .meta-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffcc00;
        background: rgba(0,0,0,0.2);
        padding: 6px 12px;
        border-radius: 8px;
        display: inline-block;
    }
    .deck-section {
        margin-top: 6px;
    }
    .deck-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .deck-cards {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        padding: 8px 6px;
        background: rgba(0,0,0,0.15);
        border-radius: 10px;
        align-content: flex-start;
        max-height: none;
        overflow-y: visible;
    }
    .deck-cards::-webkit-scrollbar {
        display: none;
    }
    .deck-card {
        width: 36px;
        height: 22px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(40,55,75,0.6);
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        font-family: 'Segoe UI', monospace;
        border: 1px solid rgba(255,255,255,0.06);
        transition: all 0.15s;
        box-sizing: border-box;
        flex-shrink: 0;
    }
    .deck-card.color-green {
        background: #007900;
        color: #ffffff;
        border-color: #00ff00;
        text-shadow: none;
    }
    .deck-card.color-red {
        background: #ff0000;
        color: #ffffff;
        border-color: #ff0000;
        text-shadow: none;
    }
    .deck-card .suit-heart,
    .deck-card .suit-diamond {
        color: inherit;
    }
    .deck-card .suit-spade,
    .deck-card .suit-club {
        color: inherit;
    }
    .footer-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
    }
    .footer-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
    }
    .footer-value .highlight-win {
        color: #4ecdc4;
    }
    .footer-value .highlight-lose {
        color: #ff6b6b;
    }
    .footer-value .highlight-push {
        color: #f0ad4e;
    }
    .footer-value .highlight-fold {
        color: #aaa;
    }

    @media (max-width: 768px) {
        .msp-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .msp-content .stats-grid-result {
            grid-template-columns: repeat(3, 1fr);
        }
        .msp-content .stats-grid-3 {
            grid-template-columns: repeat(2, 1fr);
        }
        .msp-content .detail-layout {
            flex-direction: column;
        }
        .msp-content .detail-right {
            width: 100%;
        }
        .msp-content .msp-table {
            font-size: 0.78rem;
        }
        .msp-content .msp-table th,
        .msp-content .msp-table td {
            padding: 6px 6px;
        }
        .modal-content {
            max-width: 100%;
            margin: 10px;
        }
        .modal-body {
            padding: 20px;
        }
        .hand-cards {
            font-size: 1.1rem;
            padding: 10px 12px;
        }
        .detail-meta-row {
            flex-direction: row;
        }
        .deck-card {
            width: 28px;
            height: 36px;
            font-size: 0.65rem;
        }
        .deck-cards {
            gap: 3px;
            padding: 6px 4px;
        }
        .page-btn {
            font-size: 0.75rem;
            padding: 4px 10px;
        }
    }
    @media (max-width: 480px) {
        .msp-content .stats-grid-3 {
            grid-template-columns: 1fr 1fr;
        }
        .msp-content .stats-grid-result {
            grid-template-columns: repeat(2, 1fr);
        }
        .detail-meta-row {
            flex-direction: column;
        }
        .deck-card {
            width: 24px;
            height: 32px;
            font-size: 0.55rem;
        }
        .deck-cards {
            gap: 2px;
            padding: 4px 3px;
        }
    }
</style>

<script>
    (function() {
        const MSP_URL = './Json/Mississippi_Stud_Poker.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        // 牌型名称映射（用于统计）
        const HAND_NAMES = {
            'royal_flush': '皇家同花顺',
            'straight_flush': '同花顺',
            'four_of_a_kind': '四条',
            'full_house': '葫芦',
            'flush': '同花',
            'straight': '顺子',
            'three_of_a_kind': '三条',
            'two_pair': '两对',
            'pair_jack_or_better': '一对J或更好',
            'pair_6_10': '一对6-10',
            'high_card': '高牌'
        };

        function parseCard(cardStr) {
            if (!cardStr) return '?';
            return cardStr;
        }

        function formatCards(arr, asHtml = false) {
            if (!arr || !Array.isArray(arr)) return '—';
            if (!asHtml) {
                return arr.map(c => parseCard(c)).join(' ');
            }
            return arr.map(c => {
                let card = parseCard(c);
                let suitClass = '';
                if (card.includes('♥')) suitClass = 'suit-heart';
                else if (card.includes('♦')) suitClass = 'suit-diamond';
                else if (card.includes('♠')) suitClass = 'suit-spade';
                else if (card.includes('♣')) suitClass = 'suit-club';
                return `<span class="card-suit ${suitClass}">${card}</span>`;
            }).join(' ');
        }

        function getResultBadge(result) {
            const map = {
                'Win': '<span class="msp-result-badge win">赢</span>',
                'Lose': '<span class="msp-result-badge lose">输</span>',
                'Push': '<span class="msp-result-badge push">平</span>',
                'Fold': '<span class="msp-result-badge fold">弃</span>'
            };
            return map[result] || result;
        }

        function formatWinnings(winAmount, result) {
            if (result === 'Win' && winAmount > 0) {
                return `<span class="winnings-positive">+$${winAmount}</span>`;
            } else if (result === 'Push' && winAmount > 0) {
                return `<span class="winnings-positive">+$${winAmount}</span>`;
            } else {
                return `<span class="winnings-negative">$0</span>`;
            }
        }

        function renderStats(historyRecord) {
            if (!historyRecord) return;
            const total = historyRecord.game || 0;
            const wins = historyRecord.win || 0;
            const losses = historyRecord.lose || 0;
            const pushes = historyRecord.push || 0;
            const folds = historyRecord.fold || 0;
            const winRate = total > 0 ? (wins / total * 100) : 0;

            document.getElementById('msp-total').textContent = total;
            document.getElementById('msp-winrate').textContent = winRate.toFixed(1) + '%';
            document.getElementById('msp-wins').textContent = wins;
            document.getElementById('msp-losses').textContent = losses;
            document.getElementById('msp-pushes').textContent = pushes;
            document.getElementById('msp-folds').textContent = folds;

            // 生成牌型统计
            const grid = document.getElementById('msp-result-grid');
            grid.innerHTML = '';
            for (const [key, label] of Object.entries(HAND_NAMES)) {
                const count = historyRecord[key] || 0;
                const pct = total > 0 ? (count / total * 100) : 0;
                const div = document.createElement('div');
                div.className = 'stat-item';
                div.innerHTML = `
                    <div class="stat-value" style="font-size:1.6rem;">${count}</div>
                    <div class="stat-label">${label}</div>
                    <div class="stat-sub">${pct.toFixed(1)}%</div>
                `;
                grid.appendChild(div);
            }
        }

        function renderTable() {
            const tbody = document.getElementById('msp-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
                return;
            }

            let displayRecords = [];
            if (currentView === 'latest') {
                const total = allRecords.length;
                const take = Math.min(PAGE_SIZE, total);
                const sliceStart = total - take;
                displayRecords = allRecords.slice(sliceStart).reverse();
            } else {
                const take = Math.min(PAGE_SIZE, allRecords.length);
                displayRecords = allRecords.slice(0, take);
            }

            let html = '';
            for (const game of displayRecords) {
                const realIndex = allRecords.indexOf(game);
                const result = game.result || '—';
                const winAmount = game.win_amount || 0;
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                const playerCards = formatCards(game.player_cards);
                const commCards = formatCards(game.comm_cards);
                const badge = getResultBadge(result);
                const winHtml = formatWinnings(winAmount, result);
                html += `<tr data-index="${realIndex}">
                    <td>${game.game_id || '—'}</td>
                    <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                    <td class="cards-mini">${playerCards}</td>
                    <td class="cards-mini">${commCards}</td>
                    <td>${badge}</td>
                    <td>${winHtml}</td>
                </tr>`;
            }

            tbody.innerHTML = html;

            document.querySelectorAll('#msp-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openDetailModal(allRecords[idx], idx);
                    }
                });
            });
        }

        async function loadData() {
            try {
                const resp = await fetch(MSP_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                if (!data.history || !Array.isArray(data.history)) {
                    throw new Error('数据格式错误：缺少 history 数组');
                }
                allRecords = data.history;

                if (data.history_record) {
                    renderStats(data.history_record);
                }

                renderTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('MSP load error:', err);
                document.getElementById('msp-history-body').innerHTML =
                    `<tr><td colspan="6" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        function openDetailModal(game, index) {
            document.getElementById('msp-detail-player').innerHTML = formatCards(game.player_cards, true) || '—';
            document.getElementById('msp-detail-comm').innerHTML = formatCards(game.comm_cards, true) || '—';
            document.getElementById('msp-detail-time').textContent = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';

            const result = game.result || '—';
            const winAmount = game.win_amount || 0;
            let resultHtml = '';
            if (result === 'Win') {
                resultHtml = `<span class="highlight-win">赢 ($${winAmount})</span>`;
            } else if (result === 'Push') {
                resultHtml = `<span class="highlight-push">平 ($${winAmount})</span>`;
            } else if (result === 'Lose') {
                resultHtml = `<span class="highlight-lose">输</span>`;
            } else if (result === 'Fold') {
                resultHtml = `<span class="highlight-fold">弃牌</span>`;
            } else {
                resultHtml = result;
            }
            document.getElementById('msp-detail-result').innerHTML = resultHtml;

            document.getElementById('msp-detail-index').textContent = (index + 1);
            document.getElementById('msp-detail-cut').textContent = game.cut_position ?? '—';

            const deckContainer = document.getElementById('msp-detail-deck');
            deckContainer.innerHTML = '';
            if (game.deck_order && Array.isArray(game.deck_order)) {
                const cutPos = game.cut_position;
                const total = game.deck_order.length;

                game.deck_order.forEach((card, idx) => {
                    const span = document.createElement('span');
                    span.className = 'deck-card';
                    let offset = (idx - cutPos + total) % total;
                    // 切牌后的前5张为实际使用的牌（2底牌+3公共牌）
                    if (offset >= 0 && offset <= 1) {
                        span.classList.add('color-green');
                    } else if (offset >= 2 && offset <= 4) {
                        span.classList.add('color-red');
                    }
                    let suitClass = '';
                    if (card.includes('♥')) suitClass = 'suit-heart';
                    else if (card.includes('♦')) suitClass = 'suit-diamond';
                    else if (card.includes('♠')) suitClass = 'suit-spade';
                    else if (card.includes('♣')) suitClass = 'suit-club';
                    span.innerHTML = `<span class="${suitClass}">${card}</span>`;
                    deckContainer.appendChild(span);
                });
            } else {
                deckContainer.innerHTML = '<span style="color:#6a7f94;">无牌堆数据</span>';
            }

            document.getElementById('mspDetailModal').classList.add('active');
        }

        function closeDetailModal() {
            document.getElementById('mspDetailModal').classList.remove('active');
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadData();

            document.getElementById('mspPageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('mspPageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('mspModalCloseBtn').addEventListener('click', closeDetailModal);
            document.getElementById('mspDetailModal').addEventListener('click', function(e) {
                if (e.target === this) closeDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeDetailModal();
            });

            setInterval(loadData, 1000);
        });
    })();
</script>