<!-- Casino_War.php - 完整页面内容（不含顶部/底部） -->
<div class="cw-content">
    <!-- 对局总览 + 战争结果 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>对局总览</h2>
            </div>
            <div class="stats-grid-4">
                <div class="stat-item">
                    <div class="stat-value" id="cw-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="cw-player-wins">0</div>
                    <div class="stat-label">玩家胜</div>
                    <div class="stat-sub" id="cw-player-winrate">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="cw-dealer-wins">0</div>
                    <div class="stat-label">庄家胜</div>
                    <div class="stat-sub" id="cw-dealer-winrate">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ffd700;" id="cw-war-total">0</div>
                    <div class="stat-label">战争次数</div>
                    <div class="stat-sub" id="cw-war-total-pct">0%</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <i class="fas fa-swords"></i>
                <h2>战争结果</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item">
                    <div class="stat-value green" id="cw-war-success">0</div>
                    <div class="stat-label">战争成功</div>
                    <div class="stat-sub" id="cw-war-success-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="cw-war-fail">0</div>
                    <div class="stat-label">战争失败</div>
                    <div class="stat-sub" id="cw-war-fail-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#aaa;" id="cw-war-push">0</div>
                    <div class="stat-label">战争平局</div>
                    <div class="stat-sub" id="cw-war-push-pct">0%</div>
                </div>
            </div>
        </div>
    </div>

    <!-- 对局记录 -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-list-ul"></i>
            <h2>对局记录</h2>
            <div style="margin-left:auto;display:flex;gap:10px;">
                <button class="page-btn active" data-page="latest" id="cwPageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="cwPageOldest">最旧25局</button>
            </div>
        </div>
        <div class="cw-table-wrap">
            <table class="cw-table" id="cw-history-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>时间</th>
                        <th>玩家牌</th>
                        <th>庄家牌</th>
                        <th>结果</th>
                    </tr>
                </thead>
                <tbody id="cw-history-body">
                    <tr><td colspan="5" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 模态框 -->
    <div class="modal-overlay" id="cwDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> 对局详情</h2>
                <button class="modal-close" id="cwModalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">庄家手牌</div>
                            <div class="hand-cards" id="cw-detail-dealer">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">玩家手牌</div>
                            <div class="hand-cards" id="cw-detail-player">—</div>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">时间</span>
                            <span class="footer-value" id="cw-detail-time">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">结果</span>
                            <span class="footer-value" id="cw-detail-result">—</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .cw-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .cw-content .stats-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }
    .cw-content .stats-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .cw-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .cw-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .cw-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .cw-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .cw-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
    }
    .cw-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .cw-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .cw-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .cw-content .card:hover {
        transform: translateY(-3px);
    }
    .cw-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .cw-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .cw-content .card-header h2 {
        font-size: 1.5rem;
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
    .cw-content .cw-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .cw-content .cw-table {
        table-layout: fixed;
        width: 100%;
    }
    .cw-content .cw-table th:nth-child(1),
    .cw-content .cw-table td:nth-child(1) { width: 8%; }
    .cw-content .cw-table th:nth-child(2),
    .cw-content .cw-table td:nth-child(2) { width: 20%; }
    .cw-content .cw-table th:nth-child(3),
    .cw-content .cw-table td:nth-child(3) { width: 24%; text-align: left; }
    .cw-content .cw-table th:nth-child(4),
    .cw-content .cw-table td:nth-child(4) { width: 24%; text-align: left; }
    .cw-content .cw-table th:nth-child(5),
    .cw-content .cw-table td:nth-child(5) { width: 24%; text-align: center; }

    .cw-content .cw-table th,
    .cw-content .cw-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .cw-content .cw-table th {
        background: rgba(40,55,75,0.6);
        color: #8da0b3;
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255,255,255,0.06);
    }
    .cw-content .cw-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .cw-content .cw-table tr:hover td {
        background: rgba(255,204,0,0.06);
    }
    .cw-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    .cw-content .cw-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .cw-content .cw-result-badge.win {
        background: rgba(78,205,196,0.25);
        color: #4ecdc4;
    }
    .cw-content .cw-result-badge.lose {
        background: rgba(255,107,107,0.25);
        color: #ff6b6b;
    }
    .cw-content .cw-result-badge.push {
        background: rgba(255,215,0,0.2);
        color: #ffd700;
    }
    .cw-content .cw-result-badge.surrender {
        background: rgba(255,165,0,0.25);
        color: #ffa500;
    }

    /* 模态框通用样式 */
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
        max-width: 600px;
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
        flex-direction: column;
        gap: 20px;
    }
    .hand-section {
        margin-bottom: 16px;
    }
    .hand-section:last-child {
        margin-bottom: 0;
    }
    .hand-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8da0b3;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .hand-cards {
        font-size: 1.4rem;
        font-weight: 700;
        color: #e0e0e0;
        background: rgba(0,0,0,0.25);
        padding: 12px 16px;
        border-radius: 12px;
        min-height: 50px;
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
        color: #ffd700;
    }
    .footer-value .highlight-surrender {
        color: #ffa500;
    }

    @media (max-width: 768px) {
        .cw-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .cw-content .stats-grid-4 {
            grid-template-columns: repeat(2, 1fr);
        }
        .cw-content .stats-grid-3 {
            grid-template-columns: repeat(2, 1fr);
        }
        .cw-content .cw-table {
            font-size: 0.78rem;
        }
        .cw-content .cw-table th,
        .cw-content .cw-table td {
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
        .page-btn {
            font-size: 0.75rem;
            padding: 4px 10px;
        }
    }
    @media (max-width: 480px) {
        .cw-content .stats-grid-4 {
            grid-template-columns: 1fr 1fr;
        }
        .cw-content .stats-grid-3 {
            grid-template-columns: 1fr;
        }
    }
</style>

<script>
    (function() {
        const CW_URL = './Json/Casino_War.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        // 判断是否发生战争（war_cards中有任何一个非null）
        function hasWar(game) {
            if (!game.war_cards) return false;
            return (game.war_cards.player_war_card !== null && game.war_cards.player_war_card !== undefined) ||
                   (game.war_cards.dealer_war_card !== null && game.war_cards.dealer_war_card !== undefined);
        }

        // 格式化牌面，如果是战争则附加战争牌
        function formatCardWithWar(mainCard, warCard, asHtml = false) {
            if (!mainCard) return '—';
            let display = mainCard;
            if (warCard && warCard !== null) {
                display = mainCard + ' (' + warCard + ')';
            }
            if (!asHtml) return display;
            // HTML 高亮花色
            let parts = display.split(' ');
            let html = '';
            for (let p of parts) {
                let suitClass = '';
                if (p.includes('♥')) suitClass = 'suit-heart';
                else if (p.includes('♦')) suitClass = 'suit-diamond';
                else if (p.includes('♠')) suitClass = 'suit-spade';
                else if (p.includes('♣')) suitClass = 'suit-club';
                if (suitClass) {
                    html += `<span class="card-suit ${suitClass}">${p}</span> `;
                } else {
                    html += p + ' ';
                }
            }
            return html.trim();
        }

        function getResultText(game) {
            // 优先投降
            if (game.result && game.result.surrender === true) {
                return { text: '！投降！', cls: 'surrender' };
            }
            const winner = game.result?.winner || '';
            const isWar = hasWar(game);
            let text, cls;
            if (winner === 'player') {
                text = isWar ? '战争后玩家赢' : '玩家赢';
                cls = 'win';
            } else if (winner === 'dealer') {
                text = isWar ? '战争后庄赢' : '庄家赢';
                cls = 'lose';
            } else if (winner === 'war_push') {
                text = isWar ? '战争后平局' : '平局';
                cls = 'push';
            } else {
                text = '—';
                cls = '';
            }
            return { text, cls };
        }

        function renderCwTable() {
            const tbody = document.getElementById('cw-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
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
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                const playerCard = game.player_card || '—';
                const dealerCard = game.dealer_card || '—';
                const playerWar = game.war_cards?.player_war_card || null;
                const dealerWar = game.war_cards?.dealer_war_card || null;
                const playerDisplay = formatCardWithWar(playerCard, playerWar, false);
                const dealerDisplay = formatCardWithWar(dealerCard, dealerWar, false);
                const resultInfo = getResultText(game);
                const badge = `<span class="cw-result-badge ${resultInfo.cls}">${resultInfo.text}</span>`;
                html += `<tr data-index="${realIndex}">
                    <td>${game.game_id || '—'}</td>
                    <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                    <td class="cards-mini">${playerDisplay}</td>
                    <td class="cards-mini">${dealerDisplay}</td>
                    <td>${badge}</td>
                </tr>`;
            }

            tbody.innerHTML = html;

            document.querySelectorAll('#cw-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openCwDetailModal(allRecords[idx], idx);
                    }
                });
            });
        }

        function updateStats(historyRecord) {
            if (!historyRecord) return;
            const total = historyRecord.game || 0;
            const playerWins = historyRecord.player_win || 0;
            const dealerWins = historyRecord.dealer_win || 0;
            const warTotal = historyRecord.war || 0;
            const warSuccess = historyRecord.war_success || 0;
            const warFail = historyRecord.war_fail || 0;
            const warPush = historyRecord.war_push || 0;

            const playerRate = total > 0 ? (playerWins / total * 100) : 0;
            const dealerRate = total > 0 ? (dealerWins / total * 100) : 0;
            const warTotalRate = total > 0 ? (warTotal / total * 100) : 0;
            const warSuccessRate = warTotal > 0 ? (warSuccess / warTotal * 100) : 0;
            const warFailRate = warTotal > 0 ? (warFail / warTotal * 100) : 0;
            const warPushRate = warTotal > 0 ? (warPush / warTotal * 100) : 0;

            document.getElementById('cw-total').textContent = total;
            document.getElementById('cw-player-wins').textContent = playerWins;
            document.getElementById('cw-dealer-wins').textContent = dealerWins;
            document.getElementById('cw-player-winrate').textContent = playerRate.toFixed(1) + '%';
            document.getElementById('cw-dealer-winrate').textContent = dealerRate.toFixed(1) + '%';

            document.getElementById('cw-war-total').textContent = warTotal;
            document.getElementById('cw-war-total-pct').textContent = warTotalRate.toFixed(1) + '%';
            document.getElementById('cw-war-success').textContent = warSuccess;
            document.getElementById('cw-war-success-pct').textContent = warSuccessRate.toFixed(1) + '%';
            document.getElementById('cw-war-fail').textContent = warFail;
            document.getElementById('cw-war-fail-pct').textContent = warFailRate.toFixed(1) + '%';
            document.getElementById('cw-war-push').textContent = warPush;
            document.getElementById('cw-war-push-pct').textContent = warPushRate.toFixed(1) + '%';
        }

        async function loadCw() {
            try {
                const resp = await fetch(CW_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                if (!data.history || !Array.isArray(data.history)) {
                    throw new Error('数据格式错误：缺少 history 数组');
                }
                allRecords = data.history;

                if (data.history_record) {
                    updateStats(data.history_record);
                }

                renderCwTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('CW load error:', err);
                document.getElementById('cw-history-body').innerHTML =
                    `<tr><td colspan="5" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        function openCwDetailModal(game, index) {
            const playerCard = game.player_card || '—';
            const dealerCard = game.dealer_card || '—';
            const playerWar = game.war_cards?.player_war_card || null;
            const dealerWar = game.war_cards?.dealer_war_card || null;

            document.getElementById('cw-detail-dealer').innerHTML = formatCardWithWar(dealerCard, dealerWar, true) || '—';
            document.getElementById('cw-detail-player').innerHTML = formatCardWithWar(playerCard, playerWar, true) || '—';

            const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
            document.getElementById('cw-detail-time').textContent = time;

            const resultInfo = getResultText(game);
            let resultHtml = '';
            if (resultInfo.cls === 'win') resultHtml = `<span class="highlight-win">${resultInfo.text}</span>`;
            else if (resultInfo.cls === 'lose') resultHtml = `<span class="highlight-lose">${resultInfo.text}</span>`;
            else if (resultInfo.cls === 'push') resultHtml = `<span class="highlight-push">${resultInfo.text}</span>`;
            else if (resultInfo.cls === 'surrender') resultHtml = `<span class="highlight-surrender">${resultInfo.text}</span>`;
            else resultHtml = resultInfo.text;
            document.getElementById('cw-detail-result').innerHTML = resultHtml;

            document.getElementById('cwDetailModal').classList.add('active');
        }

        function closeCwDetailModal() {
            document.getElementById('cwDetailModal').classList.remove('active');
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadCw();

            document.getElementById('cwPageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderCwTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('cwPageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderCwTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('cwModalCloseBtn').addEventListener('click', closeCwDetailModal);
            document.getElementById('cwDetailModal').addEventListener('click', function(e) {
                if (e.target === this) closeCwDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeCwDetailModal();
            });

            setInterval(loadCw, 1000);
        });
    })();
</script>