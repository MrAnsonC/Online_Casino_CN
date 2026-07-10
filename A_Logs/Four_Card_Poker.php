<!-- 四张牌扑克内容页（不含顶部/底部） -->
<div class="fcp-content">
    <!-- 对局总览 + 结果分布 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>对局总览</h2>
            </div>
            <div class="stats-grid-2">
                <div class="stat-item">
                    <div class="stat-value" id="fcp-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="fcp-winrate">0%</div>
                    <div class="stat-label">玩家胜率</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <i class="fas fa-flag-checkered"></i>
                <h2>结果分布</h2>
            </div>
            <div class="stats-grid-4">
                <div class="stat-item">
                    <div class="stat-value green" id="fcp-player-wins">0</div>
                    <div class="stat-label">玩家胜</div>
                    <div class="stat-sub" id="fcp-player-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="fcp-dealer-wins">0</div>
                    <div class="stat-label">庄家胜</div>
                    <div class="stat-sub" id="fcp-dealer-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ffd700;" id="fcp-pushes">0</div>
                    <div class="stat-label">平局</div>
                    <div class="stat-sub" id="fcp-push-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#aaa;" id="fcp-folds">0</div>
                    <div class="stat-label">弃牌</div>
                    <div class="stat-sub" id="fcp-fold-pct">0%</div>
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
                <button class="page-btn active" data-page="latest" id="fcpPageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="fcpPageOldest">最旧25局</button>
            </div>
        </div>
        <div class="fcp-table-wrap">
            <table class="fcp-table" id="fcp-history-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>时间</th>
                        <th>模式</th>
                        <th class="align-right">玩家牌</th>
                        <th>庄家牌</th>
                        <th>结果</th>
                        <th>赢钱</th>
                    </tr>
                </thead>
                <tbody id="fcp-history-body">
                    <tr><td colspan="7" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 模态框 -->
    <div class="modal-overlay" id="fcpDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> 对局详情</h2>
                <button class="modal-close" id="fcpModalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">庄家手牌</div>
                            <div class="hand-cards" id="fcp-detail-dealer">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">玩家手牌</div>
                            <div class="hand-cards" id="fcp-detail-player">—</div>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">时间</span>
                            <span class="footer-value" id="fcp-detail-time">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">模式</span>
                            <span class="footer-value" id="fcp-detail-mode">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">结果</span>
                            <span class="footer-value" id="fcp-detail-result">—</span>
                        </div>
                    </div>
                    <div class="detail-right">
                        <div class="detail-meta-row">
                            <div class="meta-item">
                                <span class="meta-label">局号</span>
                                <span class="meta-value" id="fcp-detail-index">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">切牌位置</span>
                                <span class="meta-value" id="fcp-detail-cut">—</span>
                            </div>
                        </div>
                        <div class="deck-section">
                            <div class="deck-label">牌堆顺序 (52张)</div>
                            <div class="deck-cards" id="fcp-detail-deck"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .fcp-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .fcp-content .stats-grid-2 {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
    }
    .fcp-content .stats-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .fcp-content .stat-item {
        background: rgba(40, 55, 75, 0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .fcp-content .stat-item:hover {
        background: rgba(50, 70, 95, 0.7);
        transform: scale(1.02);
    }
    .fcp-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255, 204, 0, 0.25);
        line-height: 1.2;
    }
    .fcp-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78, 205, 196, 0.25);
    }
    .fcp-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255, 107, 107, 0.25);
    }
    .fcp-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .fcp-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .fcp-content .card {
        background: rgba(25, 35, 50, 0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        transition: transform 0.25s ease;
    }
    .fcp-content .card:hover {
        transform: translateY(-3px);
    }
    .fcp-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .fcp-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .fcp-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }
    .page-btn {
        background: rgba(40, 55, 75, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
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
        background: rgba(255, 204, 0, 0.15);
        color: #ffcc00;
        border-color: #ffcc00;
    }
    .page-btn.active {
        background: #ffcc00;
        color: #0d1520;
        border-color: #ffcc00;
    }
    .fcp-content .fcp-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .fcp-content .fcp-table {
        table-layout: fixed;
        width: 100%;
    }
    .fcp-content .fcp-table th:nth-child(1),
    .fcp-content .fcp-table td:nth-child(1) {
        width: 5%;
    }
    .fcp-content .fcp-table th:nth-child(2),
    .fcp-content .fcp-table td:nth-child(2) {
        width: 15%;
    }
    .fcp-content .fcp-table th:nth-child(3),
    .fcp-content .fcp-table td:nth-child(3) {
        width: 8%;
        text-align: center;
    }
    .fcp-content .fcp-table th:nth-child(4),
    .fcp-content .fcp-table td:nth-child(4) {
        width: 22%;
        text-align: right;  /* 玩家牌列靠右 */
    }
    .fcp-content .fcp-table th:nth-child(5),
    .fcp-content .fcp-table td:nth-child(5) {
        width: 22%;
        text-align: left;   /* 庄家牌列靠左 */
    }
    .fcp-content .fcp-table th:nth-child(6),
    .fcp-content .fcp-table td:nth-child(6) {
        width: 12%;
        text-align: center;
    }
    .fcp-content .fcp-table th:nth-child(7),
    .fcp-content .fcp-table td:nth-child(7) {
        width: 16%;
        text-align: center;
    }

    .fcp-content .fcp-table th,
    .fcp-content .fcp-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .fcp-content .fcp-table th {
        background: rgba(40, 55, 75, 0.6);
        color: #8da0b3;
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255, 255, 255, 0.06);
    }
    .fcp-content .fcp-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .fcp-content .fcp-table tr:hover td {
        background: rgba(255, 204, 0, 0.06);
    }
    .fcp-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    .fcp-content .cards-mini .brace-card {
        color: #ffcc00;
        font-weight: 700;
    }
    .fcp-content .winnings-positive {
        color: #4ecdc4;
        font-weight: 700;
    }
    .fcp-content .winnings-negative {
        color: #ff6b6b;
        font-weight: 700;
    }
    .fcp-content .winnings-zero {
        color: #8da0b3;
    }
    .fcp-content .fcp-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .fcp-content .fcp-result-badge.win {
        background: rgba(78, 205, 196, 0.25);
        color: #4ecdc4;
    }
    .fcp-content .fcp-result-badge.lose {
        background: rgba(255, 107, 107, 0.25);
        color: #ff6b6b;
    }
    .fcp-content .fcp-result-badge.push {
        background: rgba(255, 215, 0, 0.2);
        color: #ffd700;
    }
    .fcp-content .fcp-result-badge.fold {
        background: rgba(150, 150, 150, 0.2);
        color: #aaa;
    }
    .fcp-content .mode-badge {
        display: inline-block;
        padding: 0px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        background: rgba(255, 204, 0, 0.15);
        color: #ffcc00;
        border: 1px solid rgba(255, 204, 0, 0.2);
    }
    .fcp-content .mode-badge.crazy {
        background: rgba(255, 107, 107, 0.2);
        color: #ff6b6b;
        border-color: rgba(255, 107, 107, 0.25);
    }

    /* 模态框通用样式 */
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
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
        background: rgba(20, 30, 45, 0.98);
        border-radius: 24px;
        max-width: 920px;
        width: 100%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
        animation: modalFade 0.3s ease;
    }
    @keyframes modalFade {
        from {
            opacity: 0;
            transform: scale(0.95) translateY(10px);
        }
        to {
            opacity: 1;
            transform: scale(1) translateY(0);
        }
    }
    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 28px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
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
        background: rgba(0, 0, 0, 0.2);
        border-radius: 16px;
        padding: 20px;
        align-self: flex-start;
    }
    .hand-section {
        margin-bottom: 20px;
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
        background: rgba(0, 0, 0, 0.25);
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
    .hand-cards .suit-heart,
    .hand-cards .suit-diamond {
        color: #ff6b6b;
    }
    .hand-cards .suit-spade,
    .hand-cards .suit-club {
        color: #ccc;
    }
    .hand-cards .brace-card {
        color: #ffcc00;
        font-weight: 700;
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
        background: rgba(0, 0, 0, 0.2);
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
        background: rgba(0, 0, 0, 0.15);
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
        background: rgba(40, 55, 75, 0.6);
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        font-family: 'Segoe UI', monospace;
        border: 1px solid rgba(255, 255, 255, 0.06);
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
        background: #aa0000;
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
        color: #ffd700;
    }
    .footer-value .mode-tag {
        display: inline-block;
        padding: 0px 14px;
        border-radius: 14px;
        font-size: 0.85rem;
        font-weight: 600;
        background: rgba(255, 204, 0, 0.15);
        color: #ffcc00;
        border: 1px solid rgba(255, 204, 0, 0.2);
    }
    .footer-value .mode-tag.crazy {
        background: rgba(255, 107, 107, 0.2);
        color: #ff6b6b;
        border-color: rgba(255, 107, 107, 0.25);
    }

    @media (max-width: 768px) {
        .fcp-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .fcp-content .stats-grid-4 {
            grid-template-columns: repeat(2, 1fr);
        }
        .fcp-content .detail-layout {
            flex-direction: column;
        }
        .fcp-content .detail-right {
            width: 100%;
        }
        .fcp-content .fcp-table {
            font-size: 0.78rem;
        }
        .fcp-content .fcp-table th,
        .fcp-content .fcp-table td {
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
            height: 18px;
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
        .fcp-content .stats-grid-4 {
            grid-template-columns: 1fr 1fr;
        }
        .fcp-content .stats-grid-2 {
            grid-template-columns: 1fr;
        }
        .detail-meta-row {
            flex-direction: column;
        }
        .deck-card {
            width: 24px;
            height: 16px;
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
        const FCP_URL = './Json/Four_Card_Poker.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        function parseCard(cardStr) {
            if (!cardStr) return '?';
            return cardStr;
        }

        /**
         * 格式化手牌，根据牌数自动添加花括号
         * @param {Array} arr         牌数组
         * @param {string} type       'player' 或 'dealer'
         * @param {boolean} asHtml    是否返回 HTML
         * @returns {string}
         */
        function formatCardsWithBrace(arr, type, asHtml = false) {
            if (!arr || !Array.isArray(arr) || arr.length === 0) return '—';

            const total = arr.length;
            let normalCount = 0;
            let braceStart = 0;

            if (type === 'player') {
                // 玩家：5张牌，前4张正常，第5张花括号
                normalCount = 4;
                braceStart = 4;
            } else { // dealer
                if (total === 5) {
                    // 5张：前4张正常，第5张花括号
                    normalCount = 4;
                    braceStart = 4;
                } else if (total === 6) {
                    // 6张：前4张正常，第5、6张花括号
                    normalCount = 4;
                    braceStart = 4;
                } else {
                    // fallback：全部正常显示
                    normalCount = total;
                    braceStart = total;
                }
            }

            const result = [];
            for (let i = 0; i < total; i++) {
                const card = parseCard(arr[i]);
                const inBrace = (i >= braceStart);
                let display = card;

                if (asHtml) {
                    let suitClass = '';
                    if (card.includes('♥')) suitClass = 'suit-heart';
                    else if (card.includes('♦')) suitClass = 'suit-diamond';
                    else if (card.includes('♠')) suitClass = 'suit-spade';
                    else if (card.includes('♣')) suitClass = 'suit-club';

                    if (inBrace) {
                        display = `<span class="card-suit ${suitClass} brace-card">${card}</span>`;
                    } else {
                        display = `<span class="card-suit ${suitClass}">${card}</span>`;
                    }
                } else {
                    if (inBrace) {
                        display = card;
                    } else {
                        display = card;
                    }
                }
                result.push({ card: display, inBrace: inBrace });
            }

            if (!asHtml) {
                // 纯文本：拼接，花括号内的用花括号包围
                const parts = [];
                let braceParts = [];
                let inBrace = false;
                for (let i = 0; i < result.length; i++) {
                    const item = result[i];
                    if (item.inBrace && !inBrace) {
                        inBrace = true;
                        braceParts = [];
                        braceParts.push(item.card);
                    } else if (item.inBrace && inBrace) {
                        braceParts.push(item.card);
                    } else if (!item.inBrace && inBrace) {
                        inBrace = false;
                        parts.push('{' + braceParts.join(' ') + '}');
                        parts.push(item.card);
                    } else {
                        parts.push(item.card);
                    }
                }
                if (inBrace) {
                    parts.push('{' + braceParts.join(' ') + '}');
                }
                return parts.join(' ');
            } else {
                // HTML
                const parts = [];
                let braceParts = [];
                let inBrace = false;
                for (let i = 0; i < result.length; i++) {
                    const item = result[i];
                    if (item.inBrace && !inBrace) {
                        inBrace = true;
                        braceParts = [];
                        braceParts.push(item.card);
                    } else if (item.inBrace && inBrace) {
                        braceParts.push(item.card);
                    } else if (!item.inBrace && inBrace) {
                        inBrace = false;
                        parts.push('<span class="brace-card">{</span>' + braceParts.join(' ') +
                            '<span class="brace-card">}</span>');
                        parts.push(item.card);
                    } else {
                        parts.push(item.card);
                    }
                }
                if (inBrace) {
                    parts.push('<span class="brace-card">{</span>' + braceParts.join(' ') +
                    '<span class="brace-card">}</span>');
                }
                return parts.join(' ');
            }
        }

        function formatWinnings(val) {
            if (val === undefined || val === null) return '—';
            const num = Number(val);
            if (num === 0) return '<span class="winnings-zero">$0</span>';
            if (num > 0) return `<span class="winnings-positive">+$${num.toFixed(0)}</span>`;
            return `<span class="winnings-negative">-$${Math.abs(num).toFixed(0)}</span>`;
        }

        function getResultBadge(winner, isFold) {
            if (winner === 'fold') return '<span class="fcp-result-badge fold">弃牌</span>';
            if (winner === 'player') return '<span class="fcp-result-badge win">玩家胜</span>';
            if (winner === 'dealer') return '<span class="fcp-result-badge lose">庄家胜</span>';
            if (winner === 'push') return '<span class="fcp-result-badge push">平局</span>';
            return '<span class="fcp-result-badge fold">—</span>';
        }

        // 修改：模式显示中文
        function getModeBadge(mode) {
            if (mode === 'crazy') {
                return '<span class="mode-badge crazy">疯狂</span>';
            }
            return '<span class="mode-badge">基本</span>';
        }

        function renderFcpTable() {
            const tbody = document.getElementById('fcp-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML =
                    '<tr><td colspan="7" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
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
                const isFold = game.fold === true;
                const winner = game.result?.winner || '';
                const winnings = game.result?.winnings ?? 0;
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                const mode = game.game_mode || 'basic';

                const playerCards = formatCardsWithBrace(game.player_cards, 'player', false);
                const dealerCards = formatCardsWithBrace(game.dealer_cards, 'dealer', false);
                const badge = getResultBadge(winner, isFold);
                const winHtml = formatWinnings(winnings);
                const modeBadge = getModeBadge(mode);

                html += `<tr data-index="${realIndex}">
                        <td>${game.game_id || '—'}</td>
                        <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                        <td>${modeBadge}</td>
                        <td class="cards-mini" style="text-align:right;">${playerCards}</td>
                        <td class="cards-mini">${dealerCards}</td>
                        <td>${badge}</td>
                        <td>${winHtml}</td>
                    </tr>`;
            }

            tbody.innerHTML = html;

            document.querySelectorAll('#fcp-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openFcpDetailModal(allRecords[idx], idx);
                    }
                });
            });
        }

        function updateStats(historyRecord) {
            if (!historyRecord) return;
            const total = historyRecord.game || 0;
            const playerWins = historyRecord.player_win || 0;
            const dealerWins = historyRecord.dealer_win || 0;
            const pushes = historyRecord.push || 0;
            const folds = historyRecord.fold || 0;

            const winRate = total > 0 ? (playerWins / total * 100) : 0;
            const playerPct = total > 0 ? (playerWins / total * 100) : 0;
            const dealerPct = total > 0 ? (dealerWins / total * 100) : 0;
            const pushPct = total > 0 ? (pushes / total * 100) : 0;
            const foldPct = total > 0 ? (folds / total * 100) : 0;

            document.getElementById('fcp-total').textContent = total;
            document.getElementById('fcp-winrate').textContent = winRate.toFixed(1) + '%';
            document.getElementById('fcp-player-wins').textContent = playerWins;
            document.getElementById('fcp-dealer-wins').textContent = dealerWins;
            document.getElementById('fcp-pushes').textContent = pushes;
            document.getElementById('fcp-folds').textContent = folds;
            document.getElementById('fcp-player-pct').textContent = playerPct.toFixed(1) + '%';
            document.getElementById('fcp-dealer-pct').textContent = dealerPct.toFixed(1) + '%';
            document.getElementById('fcp-push-pct').textContent = pushPct.toFixed(1) + '%';
            document.getElementById('fcp-fold-pct').textContent = foldPct.toFixed(1) + '%';
        }

        async function loadFcp() {
            try {
                const resp = await fetch(FCP_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                if (!data.history || !Array.isArray(data.history)) {
                    throw new Error('数据格式错误：缺少 history 数组');
                }
                allRecords = data.history;

                if (data.history_record) {
                    updateStats(data.history_record);
                }

                renderFcpTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('FCP load error:', err);
                document.getElementById('fcp-history-body').innerHTML =
                    `<tr><td colspan="7" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        function openFcpDetailModal(game, index) {
            // 玩家牌
            document.getElementById('fcp-detail-player').innerHTML =
                formatCardsWithBrace(game.player_cards, 'player', true) || '—';

            // 庄家牌
            document.getElementById('fcp-detail-dealer').innerHTML =
                formatCardsWithBrace(game.dealer_cards, 'dealer', true) || '—';

            document.getElementById('fcp-detail-index').textContent = (index + 1);
            document.getElementById('fcp-detail-cut').textContent = game.cut_position ?? '—';

            // 模式（中文）
            const mode = game.game_mode || 'basic';
            const modeEl = document.getElementById('fcp-detail-mode');
            if (mode === 'crazy') {
                modeEl.innerHTML = '<span class="mode-tag crazy">疯狂</span>';
            } else {
                modeEl.innerHTML = '<span class="mode-tag">基本</span>';
            }

            const deckContainer = document.getElementById('fcp-detail-deck');
            deckContainer.innerHTML = '';
            if (game.deck_order && Array.isArray(game.deck_order)) {
                const cutPos = game.cut_position;
                const total = game.deck_order.length;
                const dealerLen = game.dealer_cards ? game.dealer_cards.length : 5;

                game.deck_order.forEach((card, idx) => {
                    const span = document.createElement('span');
                    span.className = 'deck-card';
                    let offset = (idx - cutPos + total) % total;
                    if (offset >= 0 && offset <= 4) {
                        span.classList.add('color-green');
                    } else if (dealerLen === 6 && offset >= 5 && offset <= 10) {
                        span.classList.add('color-red');
                    } else if (dealerLen === 5 && offset >= 5 && offset <= 9) {
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

            const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
            document.getElementById('fcp-detail-time').textContent = time;

            const isFold = game.fold === true;
            const winner = game.result?.winner || '';
            const winnings = game.result?.winnings ?? 0;
            let resultText = '';
            if (winner === 'fold') {
                resultText = '弃牌';
            } else if (winner === 'player') {
                resultText = `<span class="highlight-win">玩家胜 (赢 $${winnings.toFixed(0)})</span>`;
            } else if (winner === 'dealer') {
                resultText = `<span class="highlight-lose">庄家胜</span>`;
            } else if (winner === 'push') {
                resultText = `<span class="highlight-push">平局 (赢 $${winnings.toFixed(0)})</span>`;
            } else {
                resultText = '—';
            }
            document.getElementById('fcp-detail-result').innerHTML = resultText;

            document.getElementById('fcpDetailModal').classList.add('active');
        }

        function closeFcpDetailModal() {
            document.getElementById('fcpDetailModal').classList.remove('active');
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadFcp();

            document.getElementById('fcpPageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderFcpTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('fcpPageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderFcpTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('fcpModalCloseBtn').addEventListener('click', closeFcpDetailModal);
            document.getElementById('fcpDetailModal').addEventListener('click', function(e) {
                if (e.target === this) closeFcpDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeFcpDetailModal();
            });

            setInterval(loadFcp, 1000);
        });
    })();
</script>