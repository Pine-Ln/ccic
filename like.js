// ==UserScript==
// @name         New Userscript
// @namespace    http://tampermonkey.net/
// @version      2025-05-20
// @description  try to take over the world!
// @author       You
// @match        http://www.jasongjz.top:8000/app/
// @icon         https://www.google.com/s2/favicons?sz=64&domain=jasongjz.top
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Your code here...
})();// ==UserScript==
// @name         Auto Like All Buttons
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  自动点击所有“点赞”按钮，并提供可调频率的控制面板（美化样式）
// @author       YourName
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 创建可视化控制面板
    const panel = document.createElement('div');
    panel.id = 'tm-like-panel';
    panel.innerHTML = `
        <div class="tm-panel-header">点赞面板</div>
        <div class="tm-panel-body">
            <div class="tm-row"><span class="tm-label">状态:</span> <span id="tm-like-status">等待中</span></div>
            <div class="tm-row"><span class="tm-label">频率 (秒):</span> <input type="number" id="tm-interval" value="5" min="1"></div>
            <div class="tm-buttons">
                <button id="tm-like-start">开始</button>
                <button id="tm-like-stop">停止</button>
            </div>
            <div id="tm-like-log" class="tm-log">日志:<br></div>
        </div>
    `;
    document.body.appendChild(panel);

    // 美化面板样式
    const style = document.createElement('style');
    style.innerHTML = `
        #tm-like-panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 240px;
            background: linear-gradient(135deg, #ff8a00, #da1b60);
            color: #fff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            overflow: hidden;
            z-index: 9999;
        }
        #tm-like-panel .tm-panel-header {
            background: rgba(0,0,0,0.2);
            padding: 8px 12px;
            font-size: 16px;
            font-weight: bold;
            text-align: center;
        }
        #tm-like-panel .tm-panel-body {
            padding: 12px;
        }
        #tm-like-panel .tm-row {
            margin-bottom: 8px;
            display: flex;
            align-items: center;
        }
        #tm-like-panel .tm-label {
            flex: 0 0 80px;
            font-weight: 500;
        }
        #tm-like-panel input[type="number"] {
            width: 60px;
            padding: 4px;
            border: none;
            border-radius: 4px;
            text-align: center;
        }
        #tm-like-panel .tm-buttons {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        #tm-like-panel button {
            flex: 1;
            margin: 0 4px;
            padding: 6px 0;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        #tm-like-start {
            background: #28a745;
        }
        #tm-like-start:hover {
            background: #218838;
        }
        #tm-like-stop {
            background: #dc3545;
        }
        #tm-like-stop:hover {
            background: #c82333;
        }
        #tm-like-panel .tm-log {
            max-height: 120px;
            overflow-y: auto;
            background: rgba(255,255,255,0.1);
            padding: 6px;
            border-radius: 6px;
            font-size: 12px;
            line-height: 1.4;
        }
    `;
    document.head.appendChild(style);

    let intervalId = null;
    let running = false;

    function log(msg) {
        const logEl = document.getElementById('tm-like-log');
        logEl.innerHTML += `${new Date().toLocaleTimeString()} - ${msg}<br>`;
        logEl.scrollTop = logEl.scrollHeight;
    }

    function updateStatus(text) {
        document.getElementById('tm-like-status').textContent = text;
    }

    function doLikeAll() {
        const buttons = document.querySelectorAll('button.like-button[data-id]');
        if (buttons.length === 0) {
            log('未找到任何点赞按钮');
            return;
        }
        buttons.forEach(btn => {
            try {
                btn.click();
                log(`已点击: id=${btn.getAttribute('data-id')}`);
            } catch (e) {
                log(`点击失败: id=${btn.getAttribute('data-id')}`);
            }
        });
        updateStatus('已点赞 ' + buttons.length + ' 个');
    }

    document.getElementById('tm-like-start').addEventListener('click', () => {
        if (running) return;
        const sec = parseFloat(document.getElementById('tm-interval').value) || 5;
        running = true;
        updateStatus('自动中...');
        log(`启动: 每 ${sec} 秒`);
        intervalId = setInterval(doLikeAll, sec * 1000);
    });

    document.getElementById('tm-like-stop').addEventListener('click', () => {
        if (!running) return;
        clearInterval(intervalId);
        running = false;
        updateStatus('已停止');
        log('已停止自动点赞');
    });

})();
